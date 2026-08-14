"""LangGraph 主图：model ⇄ tools，无 understand 节点。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from backend.agent.guardrails import SYSTEM_PROMPT
from backend.agent.runtime_context import thread_context
from backend.agent.state import AgentState
from backend.agent.tools import TOOL_TO_USE_CASE, build_exposed_tools
from backend.core.config import is_sql_backend, should_use_agent_graph
from backend.core.errors import LLMUnavailableError, is_llm_unavailable

logger = logging.getLogger("afvc.agent")

MAX_TOOL_ROUNDS = 8

_compiled = None


def _extract_assetnum(messages: list[BaseMessage]) -> str | None:
    for message in reversed(messages):
        tool_calls = getattr(message, "tool_calls", None) or []
        for call in tool_calls:
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {}) or {}
            assetnum = args.get("assetnum") if isinstance(args, dict) else None
            if assetnum:
                return str(assetnum).strip()
    return None


def _last_tool_name(messages: list[BaseMessage]) -> str | None:
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and getattr(message, "name", None):
            return str(message.name)
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            first = tool_calls[0]
            name = first.get("name") if isinstance(first, dict) else getattr(first, "name", None)
            if name:
                return str(name)
    return None


def tool_trace(messages: list[BaseMessage]) -> list[str]:
    names: list[str] = []
    for message in messages:
        if isinstance(message, ToolMessage) and getattr(message, "name", None):
            names.append(str(message.name))
            continue
        for call in getattr(message, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                names.append(str(name))
    # Prefer actual ToolMessage execution order when present.
    executed = [str(m.name) for m in messages if isinstance(m, ToolMessage) and getattr(m, "name", None)]
    return executed or names


def final_answer_from_state(state: dict[str, Any]) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            content = message.content
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict)
                ]
                text = "".join(parts).strip()
                if text:
                    return text
    return "我已经查询了相关能力，但这一轮没有生成完整文字答复。请再补充一下设备编号或你想看的具体内容。"


def last_use_case_from_state(state: dict[str, Any]) -> str | None:
    name = _last_tool_name(state.get("messages") or [])
    if not name:
        return None
    return TOOL_TO_USE_CASE.get(name, name)


def build_graph(*, llm: BaseChatModel, checkpointer=None, tools=None):
    """Compile the main agent graph. Checkpointer only on this outermost graph."""
    bound_tools = tools if tools is not None else build_exposed_tools()
    tool_node = ToolNode(bound_tools)

    def model_node(state: AgentState) -> dict[str, Any]:
        rounds = int(state.get("tool_rounds") or 0)
        messages = list(state.get("messages") or [])
        prompt_messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
        runnable = llm if rounds >= MAX_TOOL_ROUNDS else llm.bind_tools(bound_tools)
        try:
            response = runnable.invoke(prompt_messages)
        except Exception as exc:
            if is_llm_unavailable(exc):
                raise LLMUnavailableError(str(exc)) from exc
            raise
        return {"messages": [response]}

    def tools_node(state: AgentState) -> dict[str, Any]:
        output = tool_node.invoke(state)
        messages = list(state.get("messages") or []) + list(output.get("messages") or [])
        last_assetnum = state.get("last_assetnum") or _extract_assetnum(messages)
        return {
            "messages": output.get("messages") or [],
            "last_assetnum": last_assetnum,
            "tool_rounds": int(state.get("tool_rounds") or 0) + 1,
        }

    def route_after_model(state: AgentState) -> str:
        if int(state.get("tool_rounds") or 0) >= MAX_TOOL_ROUNDS:
            return END
        messages = state.get("messages") or []
        if not messages:
            return END
        last = messages[-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("model", model_node)
    builder.add_node("tools", tools_node)
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", route_after_model, {"tools": "tools", END: END})
    builder.add_edge("tools", "model")
    return builder.compile(checkpointer=checkpointer)


def get_compiled_graph(*, llm=None, checkpointer=None):
    """Process-wide compiled graph for the HTTP path."""
    global _compiled
    if llm is not None or checkpointer is not None:
        from backend.core.llm import get_agent_llm

        return build_graph(
            llm=llm or get_agent_llm(),
            checkpointer=checkpointer,
        )
    if _compiled is None:
        from backend.core.llm import get_agent_llm
        from langgraph.checkpoint.memory import MemorySaver

        saver = checkpointer
        if saver is None:
            if is_sql_backend():
                from backend.infrastructure.db import get_checkpointer

                saver = get_checkpointer()
            else:
                saver = MemorySaver()
        _compiled = build_graph(llm=get_agent_llm(), checkpointer=saver)
        logger.info("main agent graph compiled (checkpointer=%s)", type(saver).__name__)
    return _compiled


def invoke_main_agent(
    query: str,
    *,
    session_id: str,
    last_assetnum: str | None = None,
    graph=None,
) -> dict[str, Any]:
    compiled = graph or get_compiled_graph()
    with thread_context(session_id):
        try:
            result = compiled.invoke(
                {
                    "messages": [HumanMessage(content=query)],
                    "last_assetnum": last_assetnum,
                    "tool_rounds": 0,
                },
                config={
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 24,
                    "metadata": {"session_id": session_id},
                    "tags": ["afvc", "main-agent"],
                },
            )
        except Exception as exc:
            if is_llm_unavailable(exc):
                raise LLMUnavailableError(str(exc)) from exc
            raise
    messages = result.get("messages") or []
    assetnum = result.get("last_assetnum") or _extract_assetnum(messages)
    pending_actions = []
    if is_sql_backend():
        from backend.application.approvals import list_pending

        pending_actions = list_pending(session_id)
    return {
        "final_answer": final_answer_from_state(result),
        "last_assetnum": assetnum,
        "assetnum": assetnum,
        "use_case": last_use_case_from_state(result),
        "tool_trace": tool_trace(messages),
        "source": "agent_graph",
        "pending_actions": pending_actions,
    }


def append_resolution_notice(session_id: str, text: str) -> None:
    """Append an approval outcome to the conversation thread. Not Command(resume)."""
    compiled = get_compiled_graph()
    compiled.update_state(
        {"configurable": {"thread_id": session_id}},
        {"messages": [AIMessage(content=text)]},
    )


def reset_compiled_graph() -> None:
    global _compiled
    _compiled = None


def graph_is_active() -> bool:
    return should_use_agent_graph()
