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


def test_list_maintenance_suggestions_tool_returns_user_facing_reasons(monkeypatch):
    monkeypatch.setattr("backend.agent.tools.usecases.list_maintenance_suggestions", lambda **_: {
        "status": "success",
        "message": "今日检修建议生成成功",
        "fault_focus": "暂停服务",
        "suggestions": [{
            "assetnum": "DEMO-AGM-018",
            "station_name": "北辰站",
            "fault_focus": "暂停服务",
            "warning_level": "橙色预警",
            "risk_90d": 0.75,
            "score": 0.8015,
            "reasons": [
                "90 日复发风险 0.75",
                "站点重要度 0.96（虚构站点模拟权重）",
                "近史 5/8 条含「暂停服务」",
                "匹配班组 虚构检修1组（合成排班，非真实人员）",
            ],
            "data_note": "人员/备件/站点重要度为模拟表",
        }],
        "ranking_method": "deterministic_weighted_rules",
        "model_note": "风险输入：prediction_results.csv",
    })
    tools = {tool.name: tool for tool in build_exposed_tools()}
    raw = tools["list_maintenance_suggestions"].invoke(
        {"top_n": 3, "fault_focus": "暂停服务"}
    )
    payload = json.loads(raw)
    assert payload["status"] == "success"
    assert payload["order_note"] == "以下顺序由服务端提供，请保持原顺序。"
    assert isinstance(payload["suggestions"], list)
    assert len(payload["suggestions"]) <= 3
    if payload["suggestions"]:
        row = payload["suggestions"][0]
        assert row["assetnum"] == "DEMO-AGM-018"
        assert row["risk_90d"] == "75%"
        assert row["reasons"][0] == "未来 90 天内再次出现故障工单的风险参考值为 75%"
        assert "体验数据" in row["reasons"][1]
        assert "resource_data_note" in payload
        assert payload["suggestion_generated_at"] == "接口未提供建议生成时间"
        assert "ranking_method" not in payload and "score" not in row
        assert "prediction_results.csv" not in raw and "虚构站点模拟权重" not in raw


def test_risk_tools_hide_internal_source_fields_and_report_missing_freshness(monkeypatch):
    monkeypatch.setattr("backend.agent.tools.usecases.predict_device_risk", lambda **_: {
        "status": "success", "assetnum": "DEMO-AGM-018", "station_name": "北辰站", "line": "D02",
        "risk_30d": 0.43, "risk_90d": 0.75, "warning_level": "橙色预警",
        "prediction_source": "external_prediction_csv", "prediction_tier": "model",
        "model_note": "prediction_results.csv", "main_risk_factors": ["预测结果来自外部模型结果表"],
    })
    monkeypatch.setattr("backend.agent.tools.usecases.list_high_risk_devices", lambda **_: {
        "status": "success", "prediction_source": "external_prediction_csv", "prediction_tier": "model",
        "model_note": "prediction_results.csv", "devices": [{
            "assetnum": "DEMO-AGM-018", "risk_30d": 0.43, "risk_90d": 0.75,
        }],
    })
    tools = {tool.name: tool for tool in build_exposed_tools()}
    risk = json.loads(tools["predict_device_risk"].invoke({"assetnum": "DEMO-AGM-018"}))
    high_risk = json.loads(tools["list_high_risk"].invoke({"top_n": 2}))
    for payload in (risk, high_risk):
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "external_prediction_csv" not in serialized
        assert "prediction_results.csv" not in serialized
        assert "prediction_source" not in serialized
        assert "接口未提供更新时间" in serialized
    assert risk["risk_by_window"]["30 天"] == "43%"
    assert high_risk["devices"][0]["risk_by_window"]["90 天"] == "75%"


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
