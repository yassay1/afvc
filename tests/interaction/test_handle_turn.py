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


def test_switch_device_preserves_hyphenated_assetnum():
    from backend.interaction.understand import understand

    out = understand("切换到设备 DEMO-AGM-019 看风险")
    assert out["assetnum"] == "DEMO-AGM-019"
    assert out["use_case"] == "predict_device_risk"


def test_generic_english_text_is_not_treated_as_an_assetnum():
    from backend.interaction.understand import understand

    assert understand("Please explain the general risk")["assetnum"] is None


def test_usecase_failure_is_not_reported_as_success(monkeypatch):
    from backend.interaction import service

    monkeypatch.setenv("AFVC_USE_LLM", "false")

    def fail_usecase(*args, **kwargs):
        raise LookupError("未找到设备 DEMO-AGM-019")

    monkeypatch.setattr(service, "_invoke_usecase", fail_usecase)
    out = service.handle_turn(
        "关于设备 DEMO-AGM-019：分析这台设备的工单复发风险",
        session_id="t5",
    )
    assert out["status"] == "error"
    assert out["assetnum"] == "DEMO-AGM-019"
    assert out["result"] is None
    assert "处理失败" in out["final_answer"]
