"""Pending-action state machine unit tests."""

from backend.domain.pending_action import (
    EXECUTED,
    FAILED,
    PENDING,
    REJECTED,
    InvalidTransitionError,
    assert_transition,
    can_transition,
)


def test_allowed_transitions_from_pending():
    assert can_transition(PENDING, EXECUTED)
    assert can_transition(PENDING, REJECTED)
    assert can_transition(PENDING, FAILED)


def test_terminal_states_cannot_transition():
    for status in (EXECUTED, REJECTED, FAILED):
        assert not can_transition(status, PENDING)
        assert not can_transition(status, EXECUTED)
        assert not can_transition(status, REJECTED)


def test_assert_transition_rejects_illegal_path():
    try:
        assert_transition(REJECTED, EXECUTED)
    except InvalidTransitionError as exc:
        assert exc.from_status == REJECTED
        assert exc.to_status == EXECUTED
    else:
        raise AssertionError("expected InvalidTransitionError")
