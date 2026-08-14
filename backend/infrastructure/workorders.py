"""工单文件定位、Excel/CSV 解析，以及当前工作集加载。

查询真相默认是 Postgres。Excel 只用于 import。
紧急回退：AFVC_DATA_BACKEND=file 时读 backend/data/raw 最新文件。
"""

from pathlib import Path

import polars as pl

from backend.core.config import is_sql_backend


RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

REQUIRED_COLUMNS = [
    "assetnum",
    "station_name",
    "cust_linenum",
    "current_faildate",
    "prev_faildate",
    "total_failure_count",
    "description",
    "cust_brand",
]


def get_latest_raw_file() -> Path:
    """获取 backend/data/raw/ 目录下的工单文件（import 源，不再是查询真相）。"""
    DEFAULT_DATA_FILE = "afc非首次故障-L01线.xlsx"

    if not RAW_DATA_DIR.exists():
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_files = [
        file
        for file in RAW_DATA_DIR.iterdir()
        if file.is_file() and file.suffix.lower() in [".xlsx", ".xls", ".csv"]
    ]

    user_files = [f for f in all_files if f.name != DEFAULT_DATA_FILE]

    if user_files:
        return max(user_files, key=lambda file: file.stat().st_mtime)

    default_file = RAW_DATA_DIR / DEFAULT_DATA_FILE
    if default_file.exists():
        return default_file

    if all_files:
        return max(all_files, key=lambda file: file.stat().st_mtime)

    raise FileNotFoundError(
        f"未找到工单数据文件。请：\n"
        f"1. 通过 POST /upload/workorders 上传 AFC 工单 Excel/CSV 文件；或\n"
        f"2. 将默认数据文件 {DEFAULT_DATA_FILE} 放置到 {RAW_DATA_DIR} 目录下。"
    )


def read_workorder_file(file_path: Path | None = None) -> pl.DataFrame:
    """解析 AFC 工单 Excel / CSV。显式路径用于 import；无路径时读最新 raw 文件。"""
    if file_path is None:
        file_path = get_latest_raw_file()

    suffix = file_path.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        df = pl.read_excel(file_path)
    elif suffix == ".csv":
        try:
            df = pl.read_csv(file_path)
        except Exception:
            df = pl.read_csv(file_path, encoding="gbk")
    else:
        raise ValueError("不支持的文件格式，请上传 .xlsx、.xls 或 .csv 文件")

    df = df.rename({
        column: column.strip()
        for column in df.columns
        if isinstance(column, str)
    })

    return df


def load_workorders(*, include_id: bool = False) -> pl.DataFrame:
    """当前工单工作集。默认 Postgres；file 回退时读最新 Excel/CSV。"""
    if is_sql_backend():
        from backend.infrastructure.workorder_repo import fetch_all_as_dataframe

        return fetch_all_as_dataframe(include_id=include_id)
    return read_workorder_file()


def get_data_source_info() -> dict:
    if is_sql_backend():
        from backend.infrastructure.workorder_repo import get_data_source_info as sql_info

        return sql_info()
    latest_file = get_latest_raw_file()
    return {
        "current_file": latest_file.name,
        "file_path": str(latest_file),
        "backend": "file",
        "import_batch_id": None,
    }
