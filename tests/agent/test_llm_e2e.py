"""Optional real-GLM E2E. Skipped by default (`pytest -m "not llm"`)."""

from __future__ import annotations

import os

import pytest

from backend.core.config import is_sql_backend


@pytest.mark.llm
def test_real_glm_can_select_readonly_or_sensitive_tools(monkeypatch):
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or "YOUR" in key.upper():
        pytest.skip("no real LLM API key")
    if not is_sql_backend():
        pytest.skip("Postgres 不可用")

    monkeypatch.setenv("AFVC_USE_LLM", "true")
    monkeypatch.setenv("AFVC_AGENT_GRAPH", "true")
    from backend.agent.graph import invoke_main_agent, reset_compiled_graph

    reset_compiled_graph()
    out = invoke_main_agent(
        "看看设备 1000029970 最近的工单历史",
        session_id="llm-e2e-readonly",
    )
    assert out["source"] == "agent_graph"
    assert out["final_answer"]
    assert isinstance(out.get("tool_trace"), list)
