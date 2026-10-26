"""Interaction HTTP API —— turn / approve / reject."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import require_login
from backend.domain.pending_action import (
    ActionConflictError,
    ActionExecutionError,
    ActionNotFoundError,
)
from backend.interaction.service import (
    RunInProgressError,
    approve_pending,
    handle_turn,
    reject_pending,
)
from backend.application.approvals import list_pending

router = APIRouter(
    prefix="/interaction",
    tags=["对话交互"],
    dependencies=[Depends(require_login)],
)


class TurnRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)


class ApprovalRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    action_id: str = Field(..., min_length=1, max_length=64)


def _map_approval_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ActionNotFoundError):
        return HTTPException(
            status_code=404,
            detail={"code": "action_not_found", "message": str(exc), "action_id": exc.action_id},
        )
    if isinstance(exc, ActionConflictError):
        return HTTPException(
            status_code=409,
            detail={
                "code": "action_conflict",
                "message": str(exc),
                "action_id": exc.action_id,
                "status": exc.status,
            },
        )
    if isinstance(exc, ActionExecutionError):
        return HTTPException(
            status_code=409,
            detail={
                "code": "action_failed",
                "message": str(exc),
                "action_id": exc.action_id,
            },
        )
    return HTTPException(status_code=500, detail={"code": "internal_error", "message": str(exc)})


@router.post("/turn")
def interaction_turn(body: TurnRequest):
    """POST /interaction/turn —— 主路径为 LangGraph Agent；LLM 关闭时走规则兜底。"""
    try:
        return handle_turn(body.query, session_id=body.session_id)
    except RunInProgressError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "run_in_progress",
                "message": "当前会话仍有一轮对话在执行，请等待结束后再发送。",
                "session_id": exc.session_id,
            },
        ) from exc


@router.post("/approve")
def interaction_approve(body: ApprovalRequest):
    try:
        return approve_pending(body.session_id, body.action_id)
    except (ActionNotFoundError, ActionConflictError, ActionExecutionError) as exc:
        raise _map_approval_error(exc) from exc


@router.post("/reject")
def interaction_reject(body: ApprovalRequest):
    try:
        return reject_pending(body.session_id, body.action_id)
    except (ActionNotFoundError, ActionConflictError, ActionExecutionError) as exc:
        raise _map_approval_error(exc) from exc


@router.get("/sessions/{session_id}/pending")
def interaction_pending(session_id: str):
    return {"session_id": session_id, "pending_actions": list_pending(session_id)}
