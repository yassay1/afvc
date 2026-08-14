"""Pending-action persistence and atomic status transitions."""

from __future__ import annotations

import logging
from typing import Any

from psycopg.types.json import Jsonb

from backend.domain.pending_action import (
    FAILED,
    PENDING,
    REJECTED,
    ActionConflictError,
    ActionNotFoundError,
    assert_transition,
)
from backend.infrastructure.db import get_pool

logger = logging.getLogger("afvc.pending_action_repo")


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "hex") and not isinstance(value, str):
            out[key] = str(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def insert_pending(
    *,
    thread_id: str,
    tool_name: str,
    payload: dict[str, Any],
    summary: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            INSERT INTO agent.pending_actions (
                thread_id, tool_name, payload, summary, status, actor_id
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, thread_id, tool_name, payload, summary, status,
                      created_at, resolved_at, actor_id, result
            """,
            (thread_id, tool_name, Jsonb(payload), summary, PENDING, actor_id),
        ).fetchone()
        conn.commit()
    assert row is not None
    logger.info("pending action created id=%s tool=%s thread=%s", row["id"], tool_name, thread_id)
    return _serialize(dict(row))


def get_action(action_id: str, *, thread_id: str | None = None) -> dict[str, Any] | None:
    sql = """
        SELECT id, thread_id, tool_name, payload, summary, status,
               created_at, resolved_at, actor_id, result
        FROM agent.pending_actions
        WHERE id = %s
    """
    params: list[Any] = [action_id]
    if thread_id is not None:
        sql += " AND thread_id = %s"
        params.append(thread_id)
    with get_pool().connection() as conn:
        row = conn.execute(sql, params).fetchone()
    return _serialize(dict(row)) if row is not None else None


def list_by_thread(thread_id: str, *, status: str | None = PENDING) -> list[dict[str, Any]]:
    sql = """
        SELECT id, thread_id, tool_name, payload, summary, status,
               created_at, resolved_at, actor_id, result
        FROM agent.pending_actions
        WHERE thread_id = %s
    """
    params: list[Any] = [thread_id]
    if status is not None:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY created_at ASC"
    with get_pool().connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_serialize(dict(row)) for row in rows]


def lock_action(conn, action_id: str, thread_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT id, thread_id, tool_name, payload, summary, status,
               created_at, resolved_at, actor_id, result
        FROM agent.pending_actions
        WHERE id = %s AND thread_id = %s
        FOR UPDATE
        """,
        (action_id, thread_id),
    ).fetchone()
    if row is None:
        raise ActionNotFoundError(action_id, thread_id)
    return _serialize(dict(row))


def transition(
    conn,
    *,
    action_id: str,
    from_status: str,
    to_status: str,
    result: dict[str, Any] | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    assert_transition(from_status, to_status)
    row = conn.execute(
        """
        UPDATE agent.pending_actions
        SET status = %s,
            result = %s,
            resolved_at = NOW(),
            actor_id = COALESCE(%s, actor_id)
        WHERE id = %s AND status = %s
        RETURNING id, thread_id, tool_name, payload, summary, status,
                  created_at, resolved_at, actor_id, result
        """,
        (to_status, Jsonb(result) if result is not None else None, actor_id, action_id, from_status),
    ).fetchone()
    if row is None:
        raise ActionConflictError(action_id, from_status, "状态已被其他请求更新")
    logger.info("pending action %s: %s -> %s", action_id, from_status, to_status)
    return _serialize(dict(row))


def mark_failed_if_pending(action_id: str, error: str) -> dict[str, Any] | None:
    """Best-effort terminal failure record after the business transaction rolled back."""
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            UPDATE agent.pending_actions
            SET status = %s,
                result = %s,
                resolved_at = NOW()
            WHERE id = %s AND status = %s
            RETURNING id, thread_id, tool_name, payload, summary, status,
                      created_at, resolved_at, actor_id, result
            """,
            (FAILED, Jsonb({"error": error}), action_id, PENDING),
        ).fetchone()
        conn.commit()
    if row is None:
        return None
    logger.warning("pending action %s marked failed: %s", action_id, error)
    return _serialize(dict(row))


def reject_pending(
    conn,
    *,
    action_id: str,
    actor_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return transition(
        conn,
        action_id=action_id,
        from_status=PENDING,
        to_status=REJECTED,
        result={"reason": reason or "用户拒绝"},
        actor_id=actor_id,
    )
