"""Import the default Excel workorder file into PostgreSQL (replace working set)."""

from backend.infrastructure.db import init_db
from backend.infrastructure.workorder_repo import import_from_path
from backend.infrastructure.workorders import RAW_DATA_DIR

DEFAULT_DATA_FILE = "afc非首次故障-L01线.xlsx"


def main() -> None:
    path = RAW_DATA_DIR / DEFAULT_DATA_FILE
    if not path.exists():
        raise SystemExit(f"default file not found: {path}")
    init_db(with_checkpointer=False)
    result = import_from_path(path, mode="replace")
    print(
        f"imported {result['row_count']} rows "
        f"batch={result['import_batch_id']} file={result['source_filename']}"
    )


if __name__ == "__main__":
    main()
