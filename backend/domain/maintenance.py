"""检修闭环纯规则：打分权重、故障焦点、任务状态。"""

from __future__ import annotations

from typing import Any, Final

# V1 默认故障焦点（见 docs/DATA.md）
DEFAULT_FAULT_FOCUS: Final[str] = "暂停服务"

TASK_STATUSES: Final[frozenset[str]] = frozenset(
    {"planned", "in_progress", "done", "cancelled"}
)


class MaintenanceTaskTransitionError(ValueError):
    """任务状态变更缺少必要的现场反馈。"""


class MaintenanceTaskValidationError(ValueError):
    """检修任务字段未通过业务校验。"""


# score = w_risk * risk_90d + w_importance * station_importance
#       + w_fault * fault_relevance + w_resource * resource_factor
WEIGHT_RISK: Final[float] = 0.45
WEIGHT_IMPORTANCE: Final[float] = 0.25
WEIGHT_FAULT: Final[float] = 0.20
WEIGHT_RESOURCE: Final[float] = 0.10


def fault_relevance_from_history(
    descriptions: list[str],
    fault_focus: str = DEFAULT_FAULT_FOCUS,
) -> tuple[float, str]:
    """根据工单描述中故障焦点出现比例给出 0～1 相关度。"""
    focus = (fault_focus or DEFAULT_FAULT_FOCUS).strip()
    if not descriptions:
        return 0.0, f"无历史描述，与「{focus}」相关度按 0"
    hits = sum(1 for text in descriptions if focus in (text or ""))
    ratio = hits / len(descriptions)
    return round(ratio, 2), f"近史 {hits}/{len(descriptions)} 条含「{focus}」"


def resource_factor(
    *,
    crew_available: bool,
    spare_in_stock: bool,
) -> tuple[float, list[str]]:
    """人员与备件模拟约束 → 0～1 因子与理由。"""
    reasons: list[str] = []
    score = 0.0
    if crew_available:
        score += 0.6
        reasons.append("有可用检修班组（模拟）")
    else:
        reasons.append("无可用检修班组（模拟）")
    if spare_in_stock:
        score += 0.4
        reasons.append("相关备件有库存（模拟）")
    else:
        reasons.append("相关备件缺货或未配置（模拟）")
    return round(score, 2), reasons


def compute_suggestion_score(
    *,
    risk_90d: float,
    station_importance: float,
    fault_relevance: float,
    resource: float,
) -> float:
    raw = (
        WEIGHT_RISK * risk_90d
        + WEIGHT_IMPORTANCE * station_importance
        + WEIGHT_FAULT * fault_relevance
        + WEIGHT_RESOURCE * resource
    )
    return round(max(0.0, min(1.0, raw)), 4)


def validate_task_status(status: str) -> str:
    value = (status or "").strip().lower()
    if value not in TASK_STATUSES:
        raise ValueError(f"无效任务状态：{status}，允许：{sorted(TASK_STATUSES)}")
    return value


def task_public_dict(row: dict[str, Any]) -> dict[str, Any]:
    """规范化对外字段。"""
    reasons = row.get("suggestion_reasons") or []
    if isinstance(reasons, str):
        import json

        try:
            reasons = json.loads(reasons)
        except json.JSONDecodeError:
            reasons = [reasons]
    return {
        "id": str(row.get("id")),
        "assetnum": row.get("assetnum"),
        "station_name": row.get("station_name"),
        "fault_focus": row.get("fault_focus") or DEFAULT_FAULT_FOCUS,
        "priority": int(row.get("priority") or 100),
        "planned_date": str(row["planned_date"]) if row.get("planned_date") else None,
        "assignee_crew_id": row.get("assignee_crew_id"),
        "status": row.get("status") or "planned",
        "suggestion_score": row.get("suggestion_score"),
        "suggestion_reasons": reasons,
        "feedback_result": row.get("feedback_result"),
        "feedback_matched_fault": row.get("feedback_matched_fault"),
        "feedback_followed_suggestion": row.get("feedback_followed_suggestion"),
        "feedback_note": row.get("feedback_note"),
        "feedback_at": str(row["feedback_at"]) if row.get("feedback_at") else None,
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
    }
