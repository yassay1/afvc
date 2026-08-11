"""Application use-case facade contract tests."""

from backend.application import usecases


def test_diagnose_device_returns_aggregated_sections():
    out = usecases.diagnose_device("1000029970")
    assert out["status"] == "success"
    assert "history_summary" in out or "device_profile" in out
    assert "risk_prediction" in out
    assert "maintenance_advice" in out


def test_overview_and_high_risk_smoke():
    overview = usecases.get_data_overview(top_n=5)
    assert overview["status"] in {"success", "ok"} or "basic_metrics" in overview
    assert isinstance(usecases.list_high_risk_devices(top_n=3), dict)


def test_usecases_facade_exports_eight_functions():
    names = [
        "get_data_overview",
        "list_high_risk_devices",
        "get_device_history",
        "predict_device_risk",
        "advise_maintenance",
        "search_manual",
        "predict_fault_type",
        "diagnose_device",
    ]
    for name in names:
        assert callable(getattr(usecases, name))
