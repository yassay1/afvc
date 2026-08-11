"""用例 HTTP API —— 薄路由，只调用 application.usecases。"""

from fastapi import APIRouter, HTTPException, Query

from backend.application import usecases
from backend.domain.risk import SUPPORTED_PREDICTION_WINDOWS

router = APIRouter(
    prefix="/usecases",
    tags=["业务用例"],
)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/overview")
def overview(top_n: int = Query(default=10, ge=1, le=30)):
    try:
        return usecases.get_data_overview(top_n=top_n)
    except Exception as e:
        raise _http_error(e) from e


@router.get("/high-risk")
def high_risk(top_n: int = Query(default=10, ge=1, le=50)):
    try:
        return usecases.list_high_risk_devices(top_n=top_n)
    except Exception as e:
        raise _http_error(e) from e


@router.get("/devices/{assetnum}/history")
def device_history(
    assetnum: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        return usecases.get_device_history(assetnum=assetnum, limit=limit)
    except Exception as e:
        raise _http_error(e) from e


@router.get("/devices/{assetnum}/risk")
def device_risk(assetnum: str):
    try:
        return usecases.predict_device_risk(assetnum)
    except Exception as e:
        raise _http_error(e) from e


@router.get("/devices/{assetnum}/advice")
def device_advice(assetnum: str):
    try:
        return usecases.advise_maintenance(assetnum)
    except Exception as e:
        raise _http_error(e) from e


@router.get("/devices/{assetnum}/fault-type")
def device_fault_type(
    assetnum: str,
    window_days: int = Query(default=30, ge=7, le=90),
    top_k: int = Query(default=3, ge=1, le=10),
):
    if window_days not in SUPPORTED_PREDICTION_WINDOWS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"不支持的预测窗口 {window_days} 天，"
                f"支持窗口：{list(SUPPORTED_PREDICTION_WINDOWS)}"
            ),
        )
    try:
        return usecases.predict_fault_type(
            assetnum=assetnum,
            window_days=window_days,
            top_k=top_k,
        )
    except Exception as e:
        raise _http_error(e) from e


@router.get("/devices/{assetnum}/diagnosis")
def device_diagnosis(
    assetnum: str,
    history_limit: int = Query(default=50, ge=1, le=200),
):
    try:
        return usecases.diagnose_device(
            assetnum=assetnum,
            history_limit=history_limit,
        )
    except Exception as e:
        raise _http_error(e) from e


@router.get("/manuals/search")
def manuals_search(
    query: str = Query(..., min_length=1),
    assetnum: str | None = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=20),
):
    try:
        return usecases.search_manual(
            query=query,
            assetnum=assetnum,
            top_k=top_k,
        )
    except Exception as e:
        raise _http_error(e) from e
