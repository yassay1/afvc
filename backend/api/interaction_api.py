"""Interaction HTTP API —— Task 2 占位；Task 3 实现 handle_turn。"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/interaction",
    tags=["对话交互"],
)


class TurnRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)


@router.post("/turn")
def interaction_turn(_body: TurnRequest):
    """POST /interaction/turn —— 暂未实现（Task 3）。"""
    raise HTTPException(
        status_code=501,
        detail="Interaction layer not implemented yet (Task 3)",
    )
