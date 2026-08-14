"""LangGraph 主图会话状态。只给最外层图挂 checkpointer。"""

from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    last_assetnum: NotRequired[str | None]
    tool_rounds: NotRequired[int]
