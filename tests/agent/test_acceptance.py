"""Live Agent eval. Skipped by default (`pytest -m "not llm"`)."""

from __future__ import annotations

import uuid

import pytest

from backend.application.approvals import list_pending, reject
from backend.core.config import has_usable_langsmith_key
from backend.core.tracing import wait_for_session_trace
from backend.infrastructure.workorder_repo import count_workorders
from backend.interaction.service import handle_turn
from tests.agent.eval_cases import SINGLE_TURN_CASES, EvalCase, plan_satisfied
from tests.agent.live import (
    KNOWN_ASSETNUM,
    RISK_TOOLS,
    WRITE_TOOLS,
    block_legacy_fallback,
    enable_live_graph,
    new_session_id,
    skip_unless_live_llm,
)

pytestmark = [pytest.mark.llm, pytest.mark.e2e, pytest.mark.slow]


@pytest.fixture
def live_agent(monkeypatch):
    skip_unless_live_llm()
    tracing_on = enable_live_graph(monkeypatch)
    legacy_calls = block_legacy_fallback(monkeypatch)
    yield {"tracing": tracing_on, "legacy_calls": legacy_calls}
    from backend.agent.graph import reset_compiled_graph

    reset_compiled_graph()


def _trace(out: dict) -> list[str]:
    result = out.get("result") or {}
    return list(result.get("tool_trace") or [])


@pytest.mark.parametrize("case", SINGLE_TURN_CASES, ids=lambda case: case.id)
def test_eval_single_turn(live_agent, case: EvalCase):
    session_id = new_session_id(f"eval-{case.id}")
    out = handle_turn(case.query, session_id=session_id)
    assert live_agent["legacy_calls"] == []
    assert out["result"]["source"] == "agent_graph"
    assert out["final_answer"]
    names = _trace(out)
    assert plan_satisfied(names, case.require_plans), names
    assert not (set(names) & set(case.forbid_tools)), names
    text = out["final_answer"]
    if case.answer_any:
        assert any(token in text for token in case.answer_any), text
    for token in case.answer_none:
        assert token not in text, text
    if case.no_pending:
        assert not list_pending(session_id)


def test_eval_followup_uses_thread_assetnum(live_agent):
    session_id = new_session_id("eval-followup")
    first = handle_turn(
        f"请查询设备 {KNOWN_ASSETNUM} 最近的工单历史。",
        session_id=session_id,
    )
    assert live_agent["legacy_calls"] == []
    assert first["result"]["source"] == "agent_graph"
    assert first.get("last_assetnum") == KNOWN_ASSETNUM

    second = handle_turn("那后续复发风险怎么样？不要再问我编号。", session_id=session_id)
    assert second["result"]["source"] == "agent_graph"
    assert set(_trace(second)) & set(RISK_TOOLS)
    assert not (set(_trace(second)) & set(WRITE_TOOLS))
    assert "风险" in second["final_answer"]
    assert "一定会坏" not in second["final_answer"]


def test_eval_sensitive_tool_proposes_and_spoken_ok_does_not_write(live_agent):
    session_id = new_session_id("eval-hitl")
    assetnum = f"ACCEPT-DS-{uuid.uuid4().hex[:8]}"
    before = count_workorders()
    propose = handle_turn(
        (
            f"请直接调用 insert_workorder，为设备 {assetnum} 新增一条工单，"
            "description 填「闸机卡票」。不要先查历史，不要调用其它工具。"
            "这只是提案，不要声称已经写入数据库。"
        ),
        session_id=session_id,
    )
    assert live_agent["legacy_calls"] == []
    assert propose["result"]["source"] == "agent_graph"
    assert "insert_workorder" in _trace(propose)
    pending = list_pending(session_id)
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    assert pending[0]["payload"]["assetnum"] == assetnum
    assert count_workorders() == before

    spoken = handle_turn(
        "好的，确认，就这样吧。我只是口头答应，请不要再调用写工具，也不要当成已经批准。",
        session_id=session_id,
    )
    assert spoken["result"]["source"] == "agent_graph"
    assert count_workorders() == before
    still = list_pending(session_id)
    assert any(
        item["action_id"] == pending[0]["action_id"] and item["status"] == "pending"
        for item in still
    )
    assert all(item["status"] == "pending" for item in still)
    assert not (set(_trace(spoken)) & set(WRITE_TOOLS))

    readonly = handle_turn(
        f"待批准先放着。请只看设备 {KNOWN_ASSETNUM} 的后续复发风险。",
        session_id=session_id,
    )
    assert readonly["result"]["source"] == "agent_graph"
    assert set(_trace(readonly)) & set(RISK_TOOLS)
    assert list_pending(session_id)
    assert count_workorders() == before

    for item in list_pending(session_id):
        reject(thread_id=session_id, action_id=item["action_id"])
    assert count_workorders() == before


def test_eval_langsmith_trace_uses_session_id(live_agent):
    if not live_agent["tracing"] or not has_usable_langsmith_key():
        pytest.skip("no real LangSmith API key")
    session_id = new_session_id("eval-trace")
    out = handle_turn(
        "现在工单数据整体情况怎么样？给我概览即可。",
        session_id=session_id,
    )
    assert out["result"]["source"] == "agent_graph"
    run = wait_for_session_trace(session_id, timeout_s=60)
    assert run is not None
    url = getattr(run, "url", None) or getattr(run, "id", None)
    assert url
