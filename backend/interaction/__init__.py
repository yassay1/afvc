"""Interaction layer — LLM+Graph 走主图；否则 understand → 用例 → 叙述。"""

from backend.interaction.service import InteractionResult, handle_turn

__all__ = ["InteractionResult", "handle_turn"]
