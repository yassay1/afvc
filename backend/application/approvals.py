"""HITL approval application service. Agent proposes; only this module executes writes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.application.capabilities import is_sensitive
from backend.core.config import is_sql_backend
from backend.domain.pending_action import (
    EXECUTED,
    PENDING,
    REJECTED,
    ActionConflictError,
    ActionExecutionError,
    ActionNotFoundError,
)
from backend.infrastructure import pending_action_repo
from backend.infrastructure.workorder_repo import (
    delete_workorder,
    insert_workorder,
    update_workorder,
)
from backend.infrastructure.workorders import RAW_DATA_DIR
from backend.schemas.workorder_writes import WRITE_PAYLOAD_SCHEMAS

logger = logging.getLogger("afvc.approvals")


def _public_action(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": str(row["id"]),
        "thread_id": row["thread_id"],
        "tool_name": row["tool_name"],
        "status": row["status"],
        "summary": row.get("summary") or "",
        "payload": row.get("payload") or {},
        "result": row.get("result"),
        "created_at": row.get("created_at"),
        "resolved_at": row.get("resolved_at"),
        "executed": row.get("status") == EXECUTED,
    }


def _summary_for(tool_name: str, payload: dict[str, Any]) -> str:
    if tool_name == "insert_workorder":
        return f"插入工单 {payload.get('assetnum')}"
    if tool_name == "update_workorder":
        return f"更新工单 {payload.get('workorder_id')}"
    if tool_name == "delete_workorder":
        return f"删除工单 {payload.get('workorder_id')}"
    if tool_name == "import_workorders":
        return f"导入文件 {payload.get('source_filename')}（{payload.get('mode', 'replace')}）"
    return tool_name


def _resolve_import_path(source_filename: str) -> Path:
    name = Path(source_filename).name
    if name != source_filename:
        raise ValueError("source_filename 只能是 raw 目录下的文件名")
    path = (RAW_DATA_DIR / name).resolve()
    raw_root = RAW_DATA_DIR.resolve()
    if path.parent != raw_root:
        raise ValueError("导入文件必须位于工单 raw 目录内")
    if not path.is_file():
        raise ValueError(f"找不到可导入文件：{name}")
    return path


def _execute_on_connection(conn, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    schema = WRITE_PAYLOAD_SCHEMAS[tool_name]
    parsed = schema.model_validate(payload)
    data = parsed.model_dump(exclude_none=True)
    if tool_name == "insert_workorder":
        row = insert_workorder(data, conn=conn)
        return {"workorder": {key: row.get(key) for key in ("id", "assetnum", "description", "station_name")}}
    if tool_name == "update_workorder":
        workorder_id = data.pop("workorder_id")
        row = update_workorder(workorder_id, data, conn=conn)
        return {"workorder": {key: row.get(key) for key in ("id", "assetnum", "description", "station_name")}}
    if tool_name == "delete_workorder":
        deleted = delete_workorder(data["workorder_id"], conn=conn)
        return {"deleted": True, "workorder_id": deleted["workorder_id"]}
    if tool_name == "import_workorders":
        from backend.infrastructure.workorder_repo import import_from_path

        path = _resolve_import_path(data["source_filename"])
        imported = import_from_path(path, mode=data.get("mode", "replace"), conn=conn)
        return imported
    raise ValueError(f"不支持的写操作：{tool_name}")


def propose_write(
    *,
    thread_id: str,
    tool_name: str,
    payload: dict[str, Any],
    actor_id: str | None = None,
) -> dict[str, Any]:
    if not is_sql_backend():
        raise RuntimeError("写操作提案需要 Postgres 工单库")
    if not is_sensitive(tool_name):
        raise ValueError(f"{tool_name} 不是可审批的写操作")
    schema = WRITE_PAYLOAD_SCHEMAS.get(tool_name)
    if schema is None:
        raise ValueError(f"{tool_name} 没有写操作 schema")
    try:
        parsed = schema.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    data = parsed.model_dump(exclude_none=True)
    row = pending_action_repo.insert_pending(
        thread_id=thread_id,
        tool_name=tool_name,
        payload=data,
        summary=_summary_for(tool_name, data),
        actor_id=actor_id,
    )
    public = _public_action(row)
    public["executed"] = False
    return public


def list_pending(thread_id: str) -> list[dict[str, Any]]:
    if not is_sql_backend():
        return []
    return [_public_action(row) for row in pending_action_repo.list_by_thread(thread_id)]


def approve(
    *,
    thread_id: str,
    action_id: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    if not is_sql_backend():
        raise RuntimeError("批准写操作需要 Postgres 工单库")
    from backend.infrastructure.db import get_pool
    from backend.infrastructure.workorder_repo import invalidate_workorder_cache

    try:
        with get_pool().connection() as conn:
            with conn.transaction():
                action = pending_action_repo.lock_action(conn, action_id, thread_id)
                if action["status"] == EXECUTED:
                    logger.info("approve idempotent action_id=%s", action_id)
                    return {**_public_action(action), "idempotent": True}
                if action["status"] != PENDING:
                    raise ActionConflictError(action_id, action["status"])
                result = _execute_on_connection(conn, action["tool_name"], action["payload"] or {})
                updated = pending_action_repo.transition(
                    conn,
                    action_id=action_id,
                    from_status=PENDING,
                    to_status=EXECUTED,
                    result=result,
                    actor_id=actor_id,
                )
        invalidate_workorder_cache()
        return {**_public_action(updated), "idempotent": False}
    except (ActionConflictError, ActionNotFoundError):
        raise
    except Exception as exc:
        logger.exception("approve business write failed action_id=%s", action_id)
        pending_action_repo.mark_failed_if_pending(action_id, str(exc))
        raise ActionExecutionError(action_id, str(exc)) from exc


def reject(
    *,
    thread_id: str,
    action_id: str,
    actor_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if not is_sql_backend():
        raise RuntimeError("拒绝写操作需要 Postgres 工单库")
    from backend.infrastructure.db import get_pool

    with get_pool().connection() as conn:
        with conn.transaction():
            action = pending_action_repo.lock_action(conn, action_id, thread_id)
            if action["status"] == REJECTED:
                return {**_public_action(action), "idempotent": True}
            if action["status"] != PENDING:
                raise ActionConflictError(action_id, action["status"])
            updated = pending_action_repo.reject_pending(
                conn,
                action_id=action_id,
                actor_id=actor_id,
                reason=reason,
            )
    return {**_public_action(updated), "idempotent": False}
