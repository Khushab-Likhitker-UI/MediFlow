"""
Transfer state machine and ledger accounting rules.
Governs transfer transitions: PROPOSED -> APPROVED -> DISPATCHED -> RECEIVED -> RECONCILED.
Enforces transactional integrity, reservation creation, and discrepancy handling.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.domain.models import TransferState


class TransferDomainError(Exception):
    """Base domain error for transfer operations."""
    pass


class InvalidStateTransitionError(TransferDomainError):
    """Raised when an illegal transfer state transition is attempted."""
    pass


class InsufficientStockError(TransferDomainError):
    """Raised when live inventory at donor is insufficient at approval time."""
    pass


class IdempotencyConflictError(TransferDomainError):
    """Raised when an operation ID was already processed."""
    pass


VALID_TRANSITIONS: dict[TransferState, set[TransferState]] = {
    TransferState.PROPOSED: {
        TransferState.APPROVED,
        TransferState.REJECTED,
        TransferState.CANCELLED,
    },
    TransferState.APPROVED: {
        TransferState.DISPATCHED,
        TransferState.CANCELLED,
    },
    TransferState.DISPATCHED: {
        TransferState.RECEIVED,
        TransferState.EXCEPTION,
    },
    TransferState.RECEIVED: {
        TransferState.RECONCILED,
    },
    TransferState.REJECTED: set(),
    TransferState.CANCELLED: set(),
    TransferState.EXCEPTION: {
        TransferState.RECONCILED,
    },
    TransferState.RECONCILED: set(),
}


def validate_transition(current: TransferState, target: TransferState) -> None:
    """Validate whether transitioning from current to target state is permissible."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition transfer from '{current.value}' to '{target.value}'. "
            f"Allowed next states: {[s.value for s in allowed]}"
        )


@dataclass
class TransferLedgerEntry:
    transfer_id: str
    from_phc_id: str
    to_phc_id: str
    item_id: int
    batch_number: str
    quantity: int
    received_quantity: Optional[int]
    status: TransferState
    client_operation_id: Optional[str]
    reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    discrepancy_reason: Optional[str] = None
    created_at: datetime = None
    dispatched_at: Optional[datetime] = None
    received_at: Optional[datetime] = None

    def can_transition_to(self, new_state: TransferState) -> bool:
        return new_state in VALID_TRANSITIONS.get(self.status, set())
