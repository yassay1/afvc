from pathlib import Path
from datetime import datetime
import shutil

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query

from backend.api.deps import require_login
from backend.core.config import get_data_profile, is_sql_backend


router = APIRouter(
    prefix="/upload",
    tags=["工单文件上传"],
    dependencies=[Depends(require_login)],
)


RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/workorders")
def upload_workorder_file(
    file: UploadFile = File(...),
    mode: str = Query(default="replace"),
):
    """
    上传 AFC 维修工单文件。

    1. 保存到 backend/data/raw/（保留原文件，不进 checkpoint）；
    2. 默认将解析结果 import 进 Postgres（控制台点击上传 = 该通道已批准写入）。
    """

    if get_data_profile() == "demo":
        raise HTTPException(status_code=403, detail="demo 模式禁止上传工单")

    if mode not in {"replace", "append"}:
        raise HTTPException(status_code=422, detail="import mode 必须是 replace 或 append")

    allowed_suffixes = [".xlsx", ".xls", ".csv"]

    original_filename = file.filename

    if not original_filename:
        raise HTTPException(
            status_code=400,
            detail="未检测到上传文件名"
        )

    suffix = Path(original_filename).suffix.lower()

    if suffix not in allowed_suffixes:
        raise HTTPException(
            status_code=400,
            detail="文件格式不支持，请上传 .xlsx、.xls 或 .csv 文件"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{original_filename}"

    save_path = RAW_DATA_DIR / safe_filename

    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"文件保存失败：{str(e)}"
        )
    finally:
        file.file.close()

    payload = {
        "status": "success",
        "message": "工单文件上传成功",
        "original_filename": original_filename,
        "saved_filename": safe_filename,
        "saved_path": str(save_path),
        "file_suffix": suffix,
        "import_mode": mode,
    }

    if is_sql_backend():
        from backend.infrastructure.workorder_repo import import_from_path

        try:
            imported = import_from_path(save_path, mode=mode)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"文件已保存，但导入数据库失败：{str(e)}"
            ) from e
        payload["message"] = "工单文件已保存并导入数据库"
        payload["import"] = imported
        payload["row_count"] = imported.get("row_count")
        payload["import_batch_id"] = imported.get("import_batch_id")

    return payload
