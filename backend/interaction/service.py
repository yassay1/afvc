"""Interaction 主入口 —— LLM+Graph 走 LangGraph；否则 understand 兜底。"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, TypedDict

from backend.application import usecases
from backend.core.config import should_use_agent_graph
from backend.core.errors import LLMUnavailableError
from backend.infrastructure import session_memory
from backend.interaction.narrate import (
    narrate,
    narrate_error,
    narrate_reply,
    narrate_static,
)

logger = logging.getLogger("afvc.interaction")


class InteractionResult(TypedDict):
    status: str
    use_case: str | None
    assetnum: str | None
    final_answer: str
    session_id: str
    last_assetnum: str | None
    result: dict | None
    pending_actions: list[dict]


class RunInProgressError(RuntimeError):
    def __init__(self, session_id: str):
        super().__init__(f"session {session_id} already has a running turn")
        self.session_id = session_id


_NEEDS_ASSET = {
    "get_device_history",
    "predict_device_risk",
    "advise_maintenance",
    "predict_fault_type",
    "diagnose_device",
}

_run_lock = threading.Lock()
_active_runs: set[str] = set()


def _invoke_usecase(
    use_case: str,
    *,
    assetnum: str | None,
    query: str,
    manual_query: str | None,
) -> dict[str, Any]:
    if use_case == "get_data_overview":
        return usecases.get_data_overview()
    if use_case == "list_high_risk_devices":
        return usecases.list_high_risk_devices()
    if use_case == "list_maintenance_suggestions":
        return usecases.list_maintenance_suggestions()
    if use_case == "list_maintenance_tasks":
        return usecases.list_maintenance_tasks()
    if use_case == "get_device_history":
        return usecases.get_device_history(assetnum=assetnum or "")
    if use_case == "predict_device_risk":
        return usecases.predict_device_risk(assetnum=assetnum or "")
    if use_case == "advise_maintenance":
        return usecases.advise_maintenance(assetnum=assetnum or "")
    if use_case == "predict_fault_type":
        return usecases.predict_fault_type(assetnum=assetnum or "")
    if use_case == "diagnose_device":
        return usecases.diagnose_device(assetnum=assetnum or "")
    if use_case == "search_manual":
        return usecases.search_manual(
            query=manual_query or query,
            assetnum=assetnum,
        )
    raise ValueError(f"unknown use case: {use_case}")


def _pack(
    *,
    status: str,
    session_id: str,
    final_answer: str,
    use_case: str | None = None,
    assetnum: str | None = None,
    last_assetnum: str | None = None,
    result: dict | None = None,
    pending_actions: list[dict] | None = None,
) -> InteractionResult:
    return {
        "status": status,
        "use_case": use_case,
        "assetnum": assetnum,
        "final_answer": final_answer,
        "session_id": session_id,
        "last_assetnum": last_assetnum,
        "result": result,
        "pending_actions": pending_actions or [],
    }


def _acquire_run(session_id: str) -> None:
    with _run_lock:
        if session_id in _active_runs:
            raise RunInProgressError(session_id)
        _active_runs.add(session_id)


def _release_run(session_id: str) -> None:
    with _run_lock:
        _active_runs.discard(session_id)


def handle_turn_legacy(query: str, session_id: str | None = None) -> InteractionResult:
    """LLM 关闭 / 图关闭 / 主图失败时的规则路由兜底。"""
    from backend.interaction.understand import understand

    sid = (session_id or "").strip() or str(uuid.uuid4())
    session = session_memory.get_or_create(sid)
    last_assetnum = session.get("last_assetnum")

    understanding = understand(query, last_assetnum=last_assetnum)
    kind = understanding["kind"]

    if kind == "clarified":
        answer = narrate_static("clarified")
        session_memory.update(
            sid,
            user_message=query,
            assistant_message=answer,
        )
        return _pack(
            status="clarified",
            session_id=sid,
            final_answer=answer,
            last_assetnum=last_assetnum,
            result=None,
        )

    if kind in {"chat", "capability", "explanation"}:
        answer = narrate_reply(kind, query)
        session_memory.update(
            sid,
            user_message=query,
            assistant_message=answer,
        )
        return _pack(
            status="success",
            session_id=sid,
            final_answer=answer,
            last_assetnum=last_assetnum,
            result=None,
        )

    if kind == "rejected":
        answer = narrate_static("rejected")
        session_memory.update(
            sid,
            user_message=query,
            assistant_message=answer,
        )
        return _pack(
            status="rejected",
            session_id=sid,
            final_answer=answer,
            last_assetnum=last_assetnum,
            result=None,
        )

    use_case = understanding["use_case"]
    assetnum = understanding["assetnum"]

    if use_case in _NEEDS_ASSET and not assetnum:
        answer = narrate_static("clarified")
        session_memory.update(
            sid,
            user_message=query,
            assistant_message=answer,
        )
        return _pack(
            status="clarified",
            session_id=sid,
            final_answer=answer,
            use_case=use_case,
            last_assetnum=last_assetnum,
            result=None,
        )

    try:
        result = _invoke_usecase(
            use_case or "",
            assetnum=assetnum,
            query=query,
            manual_query=understanding.get("manual_query"),
        )
        answer = narrate(use_case or "", result, query=query)
        status = "success"
    except Exception as exc:  # noqa: BLE001 — 对话层兜底，避免打断会话
        result = None
        answer = narrate_error(str(exc))
        status = "success"

    new_last = assetnum or last_assetnum
    session_memory.update(
        sid,
        last_assetnum=new_last,
        last_use_case=use_case,
        user_message=query,
        assistant_message=answer,
    )

    return _pack(
        status=status,
        session_id=sid,
        final_answer=answer,
        use_case=use_case,
        assetnum=assetnum,
        last_assetnum=new_last,
        result=result,
    )


def handle_turn_via_graph(query: str, session_id: str | None = None) -> InteractionResult:
    from backend.agent.graph import invoke_main_agent

    sid = (session_id or "").strip() or str(uuid.uuid4())
    session = session_memory.get_or_create(sid)
    last_assetnum = session.get("last_assetnum")
    graph_result = invoke_main_agent(
        query,
        session_id=sid,
        last_assetnum=last_assetnum,
    )
    answer = graph_result["final_answer"]
    new_last = graph_result.get("last_assetnum") or last_assetnum
    use_case = graph_result.get("use_case")
    session_memory.update(
        sid,
        last_assetnum=new_last,
        last_use_case=use_case,
        user_message=query,
        assistant_message=answer,
    )
    return _pack(
        status="success",
        session_id=sid,
        final_answer=answer,
        use_case=use_case,
        assetnum=graph_result.get("assetnum"),
        last_assetnum=new_last,
        result={
            "source": "agent_graph",
            "tool_trace": graph_result.get("tool_trace") or [],
        },
        pending_actions=graph_result.get("pending_actions") or [],
    )


def handle_turn(query: str, session_id: str | None = None) -> InteractionResult:
    """LLM+Graph 开启时走主图。仅供应商不可用才降级 understand；程序/DB/图错误直接失败。"""
    sid = (session_id or "").strip() or str(uuid.uuid4())
    _acquire_run(sid)
    try:
        if should_use_agent_graph():
            try:
                return handle_turn_via_graph(query, session_id=sid)
            except RunInProgressError:
                raise
            except LLMUnavailableError as exc:
                logger.warning("llm unavailable; falling back to understand: %s", exc)
                out = handle_turn_legacy(query, session_id=sid)
                degraded = dict(out.get("result") or {})
                degraded["source"] = "legacy_fallback"
                degraded["degraded"] = "llm_unavailable"
                out["result"] = degraded
                return out
            except Exception:
                logger.exception("agent graph failed; not falling back to understand")
                raise
        return handle_turn_legacy(query, session_id=sid)
    finally:
        _release_run(sid)


def _notify_thread(session_id: str, text: str) -> None:
    if not should_use_agent_graph():
        return
    try:
        from backend.agent.graph import append_resolution_notice

        append_resolution_notice(session_id, text)
    except Exception:
        logger.exception("failed to notify agent thread %s", session_id)


def approve_pending(session_id: str, action_id: str) -> InteractionResult:
    from backend.application.approvals import approve, list_pending

    result = approve(thread_id=session_id, action_id=action_id)
    if result.get("idempotent"):
        text = f"该写操作此前已执行，未重复写入：{result.get('summary')}"
    else:
        text = f"已批准并执行：{result.get('summary')}"
    _notify_thread(session_id, f"[审批结果] {text}")
    return _pack(
        status="success",
        session_id=session_id,
        final_answer=text,
        result={"source": "approval", "action": result},
        pending_actions=list_pending(session_id),
    )


def reject_pending(session_id: str, action_id: str) -> InteractionResult:
    from backend.application.approvals import list_pending, reject

    result = reject(thread_id=session_id, action_id=action_id)
    text = f"已拒绝写操作，不会执行：{result.get('summary')}"
    _notify_thread(session_id, f"[审批结果] {text}")
    return _pack(
        status="success",
        session_id=session_id,
        final_answer=text,
        result={"source": "approval", "action": result},
        pending_actions=list_pending(session_id),
    )
