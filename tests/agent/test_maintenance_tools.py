"""Maintenance-loop read tools share Application usecases with HTTP."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from backend.agent.graph import build_graph, invoke_main_agent
from backend.agent.tools import TOOL_TO_USE_CASE, build_exposed_tools
from backend.application.capabilities import CAPABILITIES, ToolTier, is_sensitive
from tests.agent.test_main_graph import ScriptedChatModel


def test_exposed_tools_include_maintenance_reads():
    names = {tool.name for tool in build_exposed_tools()}
    assert "list_maintenance_suggestions" in names
    assert "list_maintenance_tasks" in names
    assert TOOL_TO_USE_CASE["list_maintenance_suggestions"] == "list_maintenance_suggestions"
    assert TOOL_TO_USE_CASE["list_maintenance_tasks"] == "list_maintenance_tasks"
    assert CAPABILITIES["list_maintenance_suggestions"]["layer"] == "maintenance"
    assert CAPABILITIES["list_maintenance_tasks"]["exposed"] is True
    assert is_sensitive("list_maintenance_suggestions") is False


def test_maintenance_write_capabilities_remain_unexposed():
    names = {tool.name for tool in build_exposed_tools()}
    for name in (
        "create_maintenance_task",
        "adjust_maintenance_task",
        "submit_maintenance_feedback",
    ):
        assert name not in names
        assert CAPABILITIES[name]["exposed"] is False
        assert CAPABILITIES[name]["tier"] == ToolTier.SENSITIVE


def test_list_maintenance_suggestions_tool_returns_ranked_payload():
    tools = {tool.name: tool for tool in build_exposed_tools()}
    raw = tools["list_maintenance_suggestions"].invoke(
        {"top_n": 3, "fault_focus": "暂停服务"}
    )
    payload = json.loads(raw)
    assert payload["status"] == "success"
    assert payload["ranking_method"] == "deterministic_weighted_rules"
    assert isinstance(payload["suggestions"], list)
    assert len(payload["suggestions"]) <= 3
    if payload["suggestions"]:
        row = payload["suggestions"][0]
        assert "assetnum" in row
        assert "score" in row
        assert isinstance(row.get("reasons"), list)


def test_list_maintenance_tasks_tool_returns_list_payload():
    tools = {tool.name: tool for tool in build_exposed_tools()}
    raw = tools["list_maintenance_tasks"].invoke({})
    payload = json.loads(raw)
    assert payload["status"] == "success"
    assert "tasks" in payload
    assert payload["count"] == len(payload["tasks"])


def test_agent_can_call_list_maintenance_suggestions(monkeypatch):
    understand_calls: list[str] = []

    def boom(*_args, **_kwargs):
        understand_calls.append("called")
        raise AssertionError("understand.py must not run on the main agent path")

    monkeypatch.setattr("backend.interaction.understand.understand", boom)

    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "list_maintenance_suggestions",
                        "args": {"top_n": 2, "fault_focus": "暂停服务"},
                        "id": "call_sug",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="以下为今日检修建议（服务端已排序，未重排）。",
            ),
        ]
    )
    graph = build_graph(llm=llm, checkpointer=MemorySaver())
    out = invoke_main_agent(
        "今天优先安排哪些闸机检修？",
        session_id="maint-suggestions-graph",
        graph=graph,
    )
    assert out["tool_trace"] == ["list_maintenance_suggestions"]
    assert understand_calls == []
