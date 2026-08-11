"""Application 用例门面 —— 八个对外用例函数的唯一导出点。"""

from backend.application.advice import advise_maintenance
from backend.application.diagnose import diagnose_device
from backend.application.fault_type import predict_fault_type
from backend.application.history import get_device_history
from backend.application.manual import search_manual
from backend.application.overview import get_data_overview
from backend.application.risk import list_high_risk_devices, predict_device_risk

__all__ = [
    "get_data_overview",
    "list_high_risk_devices",
    "get_device_history",
    "predict_device_risk",
    "advise_maintenance",
    "search_manual",
    "predict_fault_type",
    "diagnose_device",
]
