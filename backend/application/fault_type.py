"""故障类型预测用例。"""

from typing import Any

from backend.domain.risk import (
    SUPPORTED_PREDICTION_WINDOWS,
    compute_estimated_occurrence_probability,
    get_risk_for_window,
)
from backend.infrastructure.fault_table import (
    get_fault_type_scores,
    has_fault_prediction_file,
)
from backend.schemas.fault_prediction import (
    FaultTypeScore,
    FaultTypePredictionResult,
)

DEFAULT_WINDOW_DAYS = 30
DEFAULT_TOP_K = 3

PREDICTION_STATEMENT = (
    "故障类型概率表示在预测窗口内发生故障时，"
    "各故障类别的相对可能性，不代表故障一定发生。"
)


def _normalize_conditional_probabilities(
    scores: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not scores:
        return scores

    total = sum(s["conditional_probability"] for s in scores)
    if total <= 0:
        return scores

    for s in scores:
        s["conditional_probability"] = round(s["conditional_probability"] / total, 4)

    return scores


def predict_fault_type(
    assetnum: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    """预测设备在指定时间窗口内最可能出现的故障类别。"""
    target_assetnum = assetnum.strip()
    if not target_assetnum:
        return {
            "status": "error",
            "message": "设备编号不能为空",
            "assetnum": "",
            "prediction_window_days": window_days,
            "overall_failure_risk": 0.0,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    if window_days not in SUPPORTED_PREDICTION_WINDOWS:
        return {
            "status": "error",
            "message": (
                f"不支持的预测窗口 {window_days} 天，"
                f"支持窗口：{list(SUPPORTED_PREDICTION_WINDOWS)}"
            ),
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": 0.0,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    try:
        from backend.application.risk import predict_device_risk

        risk_result = predict_device_risk(target_assetnum)
        if risk_result.get("status") != "success":
            return {
                "status": "error",
                "message": f"设备 {target_assetnum} 风险预测失败：{risk_result.get('message', '未知错误')}",
                "assetnum": target_assetnum,
                "prediction_window_days": window_days,
                "overall_failure_risk": 0.0,
                "most_likely_fault": None,
                "fault_type_predictions": [],
                "model_source": None,
                "model_version": None,
                "prediction_statement": PREDICTION_STATEMENT,
            }
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e),
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": 0.0,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"风险预测服务异常：{str(e)}",
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": 0.0,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    try:
        overall_failure_risk = get_risk_for_window(risk_result, window_days)
        if overall_failure_risk is None:
            return {
                "status": "error",
                "message": f"风险预测结果中未找到 {window_days} 天风险值",
                "assetnum": target_assetnum,
                "prediction_window_days": window_days,
                "overall_failure_risk": 0.0,
                "most_likely_fault": None,
                "fault_type_predictions": [],
                "model_source": None,
                "model_version": None,
                "prediction_statement": PREDICTION_STATEMENT,
            }
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e),
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": 0.0,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    if not has_fault_prediction_file():
        return {
            "status": "unavailable",
            "message": "当前暂无故障类型预测模型结果，系统仅支持风险预测。",
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": overall_failure_risk,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    try:
        scores = get_fault_type_scores(target_assetnum, window_days)
    except Exception as e:
        return {
            "status": "error",
            "message": f"故障类型预测数据读取异常：{str(e)}",
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": overall_failure_risk,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    if not scores:
        return {
            "status": "unavailable",
            "message": (
                f"设备 {target_assetnum} 在 {window_days} 天窗口下暂无故障类型预测结果。"
            ),
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": overall_failure_risk,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    scores = _normalize_conditional_probabilities(scores)

    model_version = None
    for s in scores:
        s["estimated_occurrence_probability"] = compute_estimated_occurrence_probability(
            overall_failure_risk=overall_failure_risk,
            conditional_probability=s["conditional_probability"],
        )
        if model_version is None:
            model_version = s.get("model_version")

    scores = scores[:top_k]

    fault_scores = []
    for s in scores:
        try:
            fs = FaultTypeScore(
                fault_code=s["fault_code"],
                fault_name=s["fault_name"],
                conditional_probability=s["conditional_probability"],
                estimated_occurrence_probability=s["estimated_occurrence_probability"],
            )
            fault_scores.append(fs)
        except ValueError:
            continue

    if not fault_scores:
        return {
            "status": "error",
            "message": "故障类型预测结果校验失败，无有效条目。",
            "assetnum": target_assetnum,
            "prediction_window_days": window_days,
            "overall_failure_risk": overall_failure_risk,
            "most_likely_fault": None,
            "fault_type_predictions": [],
            "model_source": None,
            "model_version": None,
            "prediction_statement": PREDICTION_STATEMENT,
        }

    most_likely = fault_scores[0]

    result = FaultTypePredictionResult(
        status="success",
        message="故障类型预测成功",
        assetnum=target_assetnum,
        prediction_window_days=window_days,
        overall_failure_risk=overall_failure_risk,
        most_likely_fault=most_likely,
        fault_type_predictions=fault_scores,
        model_source="fault_type_prediction_csv",
        model_version=model_version,
        prediction_statement=PREDICTION_STATEMENT,
    )

    return result.to_compat_dict()
