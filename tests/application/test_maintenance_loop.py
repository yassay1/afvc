"""检修闭环：建议 → 计划 → 反馈。"""

from backend.application import usecases
from backend.domain.maintenance import compute_suggestion_score


def test_score_weights_are_bounded():
    score = compute_suggestion_score(
        risk_90d=0.9,
        station_importance=1.0,
        fault_relevance=1.0,
        resource=1.0,
    )
    assert 0.0 <= score <= 1.0


def test_suggestion_to_task_to_feedback():
    suggestions = usecases.list_maintenance_suggestions(top_n=3, fault_focus="暂停服务")
    assert suggestions["suggestions"]
    top = suggestions["suggestions"][0]

    created = usecases.accept_suggestion_as_task(top, priority=1)
    assert created["status"] == "success"
    task_id = created["task"]["id"]

    adjusted = usecases.adjust_maintenance_task(
        task_id,
        {"priority": 2, "status": "in_progress"},
    )
    assert adjusted["task"]["priority"] == 2
    assert adjusted["task"]["status"] == "in_progress"

    feedback = usecases.submit_maintenance_feedback(
        task_id,
        result="已现场检查，确认为暂停服务相关",
        matched_fault=True,
        followed_suggestion=True,
        note="DEMO 闭环验收",
    )
    assert feedback["task"]["status"] == "done"
    assert feedback["task"]["feedback_result"]

    listed = usecases.list_maintenance_tasks(status="done")
    assert any(t["id"] == task_id for t in listed["tasks"])
