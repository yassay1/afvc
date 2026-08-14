"""工单数据概览用例。"""

from typing import Any

import polars as pl

from backend.infrastructure.workorders import (
    REQUIRED_COLUMNS,
    get_data_source_info,
    load_workorders,
)


def _get_unique_count(df: pl.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    return df[column].drop_nulls().n_unique()


def _get_top_counts(df: pl.DataFrame, column: str, top_n: int = 10) -> list[dict[str, Any]]:
    if column not in df.columns:
        return []

    result_df = (
        df
        .select(
            pl.col(column)
            .cast(pl.Utf8)
            .fill_null("未知")
            .str.strip_chars()
            .alias("name")
        )
        .with_columns(
            pl.when(pl.col("name") == "")
            .then(pl.lit("空值"))
            .otherwise(pl.col("name"))
            .alias("name")
        )
        .group_by("name")
        .len()
        .sort("len", descending=True)
        .head(top_n)
    )

    return [{"name": row["name"], "count": row["len"]} for row in result_df.to_dicts()]


def _format_time_value(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _get_time_range(df: pl.DataFrame, column: str = "current_faildate") -> dict[str, Any]:
    if column not in df.columns:
        return {
            "start_time": None,
            "end_time": None,
            "note": f"未找到时间字段 {column}",
        }

    try:
        time_df = (
            df
            .select(
                pl.col(column)
                .cast(pl.Utf8)
                .str.strip_chars()
                .str.to_datetime(strict=False)
                .alias("record_time")
            )
            .filter(pl.col("record_time").is_not_null())
        )

        if time_df.height == 0:
            return {
                "start_time": None,
                "end_time": None,
                "note": "时间字段存在，但未能成功解析为日期时间",
            }

        return {
            "start_time": _format_time_value(time_df["record_time"].min()),
            "end_time": _format_time_value(time_df["record_time"].max()),
            "note": "这里统计的是工单记录时间范围，不直接等同于真实物理故障发生时间",
        }
    except Exception as e:
        return {
            "start_time": None,
            "end_time": None,
            "note": f"时间范围解析失败：{str(e)}",
        }


def get_basic_data_info() -> dict[str, Any]:
    """返回当前工单数据的基础信息（运维面辅助，非八大诊断用例）。"""
    source = get_data_source_info()
    df = load_workorders()

    existing_columns = df.columns
    required_column_status = {
        column: column in existing_columns for column in REQUIRED_COLUMNS
    }
    missing_columns = [
        column for column, exists in required_column_status.items() if not exists
    ]

    return {
        "status": "success",
        "message": "工单数据读取成功",
        "current_file": source["current_file"],
        "file_path": source["file_path"],
        "data_backend": source.get("backend"),
        "row_count": df.height,
        "column_count": df.width,
        "columns": existing_columns,
        "required_column_status": required_column_status,
        "missing_columns": missing_columns,
        "note": "当前接口只用于确认数据是否能被系统读取，后续会继续实现数据概览、设备查询和风险预测。",
    }


def get_data_overview(top_n: int = 10) -> dict[str, Any]:
    """获取 AFC 工单数据概览统计信息。"""
    source = get_data_source_info()
    df = load_workorders()

    return {
        "status": "success",
        "message": "工单数据概览统计成功",
        "current_file": source["current_file"],
        "data_backend": source.get("backend"),
        "basic_metrics": {
            "workorder_count": df.height,
            "column_count": df.width,
            "device_count": _get_unique_count(df, "assetnum"),
            "station_count": _get_unique_count(df, "station_name"),
            "line_count": _get_unique_count(df, "cust_linenum"),
            "brand_count": _get_unique_count(df, "cust_brand"),
        },
        "time_range": _get_time_range(df, "current_faildate"),
        "brand_distribution": _get_top_counts(df, "cust_brand", top_n),
        "fault_description_top": _get_top_counts(df, "description", top_n),
        "line_distribution": _get_top_counts(df, "cust_linenum", top_n),
        "subsystem_distribution": _get_top_counts(df, "cust_subsys", top_n),
        "worktype_distribution": _get_top_counts(df, "worktype", top_n),
        "field_note": {
            "current_faildate": "本系统将 current_faildate 作为工单记录时间使用，不直接宣称其等同于真实物理故障发生时刻。",
            "description": "description 表示工单中的故障现象描述，后续维修建议只作为检查方向参考，不直接等同于真实根因。",
            "pre_type_and_pre_value": "pre_type / pre_value 缺失情况可能较多，第一版暂不作为核心预测标签。",
        },
    }
