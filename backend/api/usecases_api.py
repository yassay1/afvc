"""用例 HTTP API —— 薄路由，只调用 application.usecases。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.deps import require_login
from backend.application import usecases
from backend.domain.maintenance import MaintenanceTaskTransitionError, MaintenanceTaskValidationError
from backend.domain.risk import SUPPORTED_PREDICTION_WINDOWS

router = APIRouter(
    prefix="/usecases",
    tags=["业务用例"],
    dependencies=[Depends(require_login)],
)


class DeviceListItem(BaseModel):
    assetnum: str
    workorder_count: int
    station_name: str | None = None
    line: str | None = None
    brand: str | None = None
    last_record_time: str | None = None


class DeviceListResponse(BaseModel):
    status: str
    message: str
    device_count: int
    devices: list[DeviceListItem]


class MaintenanceTaskCreate(BaseModel):
    assetnum: str
    station_name: str | None = None
    fault_focus: str = "暂停服务"
    priority: int = Field(default=100, ge=1, strict=True)
    planned_date: str | None = None
    assignee_crew_id: str | None = None
    status: str = "planned"
    suggestion_score: float | None = None
    suggestion_reasons: list[str] = Field(default_factory=list)
    reasons: list[str] | None = None


class MaintenanceTaskPatch(BaseModel):
    priority: int | None = Field(default=None, ge=1, strict=True)
    planned_date: str | None = None
    assignee_crew_id: str | None = None
    status: str | None = None


class MaintenanceFeedbackBody(BaseModel):
    result: str
    matched_fault: bool | None = None
    followed_suggestion: bool | None = None
    note: str | None = None


class AcceptSuggestionBody(BaseModel):
    suggestion: dict[str, Any] | None = None
    priority: int | None = Field(default=None, ge=1, strict=True)
    assetnum: str | None = None
    station_name: str | None = None
    fault_focus: str | None = None
    suggested_crew_id: str | None = None
    score: float | None = None
    reasons: list[str] | None = None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MaintenanceTaskTransitionError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, MaintenanceTaskValidationError):
        return HTTPException(status_code=422, detail=str(exc))
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


@router.get("/devices", response_model=DeviceListResponse)
def device_list():
    try:
        return usecases.get_device_list()
    except Exception as e:
        raise _http_error(e) from e


@router.get("/maintenance/suggestions")
def maintenance_suggestions(
    top_n: int = Query(default=10, ge=1, le=50),
    fault_focus: str = Query(default="暂停服务"),
):
    try:
        return usecases.list_maintenance_suggestions(
            top_n=top_n,
            fault_focus=fault_focus,
        )
    except Exception as e:
        raise _http_error(e) from e


@router.get("/maintenance/tasks")
def maintenance_tasks_list(status: str | None = Query(default=None)):
    try:
        return usecases.list_maintenance_tasks(status=status)
    except Exception as e:
        raise _http_error(e) from e


@router.post("/maintenance/tasks")
def maintenance_tasks_create(body: MaintenanceTaskCreate):
    try:
        payload = body.model_dump()
        if not payload.get("suggestion_reasons") and payload.get("reasons"):
            payload["suggestion_reasons"] = payload["reasons"]
        return usecases.create_maintenance_task(payload)
    except Exception as e:
        raise _http_error(e) from e


@router.get("/maintenance/tasks/{task_id}")
def maintenance_task_get(task_id: str):
    try:
        return usecases.get_maintenance_task(task_id)
    except Exception as e:
        raise _http_error(e) from e


@router.patch("/maintenance/tasks/{task_id}")
def maintenance_task_adjust(task_id: str, body: MaintenanceTaskPatch):
    try:
        return usecases.adjust_maintenance_task(
            task_id,
            body.model_dump(exclude_none=True),
        )
    except Exception as e:
        raise _http_error(e) from e


@router.post("/maintenance/tasks/{task_id}/feedback")
def maintenance_task_feedback(task_id: str, body: MaintenanceFeedbackBody):
    try:
        return usecases.submit_maintenance_feedback(
            task_id,
            result=body.result,
            matched_fault=body.matched_fault,
            followed_suggestion=body.followed_suggestion,
            note=body.note,
        )
    except Exception as e:
        raise _http_error(e) from e


@router.post("/maintenance/accept-suggestion")
def maintenance_accept_suggestion(body: AcceptSuggestionBody):
    try:
        suggestion = body.suggestion or {
            "assetnum": body.assetnum,
            "station_name": body.station_name,
            "fault_focus": body.fault_focus,
            "suggested_crew_id": body.suggested_crew_id,
            "score": body.score,
            "reasons": body.reasons or [],
        }
        return usecases.accept_suggestion_as_task(
            suggestion,
            priority=body.priority,
        )
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
