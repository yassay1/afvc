"""数据域内部执行图：无 LLM，不解析用户意图。

capability 名由 Main Agent 已经选中的 Tool 传入，不是 op/use_case 语义路由。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.application import usecases


class DataState(TypedDict):
    capability: str
    args: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None


DATA_CAPABILITIES: dict[str, Callable[..., dict[str, Any]]] = {
    "get_overview": usecases.get_data_overview,
    "get_device_history": usecases.get_device_history,
}


def _execute(state: DataState) -> DataState:
    name = state.get("capability") or ""
    fn = DATA_CAPABILITIES.get(name)
    if fn is None:
        return {
            "capability": name,
            "args": state.get("args") or {},
            "result": None,
            "error": f"unknown data capability: {name}",
        }
    try:
        result = fn(**(state.get("args") or {}))
        return {
            "capability": name,
            "args": state.get("args") or {},
            "result": result,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 — 交给调用方的 Tool 层
        return {
            "capability": name,
            "args": state.get("args") or {},
            "result": None,
            "error": str(exc),
        }


def build_data_subgraph():
    builder = StateGraph(DataState)
    builder.add_node("execute", _execute)
    builder.add_edge(START, "execute")
    builder.add_edge("execute", END)
    return builder.compile()


data_subgraph = build_data_subgraph()


def invoke_data_capability(capability: str, **args: Any) -> dict[str, Any]:
    """Run one data capability. The name is chosen by the calling tool, not by NLP."""
    out = data_subgraph.invoke(
        {
            "capability": capability,
            "args": args,
            "result": None,
            "error": None,
        }
    )
    if out.get("error"):
        raise ValueError(out["error"])
    result = out.get("result")
    if result is None:
        raise ValueError(f"data capability {capability} returned no result")
    return result
