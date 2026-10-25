"""规则兜底可走到维修作业只读用例（不经 Agent 图）。"""

from __future__ import annotations

from backend.interaction.service import handle_turn_legacy
from backend.interaction.understand import understand


def test_understand_routes_today_plan_to_suggestions():
    u = understand("今天优先修哪些闸机？")
    assert u["kind"] == "usecase"
    assert u["use_case"] == "list_maintenance_suggestions"
    assert u["needs_asset"] is False


def test_understand_routes_task_list():
    u = understand("当前有哪些检修任务？")
    assert u["kind"] == "usecase"
    assert u["use_case"] == "list_maintenance_tasks"


def test_legacy_turn_narrates_suggestions(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    out = handle_turn_legacy("今日检修建议给我看看", session_id="fallback-maint-sug")
    assert out["status"] == "success"
    assert out["use_case"] == "list_maintenance_suggestions"
    assert out["result"] is not None
    assert out["result"].get("suggestions") is not None
    assert "今日检修建议" in out["final_answer"]
    assert "deterministic" in out["final_answer"] or "排序" in out["final_answer"]
