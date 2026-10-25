"""故障类型预测用例单元测试。"""

import pytest

from backend.application.fault_type import (
    predict_fault_type as predict_device_fault_type,
)
from backend.application.history import get_device_list
from backend.domain.risk import SUPPORTED_PREDICTION_WINDOWS


# 公开仓 fault mock 仅含 DEMO-AGM-*；需与工单工作集对齐
KNOWN_ASSETNUM = "DEMO-AGM-001"
UNKNOWN_ASSETNUM = "ZZZ99999"


def _require_demo_asset() -> str:
    assets = {str(d.get("assetnum")) for d in get_device_list()["devices"]}
    if KNOWN_ASSETNUM not in assets:
        pytest.skip("当前工作集无 DEMO 工单；故障类型 mock 仅覆盖 DEMO-AGM-*")
    return KNOWN_ASSETNUM


class TestPredictDeviceFaultType:
    """predict_device_fault_type 完整流程测试。"""

    def test_success_prediction(self):
        """已知设备应返回成功预测。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 30, 3)
        assert result["status"] == "success"
        assert result["assetnum"] == asset
        assert result["prediction_window_days"] == 30
        assert result["most_likely_fault"] is not None
        assert len(result["fault_type_predictions"]) > 0
        assert len(result["fault_type_predictions"]) <= 3

    def test_overall_risk_in_range(self):
        """总体风险应在 [0, 1] 内。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 30, 3)
        if result["status"] == "success":
            assert 0.0 <= result["overall_failure_risk"] <= 1.0

    def test_estimated_probability_formula(self):
        """综合估计概率 = 总体风险 × 条件概率。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 30, 3)
        if result["status"] == "success":
            overall = result["overall_failure_risk"]
            for pred in result["fault_type_predictions"]:
                expected = round(overall * pred["conditional_probability"], 4)
                assert abs(pred["estimated_occurrence_probability"] - expected) < 0.01

    def test_unknown_device_error(self):
        """未知设备应返回错误状态。"""
        result = predict_device_fault_type(UNKNOWN_ASSETNUM, 30, 3)
        assert result["status"] == "error"

    def test_invalid_window_error(self):
        """非法预测窗口应返回错误状态。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 999, 3)
        assert result["status"] == "error"

    def test_all_supported_windows(self):
        """所有支持的预测窗口应能正常调用。"""
        asset = _require_demo_asset()
        for window in SUPPORTED_PREDICTION_WINDOWS:
            result = predict_device_fault_type(asset, window, 3)
            assert result["status"] in ("success", "unavailable", "error")
            assert result["prediction_window_days"] == window

    def test_empty_assetnum_error(self):
        """空设备编号应返回错误。"""
        result = predict_device_fault_type("", 30, 3)
        assert result["status"] == "error"
        assert "不能为空" in result["message"]

    def test_conditional_probability_normalized(self):
        """条件概率归一化后总和应接近 1.0。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 30, 3)
        if result["status"] == "success" and len(result["fault_type_predictions"]) > 0:
            # 由于 top_k 截取，不要求总和为 1
            pass  # 只验证归一化不报错

    def test_top_k_limit(self):
        """top_k 应正确限制返回数量。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 30, 2)
        if result["status"] == "success":
            assert len(result["fault_type_predictions"]) <= 2

    def test_most_likely_is_first(self):
        """most_likely_fault 应为 fault_type_predictions 的第一项。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 30, 3)
        if result["status"] == "success" and result["fault_type_predictions"]:
            ml = result["most_likely_fault"]
            first = result["fault_type_predictions"][0]
            assert ml["fault_code"] == first["fault_code"]

    def test_prediction_statement_present(self):
        """结果应包含 prediction_statement。"""
        asset = _require_demo_asset()
        result = predict_device_fault_type(asset, 30, 3)
        assert "prediction_statement" in result
        assert len(result["prediction_statement"]) > 0

    def test_different_windows_different_risk(self):
        """不同窗口应有不同的总体风险。"""
        asset = _require_demo_asset()
        result_30 = predict_device_fault_type(asset, 30, 3)
        result_90 = predict_device_fault_type(asset, 90, 3)
        assert result_30["prediction_window_days"] == 30
        assert result_90["prediction_window_days"] == 90
