"""Repeatable Agent eval cases. Live tests parametrize these; default pytest skips them."""

from __future__ import annotations

from dataclasses import dataclass

from tests.agent.live import KNOWN_ASSETNUM, WRITE_TOOLS


@dataclass(frozen=True)
class EvalCase:
    id: str
    query: str
    require_plans: tuple[frozenset[str], ...] = ()
    forbid_tools: frozenset[str] = WRITE_TOOLS
    answer_any: tuple[str, ...] = ()
    answer_none: tuple[str, ...] = ()
    no_pending: bool = False


def plan_satisfied(trace: list[str], plans: tuple[frozenset[str], ...]) -> bool:
    """True if any required plan is a subset of the actual tool trace."""
    if not plans:
        return True
    actual = set(trace)
    return any(plan <= actual for plan in plans)


SINGLE_TURN_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="overview",
        query="现在工单数据整体情况怎么样？给我概览即可，不用点某一台设备。",
        require_plans=(frozenset({"get_overview"}),),
    ),
    EvalCase(
        id="clarify-missing-asset",
        query="这台设备最近老出问题，帮我看看怎么回事。",
        answer_any=("编号", "assetnum", "设备号", "资产"),
        no_pending=True,
    ),
    EvalCase(
        id="history-and-risk",
        query=(
            f"看看设备 {KNOWN_ASSETNUM} 最近为什么老出问题，"
            "再判断一下后续风险。"
        ),
        require_plans=(
            frozenset({"get_device_history", "predict_device_risk"}),
            frozenset({"diagnose_device"}),
        ),
        answer_any=("风险",),
        answer_none=("一定会坏",),
    ),
    EvalCase(
        id="high-risk-list",
        query="现在哪些设备复发风险比较高，给我看看优先巡检名单。",
        require_plans=(frozenset({"list_high_risk"}),),
    ),
)
