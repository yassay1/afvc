"""LangSmith bootstrap is a no-op without a real key."""

from __future__ import annotations

from backend.core.tracing import configure_langsmith


def test_configure_langsmith_noop_without_key(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "your-langsmith-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    assert configure_langsmith(force=True) is False


def test_configure_langsmith_sets_env_when_forced(monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_fake_test_key_not_example")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_PROJECT", "afvc-test")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_CALLBACKS_BACKGROUND", "true")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "")
    assert configure_langsmith(force=True) is True
    import os

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "afvc-test"
    assert os.environ["LANGCHAIN_PROJECT"] == "afvc-test"
