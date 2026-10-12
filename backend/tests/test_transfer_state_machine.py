"""
Unit tests for the transfer state machine and transition rules.
Verifies allowed states, illegal transition rejections, and discrepancy handling.
"""

import pytest

from app.domain.models import TransferState
from app.domain.transfer import (
    InvalidStateTransitionError,
    TransferLedgerEntry,
    validate_transition,
)


def test_valid_golden_path_transitions():
    """Verify the normal complete transfer lifecycle."""
    validate_transition(TransferState.PROPOSED, TransferState.APPROVED)
    validate_transition(TransferState.APPROVED, TransferState.DISPATCHED)
    validate_transition(TransferState.DISPATCHED, TransferState.RECEIVED)
    validate_transition(TransferState.RECEIVED, TransferState.RECONCILED)


def test_valid_rejection_and_cancellation():
    """Verify proposal rejection and cancellation transitions."""
    validate_transition(TransferState.PROPOSED, TransferState.REJECTED)
    validate_transition(TransferState.PROPOSED, TransferState.CANCELLED)
    validate_transition(TransferState.APPROVED, TransferState.CANCELLED)


def test_illegal_state_skips_rejected():
    """Cannot jump directly from PROPOSED to RECEIVED or DISPATCHED."""
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.PROPOSED, TransferState.RECEIVED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.PROPOSED, TransferState.DISPATCHED)


def test_cannot_approve_without_proposal():
    """Cannot approve an already approved, rejected, or dispatched transfer."""
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.APPROVED, TransferState.APPROVED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.REJECTED, TransferState.APPROVED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.DISPATCHED, TransferState.APPROVED)


def test_cannot_skip_dispatch_to_receive():
    """Approval does not equal receipt. Must be dispatched before received."""
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.APPROVED, TransferState.RECEIVED)


def test_cannot_rewind_from_received():
    """A received transfer cannot be dispatched or approved again."""
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.RECEIVED, TransferState.DISPATCHED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransferState.RECONCILED, TransferState.PROPOSED)


def test_transfer_ledger_entry_can_transition():
    """Verify helper method on TransferLedgerEntry model."""
    entry = TransferLedgerEntry(
        transfer_id="t-1",
        from_phc_id="PHC-001",
        to_phc_id="PHC-002",
        item_id=1,
        batch_number="B1",
        quantity=50,
        received_quantity=None,
        status=TransferState.PROPOSED,
        client_operation_id="op-1",
    )

    assert entry.can_transition_to(TransferState.APPROVED) is True
    assert entry.can_transition_to(TransferState.REJECTED) is True
    assert entry.can_transition_to(TransferState.DISPATCHED) is False
    assert entry.can_transition_to(TransferState.RECEIVED) is False
