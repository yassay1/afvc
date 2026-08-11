"""Interaction handle_turn contract tests (LLM off)."""

from backend.interaction.service import handle_turn


def test_diagnose_intent_calls_usecase(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    out = handle_turn("帮我分析设备 1000029970", session_id="t1")
    assert out["status"] == "success"
    assert out["use_case"] == "diagnose_device"
    assert out["assetnum"] == "1000029970"
    assert "final_answer" in out and len(out["final_answer"]) > 0


def test_followup_uses_last_assetnum(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    handle_turn("帮我分析设备 1000029970", session_id="t2")
    out = handle_turn("那它风险高吗？", session_id="t2")
    assert out["assetnum"] == "1000029970"
    assert out["use_case"] == "predict_device_risk"


def test_missing_asset_clarifies(monkeypatch):
    monkeypatch.setenv("AFVC_USE_LLM", "false")
    out = handle_turn("帮我看看风险", session_id="t3")
    assert out["status"] == "clarified"
    assert out["result"] is None
