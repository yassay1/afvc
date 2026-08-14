"""Sensitive tools create proposals; spoken confirmation does not approve."""

from __future__ import annotations

import uuid

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.agent.graph import build_graph, invoke_main_agent
from backend.agent.tools import build_exposed_tools
from backend.application.capabilities import CAPABILITIES, ToolTier, is_sensitive
from backend.core.config import is_sql_backend
from backend.infrastructure.workorder_repo import count_workorders
from backend.application.approvals import list_pending
from tests.agent.test_main_graph import ScriptedChatModel

pytestmark = pytest.mark.skipif(not is_sql_backend(), reason="Postgres 不可用")


def test_registry_marks_write_tools_sensitive():
    names = {tool.name for tool in build_exposed_tools()}
    for name in ("insert_workorder", "update_workorder", "delete_workorder", "import_workorders"):
        assert name in names
        assert is_sensitive(name)
    assert is_sensitive("get_overview") is False
    assert all(
        is_sensitive(name) is (meta["tier"] == ToolTier.SENSITIVE)
        for name, meta in CAPABILITIES.items()
    )


def test_agent_sensitive_tool_creates_proposal_without_writing():
    before = count_workorders()
    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "insert_workorder",
                        "args": {
                            "assetnum": "HITL-GRAPH-001",
                            "description": "图提案探针",
                        },
                        "id": "call_ins",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="已提交插入提案，等待你在界面批准。口语确认不会写库。"),
        ]
    )
    session_id = f"hitl-graph-propose-{uuid.uuid4()}"
    graph = build_graph(llm=llm, checkpointer=MemorySaver())
    out = invoke_main_agent(
        "请帮我新增一条设备 HITL-GRAPH-001 的工单",
        session_id=session_id,
        graph=graph,
    )
    assert "insert_workorder" in out["tool_trace"]
    assert count_workorders() == before
    pending = list_pending(session_id)
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    assert pending[0]["payload"]["assetnum"] == "HITL-GRAPH-001"
    assert out["pending_actions"][0]["action_id"] == pending[0]["action_id"]


def test_spoken_ok_does_not_approve_pending_action():
    from backend.application.approvals import propose_write

    before = count_workorders()
    session_id = f"hitl-spoken-ok-{uuid.uuid4()}"
    action = propose_write(
        thread_id=session_id,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-OK-001", "description": "口语确认探针"},
    )
    llm = ScriptedChatModel(
        responses=[AIMessage(content="收到。批准需要你点击界面按钮，我说好的不会写库。")]
    )
    graph = build_graph(llm=llm, checkpointer=MemorySaver())
    invoke_main_agent("好的，确认，就这样吧", session_id=session_id, graph=graph)
    pending = list_pending(session_id)
    assert any(item["action_id"] == action["action_id"] and item["status"] == "pending" for item in pending)
    assert count_workorders() == before


def test_pending_thread_can_still_run_readonly_tools():
    from backend.application.approvals import propose_write

    session_id = f"hitl-readonly-{uuid.uuid4()}"
    propose_write(
        thread_id=session_id,
        tool_name="insert_workorder",
        payload={"assetnum": "HITL-RO-001", "description": "并存只读"},
    )
    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "predict_device_risk",
                        "args": {"assetnum": "1000029970"},
                        "id": "call_risk_pending",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="待批准写操作仍在，同时风险结果如下。风险不是故障日期。"),
        ]
    )
    graph = build_graph(llm=llm, checkpointer=MemorySaver())
    out = invoke_main_agent(
        "设备 1000029970 后续风险如何",
        session_id=session_id,
        graph=graph,
    )
    assert out["tool_trace"] == ["predict_device_risk"]
    assert list_pending(session_id)
