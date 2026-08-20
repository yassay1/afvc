"""LangSmith tracing bootstrap. No-op when disabled or the API key is missing."""

from __future__ import annotations

import os
import time
from typing import Any

from backend.core.config import (
    LANGSMITH_API_KEY,
    LANGSMITH_PROJECT,
    LANGSMITH_TRACING,
    has_usable_langsmith_key,
)


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def tracing_requested() -> bool:
    return _flag(os.getenv("LANGSMITH_TRACING", LANGSMITH_TRACING))


def configure_langsmith(*, force: bool = False, project: str | None = None) -> bool:
    """Enable LangChain/LangGraph auto-tracing when a usable LangSmith key is present.

    Returns True if tracing is active for this process.
    """
    if not has_usable_langsmith_key():
        return False
    if not force and not tracing_requested():
        return False
    key = os.getenv("LANGSMITH_API_KEY", LANGSMITH_API_KEY).strip()
    project_name = (
        project
        or os.getenv("LANGSMITH_PROJECT", LANGSMITH_PROJECT).strip()
        or "afvc"
    )
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_CALLBACKS_BACKGROUND"] = "false"
    os.environ["LANGSMITH_API_KEY"] = key
    os.environ["LANGSMITH_PROJECT"] = project_name
    os.environ["LANGCHAIN_PROJECT"] = project_name
    return True


def flush_tracers() -> None:
    """Block until local LangSmith tracer queues are empty."""
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers

        wait_for_all_tracers()
    except Exception:
        try:
            from langsmith.run_trees import wait_for_all_tracers as _wait

            _wait()
        except Exception:
            return


def _run_session_id(run: Any) -> str | None:
    extra = getattr(run, "extra", None) or {}
    metadata = extra.get("metadata") if isinstance(extra, dict) else None
    if not isinstance(metadata, dict):
        metadata = getattr(run, "metadata", None) or {}
    if isinstance(metadata, dict):
        value = metadata.get("session_id") or metadata.get("thread_id")
        if value:
            return str(value)
    return None


def wait_for_session_trace(
    session_id: str,
    *,
    timeout_s: float = 45.0,
) -> Any:
    """Return the first LangSmith run whose metadata session_id matches."""
    from langsmith import Client

    flush_tracers()
    client = Client()
    project = os.environ.get("LANGSMITH_PROJECT", LANGSMITH_PROJECT) or "afvc"
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    filt = (
        'and(eq(metadata_key, "session_id"), '
        f'eq(metadata_value, "{session_id}"))'
    )
    while time.time() < deadline:
        try:
            matched = list(client.list_runs(project_name=project, filter=filt, limit=5))
            if matched:
                return matched[0]
        except Exception as exc:  # noqa: BLE001 — poll until timeout; filter syntax varies by SDK
            last_error = exc
        try:
            recent = list(client.list_runs(project_name=project, is_root=True, limit=40))
            for run in recent:
                if _run_session_id(run) == session_id:
                    return run
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1.5)
    raise TimeoutError(
        f"no LangSmith trace for session_id={session_id} in project={project}: {last_error}"
    )
