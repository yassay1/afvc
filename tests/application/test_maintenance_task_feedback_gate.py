import pytest

from backend.application import maintenance_tasks
from backend.domain.maintenance import MaintenanceTaskTransitionError, MaintenanceTaskValidationError


def test_task_cannot_be_created_as_done_without_feedback(monkeypatch):
    called = False

    def create_task(_payload):
        nonlocal called
        called = True
        raise AssertionError("repository should not be called")

    monkeypatch.setattr(maintenance_tasks.repo, "create_task", create_task)
    with pytest.raises(MaintenanceTaskTransitionError, match="提交现场执行反馈"):
        maintenance_tasks.create_maintenance_task({"assetnum": "DEMO-AGM-001", "status": "done"})
    assert not called


def test_task_cannot_be_changed_to_done_without_feedback(monkeypatch):
    current = {"id": "task-1", "status": "in_progress", "feedback_result": None}
    updated = False

    monkeypatch.setattr(maintenance_tasks.repo, "get_task", lambda _task_id: current)

    def update_task(*_args, **_kwargs):
        nonlocal updated
        updated = True
        raise AssertionError("repository should not be updated")

    monkeypatch.setattr(maintenance_tasks.repo, "update_task", update_task)
    with pytest.raises(MaintenanceTaskTransitionError, match="提交现场执行反馈"):
        maintenance_tasks.adjust_maintenance_task("task-1", {"status": "DONE"})
    assert not updated


def test_submitted_feedback_is_the_completion_transition(monkeypatch):
    updated_patch = None

    def update_task(_task_id, patch):
        nonlocal updated_patch
        updated_patch = patch
        return {"id": "task-1", "status": patch["status"], "feedback_result": patch["feedback_result"]}

    monkeypatch.setattr(maintenance_tasks.repo, "update_task", update_task)
    response = maintenance_tasks.submit_maintenance_feedback("task-1", result="现场已修复")
    assert updated_patch == {
        "status": "done",
        "feedback_result": "现场已修复",
        "feedback_matched_fault": None,
        "feedback_followed_suggestion": None,
        "feedback_note": None,
        "feedback_at": updated_patch["feedback_at"],
    }
    assert response["task"]["status"] == "done"
    assert response["task"]["feedback_result"] == "现场已修复"


@pytest.mark.parametrize("priority", [0, -1, 1.5, True])
def test_create_rejects_nonpositive_priority_before_repository_write(monkeypatch, priority):
    def unexpected_write(*_args, **_kwargs):
        raise AssertionError("invalid priority must be rejected before repository write")

    monkeypatch.setattr(maintenance_tasks.repo, "create_task", unexpected_write)
    with pytest.raises(MaintenanceTaskValidationError, match="priority 必须为大于 0 的整数"):
        maintenance_tasks.create_maintenance_task({"assetnum": "DEMO-AGM-001", "priority": priority})


def test_adjust_rejects_nonpositive_priority_before_repository_write(monkeypatch):
    monkeypatch.setattr(maintenance_tasks.repo, "get_task", lambda _task_id: {"id": "task-1", "status": "planned"})

    def unexpected_write(*_args, **_kwargs):
        raise AssertionError("invalid priority must be rejected before repository write")

    monkeypatch.setattr(maintenance_tasks.repo, "update_task", unexpected_write)
    with pytest.raises(MaintenanceTaskValidationError, match="priority 必须为大于 0 的整数"):
        maintenance_tasks.adjust_maintenance_task("task-1", {"priority": 0})


def test_blank_feedback_is_validation_error_before_repository_write(monkeypatch):
    def unexpected_write(*_args, **_kwargs):
        raise AssertionError("blank feedback must be rejected before repository write")

    monkeypatch.setattr(maintenance_tasks.repo, "record_feedback", unexpected_write)
    with pytest.raises(MaintenanceTaskValidationError, match="反馈结果 result 不能为空"):
        maintenance_tasks.submit_maintenance_feedback("task-1", result="   ")
