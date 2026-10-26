"""Application 用例门面 —— 对外用例函数的唯一导出点。"""

from backend.application.advice import advise_maintenance
from backend.application.diagnose import diagnose_device
from backend.application.fault_type import predict_fault_type
from backend.application.history import get_device_history, get_device_list
from backend.application.maintenance_suggestions import list_maintenance_suggestions
from backend.application.maintenance_tasks import (
    accept_suggestion_as_task,
    adjust_maintenance_task,
    create_maintenance_task,
    get_maintenance_task,
    list_maintenance_tasks,
    submit_maintenance_feedback,
)
from backend.application.manual import search_manual
from backend.application.overview import get_data_overview
from backend.application.risk import list_high_risk_devices, predict_device_risk

__all__ = [
    "get_data_overview",
    "list_high_risk_devices",
    "list_maintenance_suggestions",
    "list_maintenance_tasks",
    "create_maintenance_task",
    "get_maintenance_task",
    "adjust_maintenance_task",
    "submit_maintenance_feedback",
    "accept_suggestion_as_task",
    "get_device_history",
    "get_device_list",
    "predict_device_risk",
    "advise_maintenance",
    "search_manual",
    "predict_fault_type",
    "diagnose_device",
]
