"""Pending-action statuses and allowed transitions. No IO."""

from __future__ import annotations

from typing import Final

PENDING: Final = "pending"
EXECUTED: Final = "executed"
REJECTED: Final = "rejected"
FAILED: Final = "failed"
EXPIRED: Final = "expired"

ALL_STATUSES: Final[frozenset[str]] = frozenset(
    {PENDING, EXECUTED, REJECTED, FAILED, EXPIRED}
)

TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {EXECUTED, REJECTED, FAILED, EXPIRED}
)

# Transitions that persist a new status. Idempotent re-read of executed is not a transition.
ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    PENDING: frozenset({EXECUTED, REJECTED, FAILED, EXPIRED}),
    EXECUTED: frozenset(),
    REJECTED: frozenset(),
    FAILED: frozenset(),
    EXPIRED: frozenset(),
}


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status not in ALL_STATUSES or to_status not in ALL_STATUSES:
        return False
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


def assert_transition(from_status: str, to_status: str) -> None:
    if not can_transition(from_status, to_status):
        raise InvalidTransitionError(from_status, to_status)


class PendingActionError(Exception):
    """Base type for approval/pending-action failures."""


class InvalidTransitionError(PendingActionError):
    def __init__(self, from_status: str, to_status: str):
        super().__init__(f"不能从 {from_status} 转到 {to_status}")
        self.from_status = from_status
        self.to_status = to_status


class ActionNotFoundError(PendingActionError):
    def __init__(self, action_id: str, thread_id: str | None = None):
        super().__init__("待审批操作不存在")
        self.action_id = action_id
        self.thread_id = thread_id


class ActionConflictError(PendingActionError):
    def __init__(self, action_id: str, status: str, message: str | None = None):
        super().__init__(message or f"待审批操作当前状态为 {status}，不能执行该操作")
        self.action_id = action_id
        self.status = status


class ActionExecutionError(PendingActionError):
    def __init__(self, action_id: str, error: str):
        super().__init__(error)
        self.action_id = action_id
        self.error = error
