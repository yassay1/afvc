"""Regenerate the committed, wholly fictional AFVC demo fixtures (v1)."""

from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend" / "data" / "mock"
NAMESPACE = uuid.UUID("ac7e2a13-21da-4a87-911b-13fae36ad001")
STATIONS = [
    ("星澜站", "D01", 0.92), ("云桥站", "D01", 0.74),
    ("青禾站", "D01", 0.63), ("北辰站", "D02", 0.96),
    ("松影站", "D02", 0.68), ("月港站", "D02", 0.81),
    ("晴川站", "D03", 0.88), ("锦湖站", "D03", 0.71),
    ("梧桐站", "D03", 0.59), ("晨光站", "D04", 0.77),
    ("远帆站", "D04", 0.84), ("银湾站", "D04", 0.66),
]
FAULTS = [
    ("暂停服务", "扇门驱动自检异常", "GATE_CONTROL"),
    ("暂停服务", "主控板通信超时", "COMMUNICATION"),
    ("卡票", "票卡回收模块卡滞", "TICKET_CARD"),
    ("暂停服务", "通行传感器响应间歇", "SERVICE_SUSPENDED"),
    ("死机", "显示控制模块重启", "SYSTEM"),
]
FAULT_NAMES = {
    "GATE_CONTROL": "通行控制或扇门异常", "COMMUNICATION": "通信异常",
    "TICKET_CARD": "票卡处理异常", "SERVICE_SUSPENDED": "设备暂停服务或服务中止",
    "SYSTEM": "主控、显示或系统运行异常",
}


def write_csv(name: str, columns: list[str], rows: list[dict]) -> None:
    with (ROOT / name).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate() -> None:
    workorders, predictions, fault_predictions, tasks = [], [], [], []
    base = datetime(2026, 10, 20, 8, 0)
    for index in range(1, 37):
        asset = f"DEMO-AGM-{index:03d}"
        station, line, _ = STATIONS[(index - 1) // 3]
        brand = ["虚构辰星", "虚构海岚", "虚构青岳"][index % 3]
        dates = [base - timedelta(days=7 * n + index % 5, hours=(index + n) % 9) for n in range(8)]
        for n, current in enumerate(dates):
            focus, detail, _ = FAULTS[(index + n) % len(FAULTS)]
            workorders.append({
                "assetnum": asset, "station_name": station, "cust_linenum": line,
                "current_faildate": current.strftime("%Y-%m-%d %H:%M:%S"),
                "prev_faildate": dates[n + 1].strftime("%Y-%m-%d %H:%M:%S") if n < 7 else "2026-08-01 08:00:00",
                "total_failure_count": str(12 - n + index % 5),
                "description": f"合成工单：{focus}，{detail}；现场复位并记录模拟观察值",
                "cust_brand": brand, "cust_subsys": "AFCAGM", "worktype": "CM",
                "pre_type": "故障", "pre_value": focus,
            })
        risk90 = round(0.36 + ((index * 13) % 52) / 100, 2)
        predictions.append({"assetnum": asset, **{
            f"risk_{days}d": f"{min(0.95, round(risk90 * factor, 2)):.2f}"
            for days, factor in [(7, .19), (14, .31), (21, .43), (30, .57), (60, .79), (90, 1)]
        }})
        primary = FAULTS[index % len(FAULTS)][2]
        others = [code for code in FAULT_NAMES if code != primary][:2]
        for window in (7, 30, 90):
            for code, probability in zip([primary, *others], (.55, .28, .17)):
                fault_predictions.append({
                    "assetnum": asset, "window_days": window, "fault_code": code,
                    "fault_name": FAULT_NAMES[code], "conditional_probability": probability,
                    "model_version": "synthetic-v1",
                })
        if index <= 18:
            status = ["planned", "in_progress", "done"][((index - 1) // 6)]
            task = {
                "id": str(uuid.uuid5(NAMESPACE, asset)), "assetnum": asset,
                "station_name": station, "fault_focus": "暂停服务",
                "priority": 10 + index * 3,
                "planned_date": (base + timedelta(days=index % 9 - 5)).date().isoformat(),
                "assignee_crew_id": f"DEMO-CREW-{(index % 4) + 1:02d}",
                "status": status, "suggestion_score": round(risk90 * .64 + .22, 3),
                "suggestion_reasons": ["合成风险输入", "模拟站点重要度", "模拟班组及备件资源"],
                "feedback_result": "完成模拟检修，扇门动作与通信自检通过" if status == "done" else None,
                "feedback_matched_fault": True if status == "done" else None,
                "feedback_followed_suggestion": True if status == "done" else None,
                "feedback_note": "合成执行反馈，仅用于演示" if status == "done" else None,
                "feedback_at": "2026-10-19T16:00:00+08:00" if status == "done" else None,
            }
            tasks.append(task)

    write_csv("workorders_demo.csv", list(workorders[0]), workorders)
    write_csv("prediction_results.csv", list(predictions[0]), predictions)
    write_csv("fault_prediction_results.csv", list(fault_predictions[0]), fault_predictions)
    write_csv("station_importance.csv", ["station_name", "importance", "note"], [
        {"station_name": name, "importance": f"{value:.2f}", "note": "虚构站点模拟权重"}
        for name, _, value in STATIONS
    ])
    write_csv("crew_availability.csv", ["crew_id", "crew_name", "available", "skill_tags", "note"], [
        {"crew_id": f"DEMO-CREW-{n:02d}", "crew_name": f"虚构检修{n}组",
         "available": "true" if n < 4 else "false", "skill_tags": "AFCAGM;暂停服务;卡票",
         "note": "合成排班，非真实人员"} for n in range(1, 5)
    ])
    write_csv("spare_parts.csv", ["part_code", "part_name", "stock_qty", "related_fault", "note"], [
        {"part_code": f"DEMO-PART-{n:02d}", "part_name": name, "stock_qty": qty,
         "related_fault": focus, "note": "合成库存，非真实备件"}
        for n, (name, qty, focus) in enumerate([
            ("虚构扇门驱动组件", 8, "暂停服务"), ("虚构主控电源模块", 5, "暂停服务"),
            ("虚构通行传感器", 11, "暂停服务"), ("虚构票卡回收模块", 3, "卡票"),
        ], 1)
    ])
    (ROOT / "maintenance_tasks_demo.json").write_text(
        json.dumps({"version": 1, "tasks": tasks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    generate()
