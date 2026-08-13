"""Interaction 主入口 —— understand → clarify → usecase → narrate。"""

from __future__ import annotations

import uuid
from typing import Any, TypedDict

from backend.application import usecases
from backend.infrastructure import session_memory
from backend.interaction.narrate import narrate, narrate_error, narrate_static
from backend.interaction.understand import understand


class InteractionResult(TypedDict):
    status: str
    use_case: str | None
    assetnum: str | None
    final_answer: str
    session_id: str
    last_assetnum: str | None
    result: dict | None


_NEEDS_ASSET = {
    "get_device_history",
    "predict_device_risk",
    "advise_maintenance",
    "predict_fault_type",
    "diagnose_device",
}


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
) -> InteractionResult:
    return {
        "status": status,
        "use_case": use_case,
        "assetnum": assetnum,
        "final_answer": final_answer,
        "session_id": session_id,
        "last_assetnum": last_assetnum,
        "result": result,
    }


def handle_turn(query: str, session_id: str | None = None) -> InteractionResult:
    """薄对话一轮：理解 →（必要时澄清）→ 调用一个用例 → 叙述。"""
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
        answer = narrate_static(kind)
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
