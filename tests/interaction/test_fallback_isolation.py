"""Legacy fallback is isolated from Agent graph programming errors."""

from __future__ import annotations

import pytest

from backend.core.errors import LLMUnavailableError
from backend.interaction.service import handle_turn


def test_graph_programming_error_does_not_call_understand(monkeypatch):
    understand_calls: list[str] = []

    def boom(*_args, **_kwargs):
        understand_calls.append("called")
        raise AssertionError("understand must not run on graph bugs")

    monkeypatch.setenv("AFVC_USE_LLM", "true")
    monkeypatch.setenv("AFVC_AGENT_GRAPH", "true")
    monkeypatch.setattr("backend.interaction.understand.understand", boom)
    monkeypatch.setattr(
        "backend.agent.graph.invoke_main_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("tool schema boom")),
    )
    with pytest.raises(ValueError, match="tool schema boom"):
        handle_turn("帮我分析设备 1000029970", session_id="fallback-bug")
    assert understand_calls == []


def test_llm_unavailable_falls_back_observably(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "true")
    monkeypatch.setenv("AFVC_AGENT_GRAPH", "true")
    monkeypatch.setattr(
        "backend.agent.graph.invoke_main_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(LLMUnavailableError("provider down")),
    )
    out = handle_turn("你好", session_id="fallback-llm")
    assert out["status"] in {"success", "clarified", "rejected"}
    assert out["result"]["degraded"] == "llm_unavailable"
    assert out["result"]["source"] == "legacy_fallback"
    assert out["final_answer"]


def test_legacy_path_still_used_when_graph_disabled(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    monkeypatch.setenv("AFVC_AGENT_GRAPH", "true")
    out = handle_turn("帮我分析设备 1000029970", session_id="fallback-legacy")
    assert out["use_case"] == "diagnose_device"
    assert out["assetnum"] == "1000029970"
