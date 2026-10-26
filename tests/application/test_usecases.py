"""Application use-case facade contract tests."""

from backend.application import usecases


def _known_assetnum() -> str:
    from backend.application.history import get_device_list

    rows = get_device_list()["devices"]
    assert rows
    for row in rows:
        asset = str(row.get("assetnum") or "")
        if asset.startswith("DEMO-"):
            return asset
    return str(rows[0]["assetnum"])


def test_diagnose_device_returns_aggregated_sections():
    out = usecases.diagnose_device(_known_assetnum())
    assert out["status"] == "success"
    assert "history_summary" in out or "device_profile" in out
    assert "risk_prediction" in out
    assert "maintenance_advice" in out


def test_overview_and_high_risk_smoke():
    overview = usecases.get_data_overview(top_n=5)
    assert overview["status"] in {"success", "ok"} or "basic_metrics" in overview
    high = usecases.list_high_risk_devices(top_n=3)
    assert isinstance(high, dict)
    assert high.get("devices")


def test_maintenance_suggestions_smoke():
    out = usecases.list_maintenance_suggestions(top_n=5, fault_focus="暂停服务")
    assert out["status"] == "success"
    assert out["suggestions"]
    assert out["ranking_method"] == "deterministic_weighted_rules"


def test_usecases_facade_exports_core_functions():
    names = [
        "get_data_overview",
        "list_high_risk_devices",
        "list_maintenance_suggestions",
        "list_maintenance_tasks",
        "create_maintenance_task",
        "adjust_maintenance_task",
        "submit_maintenance_feedback",
        "get_device_history",
        "get_device_list",
        "predict_device_risk",
        "advise_maintenance",
        "search_manual",
        "predict_fault_type",
        "diagnose_device",
    ]
    for name in names:
        assert callable(getattr(usecases, name))
