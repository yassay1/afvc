"""检修计划：创建、调整、反馈（独立于工单 HITL）。"""

from __future__ import annotations

from datetime import date
from typing import Any

from backend.domain.maintenance import DEFAULT_FAULT_FOCUS
from backend.infrastructure import maintenance_task_repo as repo


def create_maintenance_task(payload: dict[str, Any]) -> dict[str, Any]:
    assetnum = str(payload.get("assetnum") or "").strip()
    if not assetnum:
        raise ValueError("创建检修任务需要 assetnum")
    body = {
        "assetnum": assetnum,
        "station_name": payload.get("station_name"),
        "fault_focus": payload.get("fault_focus") or DEFAULT_FAULT_FOCUS,
        "priority": int(payload.get("priority") or 100),
        "planned_date": payload.get("planned_date") or date.today().isoformat(),
        "assignee_crew_id": payload.get("assignee_crew_id"),
        "status": payload.get("status") or "planned",
        "suggestion_score": payload.get("suggestion_score"),
        "suggestion_reasons": list(payload.get("suggestion_reasons") or payload.get("reasons") or []),
    }
    task = repo.create_task(body)
    return {"status": "success", "message": "检修任务已创建", "task": task}


def list_maintenance_tasks(*, status: str | None = None) -> dict[str, Any]:
    tasks = repo.list_tasks(status=status)
    return {
        "status": "success",
        "message": "检修任务列表",
        "tasks": tasks,
        "count": len(tasks),
    }


def get_maintenance_task(task_id: str) -> dict[str, Any]:
    task = repo.get_task(task_id)
    if task is None:
        raise ValueError(f"检修任务不存在：{task_id}")
    return {"status": "success", "task": task}


def adjust_maintenance_task(task_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    allowed = {"priority", "planned_date", "assignee_crew_id", "status"}
    clean = {k: v for k, v in patch.items() if k in allowed and v is not None}
    if not clean:
        raise ValueError("至少提供 priority / planned_date / assignee_crew_id / status 之一")
    task = repo.update_task(task_id, clean)
    return {"status": "success", "message": "检修任务已调整", "task": task}


def submit_maintenance_feedback(
    task_id: str,
    *,
    result: str,
    matched_fault: bool | None = None,
    followed_suggestion: bool | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    text = (result or "").strip()
    if not text:
        raise ValueError("反馈结果 result 不能为空")
    task = repo.record_feedback(
        task_id,
        result=text,
        matched_fault=matched_fault,
        followed_suggestion=followed_suggestion,
        note=note,
    )
    return {
        "status": "success",
        "message": "执行反馈已记录",
        "task": task,
        "proof_note": "可用于复盘：是否属目标故障类、是否按建议执行（不宣称降本减故）",
    }


def accept_suggestion_as_task(suggestion: dict[str, Any], *, priority: int | None = None) -> dict[str, Any]:
    """从建议行一键生成计划任务。"""
    return create_maintenance_task(
        {
            "assetnum": suggestion.get("assetnum"),
            "station_name": suggestion.get("station_name"),
            "fault_focus": suggestion.get("fault_focus") or DEFAULT_FAULT_FOCUS,
            "priority": priority if priority is not None else 10,
            "assignee_crew_id": suggestion.get("suggested_crew_id"),
            "suggestion_score": suggestion.get("score"),
            "suggestion_reasons": suggestion.get("reasons") or [],
        }
    )
