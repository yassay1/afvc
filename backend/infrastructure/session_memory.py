"""进程内会话短记忆 —— session_id → messages / last_assetnum。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_SESSIONS: dict[str, dict[str, Any]] = {}


def _empty_session() -> dict[str, Any]:
    return {
        "messages": [],
        "last_assetnum": None,
        "last_use_case": None,
    }


def get_or_create(session_id: str) -> dict[str, Any]:
    """返回会话快照（拷贝）；不存在则创建。"""
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = _empty_session()
    return deepcopy(_SESSIONS[session_id])


def update(
    session_id: str,
    *,
    last_assetnum: str | None = None,
    last_use_case: str | None = None,
    user_message: str | None = None,
    assistant_message: str | None = None,
    max_messages: int = 20,
) -> dict[str, Any]:
    """更新会话字段并追加短对话历史。"""
    session = _SESSIONS.setdefault(session_id, _empty_session())

    if last_assetnum is not None:
        session["last_assetnum"] = last_assetnum
    if last_use_case is not None:
        session["last_use_case"] = last_use_case

    messages: list[dict[str, str]] = session.setdefault("messages", [])
    if user_message is not None:
        messages.append({"role": "user", "content": user_message})
    if assistant_message is not None:
        messages.append({"role": "assistant", "content": assistant_message})
    if len(messages) > max_messages:
        session["messages"] = messages[-max_messages:]

    return deepcopy(session)


def clear(session_id: str | None = None) -> None:
    """清空指定会话，或全部（测试用）。"""
    if session_id is None:
        _SESSIONS.clear()
        return
    _SESSIONS.pop(session_id, None)
