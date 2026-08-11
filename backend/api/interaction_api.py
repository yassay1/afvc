"""Interaction HTTP API —— POST /interaction/turn → handle_turn。"""

from pydantic import BaseModel, Field
from fastapi import APIRouter

from backend.interaction.service import handle_turn

router = APIRouter(
    prefix="/interaction",
    tags=["对话交互"],
)


class TurnRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)


@router.post("/turn")
def interaction_turn(body: TurnRequest):
    """POST /interaction/turn —— 薄 Interaction 一轮对话。"""
    return handle_turn(body.query, session_id=body.session_id)
