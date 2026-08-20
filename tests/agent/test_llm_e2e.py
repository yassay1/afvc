"""Optional live-LLM smoke. Skipped by default (`pytest -m "not llm"`)."""

from __future__ import annotations

import pytest

from backend.agent.graph import invoke_main_agent
from tests.agent.live import (
    HISTORY_TOOLS,
    KNOWN_ASSETNUM,
    enable_live_graph,
    new_session_id,
    skip_unless_live_llm,
)

pytestmark = [pytest.mark.llm, pytest.mark.e2e]


def test_live_llm_can_select_readonly_history_tool(monkeypatch):
    skip_unless_live_llm()
    enable_live_graph(monkeypatch)
    out = invoke_main_agent(
        f"请查询设备 {KNOWN_ASSETNUM} 最近的工单历史，不要凭记忆回答。",
        session_id=new_session_id("llm-e2e-readonly"),
    )
    assert out["source"] == "agent_graph"
    assert out["final_answer"]
    assert isinstance(out.get("tool_trace"), list)
    assert set(out["tool_trace"]) & HISTORY_TOOLS
