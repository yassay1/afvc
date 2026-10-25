"""今日检修建议：确定性规则打分（不用 LLM/RAG 定序）。"""

from __future__ import annotations

from typing import Any

import polars as pl

from backend.application.risk import list_high_risk_devices, predict_device_risk
from backend.domain.maintenance import (
    DEFAULT_FAULT_FOCUS,
    compute_suggestion_score,
    fault_relevance_from_history,
    resource_factor,
)
from backend.infrastructure import maintenance_resources as resources
from backend.infrastructure.workorders import load_workorders


def list_maintenance_suggestions(
    *,
    top_n: int = 10,
    fault_focus: str = DEFAULT_FAULT_FOCUS,
) -> dict[str, Any]:
    """预测对齐设备 → 规则打分 → 有序建议清单 + reasons。"""
    focus = (fault_focus or DEFAULT_FAULT_FOCUS).strip() or DEFAULT_FAULT_FOCUS
    high = list_high_risk_devices(top_n=max(top_n * 3, top_n))
    devices = list(high.get("devices") or [])
    df = load_workorders()

    # 若高风险列表空，退化为工单中出现的设备
    if not devices and "assetnum" in df.columns:
        assetnums = (
            df.select(
                pl.col("assetnum").cast(pl.Utf8).fill_null("").str.strip_chars().alias("assetnum")
            )
            .filter(pl.col("assetnum") != "")
            .unique()
            .to_series()
            .to_list()
        )
        for assetnum in assetnums[: max(top_n * 3, top_n)]:
            try:
                prediction = predict_device_risk(assetnum)
            except Exception:
                continue
            devices.append(
                {
                    "assetnum": assetnum,
                    "station_name": prediction.get("station_name"),
                    "risk_90d": prediction.get("risk_90d"),
                    "risk_30d": prediction.get("risk_30d"),
                    "warning_level": prediction.get("warning_level"),
                }
            )

    suggestions: list[dict[str, Any]] = []
    for device in devices:
        assetnum = str(device.get("assetnum") or "").strip()
        if not assetnum:
            continue
        station = device.get("station_name")
        risk_90d = float(device.get("risk_90d") or 0.01)

        device_df = df
        if "assetnum" in df.columns:
            device_df = df.filter(
                pl.col("assetnum").cast(pl.Utf8).fill_null("").str.strip_chars() == assetnum
            )
        descriptions: list[str] = []
        if device_df.height and "description" in device_df.columns:
            descriptions = [
                str(x) for x in device_df["description"].to_list() if x is not None
            ]
            if station is None and "station_name" in device_df.columns:
                station = device_df["station_name"][0]

        fault_rel, fault_reason = fault_relevance_from_history(descriptions, focus)
        importance, importance_reason = resources.station_importance(
            str(station) if station is not None else None
        )
        crew_id, crew_ok, crew_reason = resources.pick_crew_for_fault(focus)
        spare_ok, spare_reason = resources.spare_in_stock_for_fault(focus)
        res_score, res_reasons = resource_factor(
            crew_available=crew_ok, spare_in_stock=spare_ok
        )
        score = compute_suggestion_score(
            risk_90d=risk_90d,
            station_importance=importance,
            fault_relevance=fault_rel,
            resource=res_score,
        )
        reasons = [
            f"90 日复发风险 {risk_90d}",
            importance_reason,
            fault_reason,
            crew_reason,
            spare_reason,
            *res_reasons,
        ]
        suggestions.append(
            {
                "assetnum": assetnum,
                "station_name": station,
                "fault_focus": focus,
                "risk_90d": risk_90d,
                "risk_30d": device.get("risk_30d"),
                "warning_level": device.get("warning_level"),
                "station_importance": importance,
                "fault_relevance": fault_rel,
                "resource_factor": res_score,
                "suggested_crew_id": crew_id,
                "score": score,
                "reasons": reasons,
                "data_note": "人员/备件/站点重要度为模拟表，非真实排班或库存系统",
            }
        )

    suggestions.sort(key=lambda row: row["score"], reverse=True)
    suggestions = suggestions[:top_n]
    return {
        "status": "success",
        "message": "今日检修建议生成成功",
        "fault_focus": focus,
        "top_n": top_n,
        "suggestions": suggestions,
        "ranking_method": "deterministic_weighted_rules",
        "prediction_tier": high.get("prediction_tier"),
        "model_note": (
            "排序由确定性规则完成，不使用 LLM/RAG 决定优先级。"
            + (f" 风险输入：{high.get('model_note')}" if high.get("model_note") else "")
        ),
    }
