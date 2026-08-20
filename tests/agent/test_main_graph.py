"""Main Agent graph: multi-tool loop without understand.py."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from pydantic import Field

from backend.agent.data_subgraph import DATA_CAPABILITIES, invoke_data_capability
from backend.agent.graph import build_graph, invoke_main_agent
from backend.agent.tools import TOOL_REGISTRY, build_exposed_tools
from backend.interaction.service import handle_turn


class ScriptedChatModel(BaseChatModel):
    responses: list[AIMessage] = Field(default_factory=list)
    cursor: list[int] = Field(default_factory=lambda: [0])

    @property
    def _llm_type(self) -> str:
        return "scripted-afvc"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        idx = self.cursor[0]
        if idx >= len(self.responses):
            message = AIMessage(content="（脚本模型没有更多响应）")
        else:
            message = self.responses[idx]
            self.cursor[0] = idx + 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def test_exposed_tools_are_capabilities_not_op_enum():
    names = {tool.name for tool in build_exposed_tools()}
    assert "data_op" not in names
    assert "get_overview" in names
    assert "get_device_history" in names
    assert TOOL_REGISTRY["get_overview"]["layer"] == "data"
    assert "detect_device_use_case" not in DATA_CAPABILITIES


def test_data_subgraph_executes_named_capability():
    overview = invoke_data_capability("get_overview", top_n=3)
    assert "basic_metrics" in overview
    assert overview["basic_metrics"]["workorder_count"] > 0


def test_data_subgraph_rejects_unknown_capability():
    import pytest

    with pytest.raises(ValueError, match="unknown data capability"):
        invoke_data_capability("detect_device_use_case")


def test_main_graph_multi_tool_trace_without_understand(monkeypatch):
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
                        "name": "get_device_history",
                        "args": {"assetnum": "1000029970", "limit": 5},
                        "id": "call_hist",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "predict_device_risk",
                        "args": {"assetnum": "1000029970"},
                        "id": "call_risk",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content=(
                    "这台设备近期工单较密，后续窗口内复发风险需要结合风险工具结果解读；"
                    "风险不是具体故障日期。"
                )
            ),
        ]
    )
    graph = build_graph(llm=llm, checkpointer=MemorySaver())
    out = invoke_main_agent(
        "看看这台设备最近为什么老出问题，再判断一下后续风险。设备 1000029970",
        session_id="trace-multi-tool",
        graph=graph,
    )
    assert understand_calls == []
    assert out["tool_trace"] == ["get_device_history", "predict_device_risk"]
    assert out["assetnum"] == "1000029970"
    assert "风险" in out["final_answer"]


def test_missing_device_history_returns_tool_error_not_crash():
    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_device_history",
                        "args": {"assetnum": "NO-SUCH-DEVICE", "limit": 5},
                        "id": "call_hist_missing",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="没有找到这台设备的历史工单，请确认编号或改为新增工单。"),
        ]
    )
    graph = build_graph(llm=llm, checkpointer=MemorySaver())
    out = invoke_main_agent(
        "查一下设备 NO-SUCH-DEVICE 的历史",
        session_id="missing-hist",
        graph=graph,
    )
    assert out["source"] == "agent_graph"
    assert "get_device_history" in out["tool_trace"]
    assert "没有找到" in out["final_answer"]


def test_tool_trace_covers_current_turn_only():
    llm = ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_overview",
                        "args": {"top_n": 3},
                        "id": "call_overview",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="当前工单工作集概览如下。"),
            AIMessage(content="收到，这只是口头确认，不会写库。"),
        ]
    )
    graph = build_graph(llm=llm, checkpointer=MemorySaver())
    session_id = "trace-this-turn"
    first = invoke_main_agent("给我数据概览", session_id=session_id, graph=graph)
    assert first["tool_trace"] == ["get_overview"]
    second = invoke_main_agent("好的，确认", session_id=session_id, graph=graph)
    assert second["tool_trace"] == []
    assert second["use_case"] is None


def test_handle_turn_graph_flag_skips_understand(monkeypatch):
    understand_calls: list[str] = []

    def boom(*_args, **_kwargs):
        understand_calls.append("called")
        raise AssertionError("understand.py must not run on the graph path")

    monkeypatch.setenv("AFVC_USE_LLM", "true")
    monkeypatch.setenv("AFVC_AGENT_GRAPH", "true")
    monkeypatch.setattr("backend.interaction.understand.understand", boom)
    monkeypatch.setattr(
        "backend.agent.graph.invoke_main_agent",
        lambda query, session_id, last_assetnum=None, graph=None: {
            "final_answer": "已查看历史并评估后续风险。",
            "last_assetnum": "1000029970",
            "assetnum": "1000029970",
            "use_case": "predict_device_risk",
            "tool_trace": ["get_device_history", "predict_device_risk"],
            "source": "agent_graph",
        },
    )
    out = handle_turn(
        "看看这台设备最近为什么老出问题，再判断一下后续风险。设备 1000029970",
        session_id="graph-turn-1",
    )
    assert understand_calls == []
    assert out["result"]["source"] == "agent_graph"
    assert out["result"]["tool_trace"] == ["get_device_history", "predict_device_risk"]
    assert out["final_answer"].startswith("已查看历史")
