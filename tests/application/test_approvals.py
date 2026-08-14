"""HITL approval application service — success and failure contracts."""

from __future__ import annotations

import uuid

import pytest

from backend.core.config import is_sql_backend
from backend.domain.pending_action import (
    EXECUTED,
    FAILED,
    PENDING,
    REJECTED,
    ActionConflictError,
    ActionExecutionError,
)
from backend.infrastructure.workorder_repo import count_workorders, get_workorder, invalidate_workorder_cache
from backend.application.approvals import approve, list_pending, propose_write, reject
from backend.application.history import get_device_history
from backend.infrastructure.pending_action_repo import get_action

pytestmark = pytest.mark.skipif(not is_sql_backend(), reason="Postgres 不可用")

THREAD = f"hitl-thread-approvals-{uuid.uuid4()}"


@pytest.fixture(autouse=True)
def _cleanup_hitl_rows():
    yield
    from backend.infrastructure.db import get_pool

    with get_pool().connection() as conn:
        conn.execute("DELETE FROM business.workorders WHERE assetnum LIKE %s", ("HITL-%",))
        conn.commit()
    invalidate_workorder_cache()


def test_propose_insert_does_not_write_business_rows():
    before = count_workorders()
    action = propose_write(
        thread_id=THREAD,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-INS-001", "description": "提案探针"},
    )
    assert action["executed"] is False
    assert action["status"] == PENDING
    assert action["action_id"]
    assert count_workorders() == before
    pending = list_pending(THREAD)
    assert any(item["action_id"] == action["action_id"] for item in pending)


def test_approve_insert_writes_once_and_is_idempotent():
    before = count_workorders()
    action = propose_write(
        thread_id=THREAD,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-INS-002", "description": "批准探针"},
    )
    first = approve(thread_id=THREAD, action_id=action["action_id"])
    assert first["status"] == EXECUTED
    assert first["idempotent"] is False
    assert count_workorders() == before + 1
    workorder_id = first["result"]["workorder"]["id"]
    assert get_workorder(workorder_id) is not None

    second = approve(thread_id=THREAD, action_id=action["action_id"])
    assert second["idempotent"] is True
    assert second["status"] == EXECUTED
    assert count_workorders() == before + 1

    delete_probe = propose_write(
        thread_id=THREAD,
        tool_name="delete_workorder",
        payload={"workorder_id": workorder_id},
    )
    approve(thread_id=THREAD, action_id=delete_probe["action_id"])


def test_reject_never_executes_and_cannot_approve_later():
    before = count_workorders()
    action = propose_write(
        thread_id=THREAD,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-REJ-001", "description": "拒绝探针"},
    )
    rejected = reject(thread_id=THREAD, action_id=action["action_id"])
    assert rejected["status"] == REJECTED
    assert count_workorders() == before
    with pytest.raises(ActionConflictError) as exc:
        approve(thread_id=THREAD, action_id=action["action_id"])
    assert exc.value.status == REJECTED
    assert count_workorders() == before


def test_business_write_failure_marks_failed_and_rolls_back(monkeypatch):
    before = count_workorders()
    action = propose_write(
        thread_id=THREAD,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-FAIL-001", "description": "失败探针"},
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr("backend.application.approvals.insert_workorder", boom)
    with pytest.raises(ActionExecutionError):
        approve(thread_id=THREAD, action_id=action["action_id"])
    stored = get_action(action["action_id"], thread_id=THREAD)
    assert stored is not None
    assert stored["status"] == FAILED
    assert "simulated write failure" in str(stored["result"])
    assert count_workorders() == before


def test_update_and_delete_missing_record_fails_clearly():
    missing_id = str(uuid.uuid4())
    update_action = propose_write(
        thread_id=THREAD,
        tool_name="update_workorder",
        payload={"workorder_id": missing_id, "description": "不存在"},
    )
    with pytest.raises(ActionExecutionError, match="工单不存在"):
        approve(thread_id=THREAD, action_id=update_action["action_id"])
    stored = get_action(update_action["action_id"], thread_id=THREAD)
    assert stored is not None
    assert stored["status"] == FAILED

    delete_action = propose_write(
        thread_id=THREAD,
        tool_name="delete_workorder",
        payload={"workorder_id": missing_id},
    )
    with pytest.raises(ActionExecutionError, match="工单不存在"):
        approve(thread_id=THREAD, action_id=delete_action["action_id"])


def test_payload_rejects_unknown_fields_and_action_id_override():
    with pytest.raises(ValueError):
        propose_write(
            thread_id=THREAD,
            tool_name="insert_workorder",
            payload={"assetnum": "X", "action_id": "forged", "id": "also-forged"},
        )
    with pytest.raises(ValueError):
        propose_write(
            thread_id=THREAD,
            tool_name="import_workorders",
            payload={"source_filename": "../secret.xlsx", "mode": "replace"},
        )


def test_history_exposes_workorder_id_for_update_target():
    history = get_device_history("1000029970", limit=1)
    assert history["history"]
    assert "workorder_id" in history["history"][0]


def test_pending_does_not_block_new_proposals_on_same_thread():
    first = propose_write(
        thread_id=THREAD,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-MULTI-1", "description": "并存1"},
    )
    second = propose_write(
        thread_id=THREAD,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-MULTI-2", "description": "并存2"},
    )
    pending_ids = {item["action_id"] for item in list_pending(THREAD)}
    assert first["action_id"] in pending_ids
    assert second["action_id"] in pending_ids
    reject(thread_id=THREAD, action_id=first["action_id"])
    reject(thread_id=THREAD, action_id=second["action_id"])
