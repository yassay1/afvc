"""V1 模拟资源表：站点重要度、班组、备件（明确标注非真实系统）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

MOCK_DIR = Path(__file__).resolve().parent.parent / "data" / "mock"


def _read_csv(name: str) -> pl.DataFrame:
    path = MOCK_DIR / name
    if not path.exists():
        return pl.DataFrame()
    return pl.read_csv(path)


def station_importance(station_name: str | None) -> tuple[float, str]:
    name = (station_name or "").strip()
    df = _read_csv("station_importance.csv")
    if df.height == 0 or not name:
        return 0.5, "站点重要度缺省 0.5（模拟表无匹配）"
    hit = df.filter(pl.col("station_name").cast(pl.Utf8).str.strip_chars() == name)
    if hit.height == 0:
        return 0.5, f"站点「{name}」未在模拟重要度表，缺省 0.5"
    row = hit.head(1).to_dicts()[0]
    value = float(row.get("importance") or 0.5)
    note = row.get("note") or "模拟站点重要度"
    return value, f"站点重要度 {value}（{note}）"


def list_available_crews() -> list[dict[str, Any]]:
    df = _read_csv("crew_availability.csv")
    if df.height == 0:
        return []
    rows = []
    for row in df.to_dicts():
        available = str(row.get("available", "")).strip().lower() in {"true", "1", "yes"}
        if available:
            rows.append(row)
    return rows


def pick_crew_for_fault(fault_focus: str) -> tuple[str | None, bool, str]:
    crews = list_available_crews()
    if not crews:
        return None, False, "模拟班组表为空或均不可用"
    focus = (fault_focus or "").strip()
    for crew in crews:
        tags = str(crew.get("skill_tags") or "")
        if focus and focus in tags:
            return (
                str(crew.get("crew_id")),
                True,
                f"匹配班组 {crew.get('crew_name')}（{crew.get('note')}）",
            )
    crew = crews[0]
    return (
        str(crew.get("crew_id")),
        True,
        f"选用可用班组 {crew.get('crew_name')}（{crew.get('note')}）",
    )


def spare_in_stock_for_fault(fault_focus: str) -> tuple[bool, str]:
    df = _read_csv("spare_parts.csv")
    if df.height == 0:
        return False, "模拟备件表为空"
    focus = (fault_focus or "").strip()
    related = df.filter(pl.col("related_fault").cast(pl.Utf8).str.strip_chars() == focus)
    if related.height == 0:
        return False, f"无与「{focus}」相关的模拟备件行"
    for row in related.to_dicts():
        qty = int(float(row.get("stock_qty") or 0))
        if qty > 0:
            return True, f"备件 {row.get('part_name')} 库存 {qty}（{row.get('note')}）"
    return False, f"与「{focus}」相关的模拟备件均缺货"
