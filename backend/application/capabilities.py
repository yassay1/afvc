"""Closed capability catalog — single source for safe vs sensitive tools."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final


class ToolTier(StrEnum):
    SAFE = "safe"
    SENSITIVE = "sensitive"


CAPABILITIES: Final[dict[str, dict[str, Any]]] = {
    "get_overview": {"layer": "data", "tier": ToolTier.SAFE, "exposed": True},
    "get_device_history": {"layer": "data", "tier": ToolTier.SAFE, "exposed": True},
    "list_high_risk": {"layer": "prediction", "tier": ToolTier.SAFE, "exposed": True},
    "list_maintenance_suggestions": {
        "layer": "maintenance",
        "tier": ToolTier.SAFE,
        "exposed": True,
    },
    "list_maintenance_tasks": {"layer": "maintenance", "tier": ToolTier.SAFE, "exposed": True},
    "predict_device_risk": {"layer": "prediction", "tier": ToolTier.SAFE, "exposed": True},
    "predict_fault_type": {"layer": "prediction", "tier": ToolTier.SAFE, "exposed": True},
    "advise_maintenance": {"layer": "application", "tier": ToolTier.SAFE, "exposed": True},
    "search_manual": {"layer": "application", "tier": ToolTier.SAFE, "exposed": True},
    "diagnose_device": {"layer": "application", "tier": ToolTier.SAFE, "exposed": True},
    "create_maintenance_task": {
        "layer": "maintenance",
        "tier": ToolTier.SENSITIVE,
        "exposed": False,
    },
    "adjust_maintenance_task": {
        "layer": "maintenance",
        "tier": ToolTier.SENSITIVE,
        "exposed": False,
    },
    "submit_maintenance_feedback": {
        "layer": "maintenance",
        "tier": ToolTier.SENSITIVE,
        "exposed": False,
    },
    "insert_workorder": {"layer": "data", "tier": ToolTier.SENSITIVE, "exposed": True},
    "update_workorder": {"layer": "data", "tier": ToolTier.SENSITIVE, "exposed": True},
    "delete_workorder": {"layer": "data", "tier": ToolTier.SENSITIVE, "exposed": True},
    "import_workorders": {"layer": "data", "tier": ToolTier.SENSITIVE, "exposed": True},
}


def is_sensitive(name: str) -> bool:
    meta = CAPABILITIES.get(name)
    return bool(meta and meta["tier"] == ToolTier.SENSITIVE)


def is_safe(name: str) -> bool:
    meta = CAPABILITIES.get(name)
    return bool(meta and meta["tier"] == ToolTier.SAFE)


def exposed_capability_names(*, tier: ToolTier | None = None) -> list[str]:
    names: list[str] = []
    for name, meta in CAPABILITIES.items():
        if not meta.get("exposed"):
            continue
        if tier is not None and meta["tier"] != tier:
            continue
        names.append(name)
    return names
