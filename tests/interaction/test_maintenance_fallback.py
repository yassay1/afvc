"""规则兜底可走到维修作业只读用例（不经 Agent 图）。"""

from __future__ import annotations

from backend.interaction.service import handle_turn_legacy
from backend.interaction.understand import understand
from backend.interaction.narrate import narrate_maintenance_suggestions, narrate_overview


def test_understand_routes_today_plan_to_suggestions():
    u = understand("今天优先修哪些闸机？")
    assert u["kind"] == "usecase"
    assert u["use_case"] == "list_maintenance_suggestions"
    assert u["needs_asset"] is False


def test_understand_routes_user_facing_recommendation_wording():
    u = understand("哪些设备建议优先检修？")
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
    assert "检修建议" in out["final_answer"]
    assert "按服务端提供的顺序列出" in out["final_answer"]
    assert "prediction_results.csv" not in out["final_answer"]


def test_suggestion_narration_uses_field_language_and_preserves_source_context():
    answer = narrate_maintenance_suggestions({
        "fault_focus": "暂停服务",
        "model_note": "风险输入：prediction_results.csv",
        "suggestions": [{
            "assetnum": "DEMO-AGM-018",
            "station_name": "北辰站",
            "reasons": [
                "90 日复发风险 0.75",
                "站点重要度 0.96（虚构站点模拟权重）",
                "近史 5/8 条含「暂停服务」",
            ],
            "data_note": "人员/备件/站点重要度为模拟表",
        }],
    })
    assert "未来 90 天内再次出现故障工单的风险参考值为 75%" in answer
    assert "近 8 条相关工单中，有 5 条记录了“暂停服务”现象" in answer
    assert "体验数据" in answer
    assert "prediction_results.csv" not in answer
    assert "虚构站点模拟权重" not in answer
    assert "LLM" not in answer and "RAG" not in answer
    assert "接口未提供该数据的更新时间" in answer


def test_overview_narration_does_not_expose_filename_and_admits_missing_freshness():
    answer = narrate_overview({
        "data_backend": "file",
        "current_file": "workorders_demo.csv",
        "basic_metrics": {},
        "time_range": {},
    })
    assert "当前接入的工单文件" in answer
    assert "接口未提供数据更新时间" in answer
    assert "workorders_demo.csv" not in answer
