"""检修任务仓储。SQL 后端用 Postgres；file 回退用本地 JSON。"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.config import is_sql_backend
from backend.domain.maintenance import task_public_dict, validate_task_status

_FILE_STORE = Path(__file__).resolve().parent.parent / "data" / "mock" / "maintenance_tasks.json"
_file_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_file_store() -> list[dict[str, Any]]:
    if not _FILE_STORE.exists():
        return []
    with _FILE_STORE.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


def _write_file_store(rows: list[dict[str, Any]]) -> None:
    _FILE_STORE.parent.mkdir(parents=True, exist_ok=True)
    with _FILE_STORE.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)


def create_task(payload: dict[str, Any]) -> dict[str, Any]:
    status = validate_task_status(payload.get("status") or "planned")
    if is_sql_backend():
        return _sql_create(payload, status)
    return _file_create(payload, status)


def list_tasks(*, status: str | None = None) -> list[dict[str, Any]]:
    if is_sql_backend():
        return _sql_list(status=status)
    with _file_lock:
        rows = _read_file_store()
    if status:
        want = validate_task_status(status)
        rows = [r for r in rows if r.get("status") == want]
    rows = sorted(rows, key=lambda r: (int(r.get("priority") or 100), str(r.get("created_at") or "")))
    return [task_public_dict(r) for r in rows]


def get_task(task_id: str) -> dict[str, Any] | None:
    if is_sql_backend():
        return _sql_get(task_id)
    with _file_lock:
        for row in _read_file_store():
            if str(row.get("id")) == str(task_id):
                return task_public_dict(row)
    return None


def update_task(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    if is_sql_backend():
        return _sql_update(task_id, patch)
    return _file_update(task_id, patch)


def record_feedback(
    task_id: str,
    *,
    result: str,
    matched_fault: bool | None,
    followed_suggestion: bool | None,
    note: str | None,
) -> dict[str, Any]:
    patch = {
        "status": "done",
        "feedback_result": result,
        "feedback_matched_fault": matched_fault,
        "feedback_followed_suggestion": followed_suggestion,
        "feedback_note": note,
        "feedback_at": _now_iso(),
    }
    return update_task(task_id, patch)


def _file_create(payload: dict[str, Any], status: str) -> dict[str, Any]:
    now = _now_iso()
    row = {
        "id": str(uuid.uuid4()),
        "assetnum": payload["assetnum"],
        "station_name": payload.get("station_name"),
        "fault_focus": payload.get("fault_focus") or "暂停服务",
        "priority": int(payload.get("priority") or 100),
        "planned_date": payload.get("planned_date"),
        "assignee_crew_id": payload.get("assignee_crew_id"),
        "status": status,
        "suggestion_score": payload.get("suggestion_score"),
        "suggestion_reasons": list(payload.get("suggestion_reasons") or []),
        "feedback_result": None,
        "feedback_matched_fault": None,
        "feedback_followed_suggestion": None,
        "feedback_note": None,
        "feedback_at": None,
        "created_at": now,
        "updated_at": now,
    }
    with _file_lock:
        rows = _read_file_store()
        rows.append(row)
        _write_file_store(rows)
    return task_public_dict(row)


def _file_update(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    with _file_lock:
        rows = _read_file_store()
        found = None
        for idx, row in enumerate(rows):
            if str(row.get("id")) != str(task_id):
                continue
            updated = dict(row)
            for key, value in patch.items():
                if key == "status" and value is not None:
                    updated["status"] = validate_task_status(str(value))
                elif key in updated:
                    updated[key] = value
            updated["updated_at"] = _now_iso()
            rows[idx] = updated
            found = updated
            break
        if found is None:
            raise ValueError(f"检修任务不存在：{task_id}")
        _write_file_store(rows)
    return task_public_dict(found)


def _sql_create(payload: dict[str, Any], status: str) -> dict[str, Any]:
    from backend.infrastructure.db import get_pool

    task_id = uuid.uuid4()
    reasons = json.dumps(list(payload.get("suggestion_reasons") or []), ensure_ascii=False)
    planned = payload.get("planned_date")
    with get_pool().connection() as conn:
        conn.execute(
            """
            INSERT INTO business.maintenance_tasks (
                id, assetnum, station_name, fault_focus, priority, planned_date,
                assignee_crew_id, status, suggestion_score, suggestion_reasons
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            """,
            (
                str(task_id),
                payload["assetnum"],
                payload.get("station_name"),
                payload.get("fault_focus") or "暂停服务",
                int(payload.get("priority") or 100),
                planned,
                payload.get("assignee_crew_id"),
                status,
                payload.get("suggestion_score"),
                reasons,
            ),
        )
        conn.commit()
    got = get_task(str(task_id))
    assert got is not None
    return got


def _sql_list(*, status: str | None) -> list[dict[str, Any]]:
    from backend.infrastructure.db import get_pool

    sql = "SELECT * FROM business.maintenance_tasks"
    params: tuple[Any, ...] = ()
    if status:
        sql += " WHERE status = %s"
        params = (validate_task_status(status),)
    sql += " ORDER BY priority ASC, created_at ASC"
    with get_pool().connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [task_public_dict(dict(r)) for r in rows]


def _sql_get(task_id: str) -> dict[str, Any] | None:
    from backend.infrastructure.db import get_pool

    with get_pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM business.maintenance_tasks WHERE id = %s",
            (task_id,),
        ).fetchone()
    return task_public_dict(dict(row)) if row else None


def _sql_update(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    from backend.infrastructure.db import get_pool

    allowed = {
        "priority",
        "planned_date",
        "assignee_crew_id",
        "status",
        "feedback_result",
        "feedback_matched_fault",
        "feedback_followed_suggestion",
        "feedback_note",
        "feedback_at",
    }
    sets: list[str] = []
    values: list[Any] = []
    for key, value in patch.items():
        if key not in allowed:
            continue
        if key == "status" and value is not None:
            value = validate_task_status(str(value))
        sets.append(f"{key} = %s")
        values.append(value)
    if not sets:
        got = get_task(task_id)
        if got is None:
            raise ValueError(f"检修任务不存在：{task_id}")
        return got
    sets.append("updated_at = NOW()")
    values.append(task_id)
    with get_pool().connection() as conn:
        cur = conn.execute(
            f"UPDATE business.maintenance_tasks SET {', '.join(sets)} WHERE id = %s RETURNING *",
            tuple(values),
        )
        row = cur.fetchone()
        conn.commit()
    if row is None:
        raise ValueError(f"检修任务不存在：{task_id}")
    return task_public_dict(dict(row))
