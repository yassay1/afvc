"""Per-turn Agent runtime context. Not supplied by the model."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator

_current_thread_id: ContextVar[str | None] = ContextVar("afvc_thread_id", default=None)


def get_thread_id() -> str:
    thread_id = _current_thread_id.get()
    if not thread_id:
        raise RuntimeError("Agent 写工具缺少 thread_id 上下文")
    return thread_id


@contextmanager
def thread_context(thread_id: str) -> Iterator[None]:
    token = _current_thread_id.set(thread_id)
    try:
        yield
    finally:
        _current_thread_id.reset(token)
