"""HTTP mapping for HITL approve/reject."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.core.config import is_sql_backend
from backend.application.approvals import propose_write
from backend.infrastructure.workorder_repo import count_workorders, invalidate_workorder_cache
from backend.main import app

pytestmark = pytest.mark.skipif(not is_sql_backend(), reason="Postgres 不可用")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_hitl_rows():
    yield
    from backend.infrastructure.db import get_pool

    with get_pool().connection() as conn:
        conn.execute("DELETE FROM business.workorders WHERE assetnum LIKE %s", ("HITL-%",))
        conn.commit()
    invalidate_workorder_cache()


def test_approve_reject_http_roundtrip():
    thread_id = f"api-hitl-{uuid.uuid4()}"
    before = count_workorders()
    action = propose_write(
        thread_id=thread_id,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-API-001", "description": "API 探针"},
    )
    listed = client.get(f"/interaction/sessions/{thread_id}/pending")
    assert listed.status_code == 200
    assert any(item["action_id"] == action["action_id"] for item in listed.json()["pending_actions"])

    rejected = client.post(
        "/interaction/reject",
        json={"session_id": thread_id, "action_id": action["action_id"]},
    )
    assert rejected.status_code == 200
    assert count_workorders() == before

    second = propose_write(
        thread_id=thread_id,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-API-002", "description": "API 批准探针"},
    )
    approved = client.post(
        "/interaction/approve",
        json={"session_id": thread_id, "action_id": second["action_id"]},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["result"]["action"]["status"] == "executed"
    assert count_workorders() == before + 1

    again = client.post(
        "/interaction/approve",
        json={"session_id": thread_id, "action_id": second["action_id"]},
    )
    assert again.status_code == 200
    assert again.json()["result"]["action"]["idempotent"] is True
    assert count_workorders() == before + 1

    workorder_id = body["result"]["action"]["result"]["workorder"]["id"]
    cleanup = propose_write(
        thread_id=thread_id,
        tool_name="delete_workorder",
        payload={"workorder_id": workorder_id},
    )
    client.post("/interaction/approve", json={"session_id": thread_id, "action_id": cleanup["action_id"]})


def test_approve_rejected_action_conflict():
    thread_id = f"api-hitl-conflict-{uuid.uuid4()}"
    action = propose_write(
        thread_id=thread_id,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-API-CONFLICT", "description": "冲突探针"},
    )
    client.post(
        "/interaction/reject",
        json={"session_id": thread_id, "action_id": action["action_id"]},
    )
    again = client.post(
        "/interaction/approve",
        json={"session_id": thread_id, "action_id": action["action_id"]},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "action_conflict"


def test_approve_unknown_action_not_found():
    response = client.post(
        "/interaction/approve",
        json={"session_id": "api-hitl-missing", "action_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404
