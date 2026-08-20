"""Shared setup for live Agent tests. Default pytest run still skips these."""

from __future__ import annotations

import os
import uuid

import pytest

from backend.core.config import has_usable_langsmith_key, has_usable_llm_key, is_sql_backend

KNOWN_ASSETNUM = "1000029970"
WRITE_TOOLS = frozenset(
    {
        "insert_workorder",
        "update_workorder",
        "delete_workorder",
        "import_workorders",
    }
)
HISTORY_TOOLS = frozenset({"get_device_history", "diagnose_device"})
RISK_TOOLS = frozenset({"predict_device_risk", "diagnose_device", "advise_maintenance"})


def skip_unless_live_llm() -> None:
    if not has_usable_llm_key():
        pytest.skip("no real LLM API key")
    if not is_sql_backend():
        pytest.skip("Postgres 不可用")


def new_session_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def enable_live_graph(monkeypatch: pytest.MonkeyPatch, *, force_tracing: bool = True) -> bool:
    """Turn on the LangGraph+LLM path for this test process. Returns tracing-on."""
    monkeypatch.setenv("AFVC_USE_LLM", "true")
    monkeypatch.setenv("AFVC_AGENT_GRAPH", "true")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", os.getenv("OPENAI_TIMEOUT_SECONDS", "90"))
    monkeypatch.setenv("OPENAI_MAX_RETRIES", os.getenv("OPENAI_MAX_RETRIES", "2"))
    from backend.core.tracing import configure_langsmith
    from backend.agent.graph import reset_compiled_graph

    tracing_on = False
    if force_tracing and has_usable_langsmith_key():
        tracing_on = configure_langsmith(force=True, project=os.getenv("LANGSMITH_PROJECT", "afvc"))
    reset_compiled_graph()
    return tracing_on


def block_legacy_fallback(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Live Agent tests must not silently fall back to understand.py."""
    calls: list[str] = []

    def boom(*_args, **_kwargs):
        calls.append("legacy")
        raise AssertionError("understand/legacy path must not run on live Agent tests")

    monkeypatch.setattr("backend.interaction.service.handle_turn_legacy", boom)
    monkeypatch.setattr("backend.interaction.understand.understand", boom)
    return calls
