"""
Transfers API Router.
Implements the safe inter-facility redistribution workflow:
PROPOSED -> APPROVED -> DISPATCHED -> RECEIVED -> RECONCILED.
Enforces transactional inventory updates, reservation holds, row locking, and audit logs.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import db
from app.domain.auth import get_current_user, require_roles, verify_district_access
from app.domain.donor import evaluate_donor_candidates
from app.domain.inventory import calculate_usable_stock
from app.domain.models import (
    DonorFacilityContext,
    InventoryBatch,
    TransferState,
)
from app.domain.transfer import validate_transition
from app.models.schemas import (
    TransferProposalCreate,
    TransferReceiveRequest,
    TransferRejectRequest,
    TransferResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transfers", tags=["Transfers"])


def _row_to_transfer_response(row: dict) -> TransferResponse:
    """Format database row into a typed TransferResponse."""
    return TransferResponse(
        transfer_id=str(row["transfer_id"]),
        from_phc_id=row["from_phc_id"],
        from_facility_name=row.get("from_facility_name"),
        to_phc_id=row["to_phc_id"],
        to_facility_name=row.get("to_facility_name"),
        item_id=row["item_id"],
        item_name=row.get("item_name"),
        batch_number=row.get("batch_number", "DEFAULT_BATCH"),
        quantity=row["quantity"],
        received_quantity=row.get("received_quantity"),
        status=row["status"],
        reason=row.get("reason"),
        rejection_reason=row.get("rejection_reason"),
        discrepancy_reason=row.get("discrepancy_reason"),
        client_operation_id=str(row["client_operation_id"]) if row.get("client_operation_id") else None,
        proposed_by=row.get("proposed_by"),
        approved_by=row.get("approved_by"),
        dispatched_by=row.get("dispatched_by"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at") or row["created_at"],
        dispatched_at=row.get("dispatched_at"),
        received_at=row.get("received_at"),
    )



# ── 1. Propose Transfer ───────────────────────────────────────────────────────

@router.post(
    "/propose",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a stock transfer between facilities",
)
@router.post(
    "/proposals",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def propose_transfer(
    payload: TransferProposalCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new transfer proposal.
    Rejects self-transfers and ensures donor and recipient facilities exist.
    Supports idempotent submission via client_operation_id.
    """
    if payload.from_phc_id == payload.to_phc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and destination facilities cannot be identical.",
        )

    # 1. Idempotency Check
    if payload.client_operation_id:
        existing = db.fetch_one(
            "SELECT * FROM processed_operations WHERE operation_id = %s",
            (payload.client_operation_id,),
        )
        if existing:
            cached = json.loads(existing["response_payload"])
            return cached

    # 2. Verify facilities exist
    source_fac = db.fetch_one(
        "SELECT phc_id, facility_name, district FROM facilities WHERE phc_id = %s",
        (payload.from_phc_id,),
    )
    if not source_fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source facility '{payload.from_phc_id}' does not exist.",
        )

    dest_fac = db.fetch_one(
        "SELECT phc_id, facility_name, district FROM facilities WHERE phc_id = %s",
        (payload.to_phc_id,),
    )
    if not dest_fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination facility '{payload.to_phc_id}' does not exist.",
        )

    # 3. Verify medicine exists
    medicine = db.fetch_one(
        "SELECT item_id, name, unit FROM medicines WHERE item_id = %s",
        (payload.item_id,),
    )
    if not medicine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medicine item_id {payload.item_id} does not exist.",
        )

    transfer_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    user_identifier = current_user.get("username") or current_user.get("email", "unknown")

    insert_query = """
    INSERT INTO transfers (
        transfer_id, from_phc_id, to_phc_id, item_id, batch_number,
        quantity, status, reason, client_operation_id, proposed_by,
        created_at, updated_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING *;
    """
    params = (
        transfer_id,
        payload.from_phc_id,
        payload.to_phc_id,
        payload.item_id,
        payload.batch_number,
        payload.quantity,
        TransferState.PROPOSED.value,
        payload.reason,
        payload.client_operation_id,
        user_identifier,
        now,
        now,
    )

    try:
        created_row = db.fetch_one(insert_query, params)
    except Exception as e:
        logger.error("Failed to insert transfer proposal: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving transfer proposal.",
        )

    # Enrich with names
    created_row["from_facility_name"] = source_fac["facility_name"]
    created_row["to_facility_name"] = dest_fac["facility_name"]
    created_row["item_name"] = medicine["name"]

    response = _row_to_transfer_response(created_row)

    # Save to processed_operations if client_operation_id provided
    if payload.client_operation_id:
        try:
            db.execute_query(
                """
                INSERT INTO processed_operations (
                    operation_id, endpoint, phc_id, status_code, response_payload, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (operation_id) DO NOTHING;
                """,
                (
                    payload.client_operation_id,
                    "/api/v1/transfers/propose",
                    payload.from_phc_id,
                    201,
                    json.dumps(response.model_dump(), default=str),
                    now,
                ),
            )
        except Exception as e:
            logger.warning("Failed to record idempotency log: %s", e)

    # Log audit event
    try:
        db.execute_query(
            """
            INSERT INTO audit_events (
                entity_type, entity_id, action, actor_id, actor_role, details, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (
                "transfer",
                transfer_id,
                "propose",
                user_identifier,
                current_user.get("role"),
                json.dumps({
                    "from_phc": payload.from_phc_id,
                    "to_phc": payload.to_phc_id,
                    "item_id": payload.item_id,
                    "quantity": payload.quantity,
                }),
                now,
            ),
        )
    except Exception as e:
        logger.warning("Failed to write audit event: %s", e)

    return response


# ── 2. Approve Transfer ───────────────────────────────────────────────────────

@router.post(
    "/{transfer_id}/approve",
    response_model=TransferResponse,
    summary="Approve a transfer proposal and reserve stock atomically",
)
async def approve_transfer(
    transfer_id: str,
    current_user: dict = Depends(require_roles(["admin", "manager"])),
):
    """
    Approve transfer proposal.
    Re-validates live stock on donor, reserves quantity atomically,
    and transitions state from PROPOSED to APPROVED.
    """
    # 1. Fetch current transfer
    transfer = db.fetch_one(
        "SELECT * FROM transfers WHERE transfer_id = %s",
        (transfer_id,),
    )
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transfer '{transfer_id}' not found.",
        )

    current_state = TransferState(transfer["status"])
    validate_transition(current_state, TransferState.APPROVED)

    # Verify authority in source district
    source_fac = db.fetch_one(
        "SELECT district, facility_name FROM facilities WHERE phc_id = %s",
        (transfer["from_phc_id"],),
    )
    verify_district_access(current_user, source_fac.get("district") if source_fac else None)

    # 2. Re-read live stock and active reservations at donor facility
    now = datetime.now(timezone.utc)
    today = now.date()

    batches_raw = db.fetch_all(
        """
        SELECT batch_number, quantity, expiry_date
        FROM inventory
        WHERE phc_id = %s AND item_id = %s
        """,
        (transfer["from_phc_id"], transfer["item_id"]),
    )

    batches = [
        InventoryBatch(
            batch_number=b["batch_number"],
            quantity=b["quantity"],
            expiry_date=b["expiry_date"],
        )
        for b in batches_raw
    ]

    active_res = db.fetch_one(
        """
        SELECT COALESCE(SUM(reserved_quantity), 0) as total_reserved
        FROM stock_reservations
        WHERE phc_id = %s AND item_id = %s AND status = 'active'
        """,
        (transfer["from_phc_id"], transfer["item_id"]),
    )
    current_reserved = active_res["total_reserved"] if active_res else 0

    usable_calc = calculate_usable_stock(
        facility_id=transfer["from_phc_id"],
        item_id=transfer["item_id"],
        item_name="item",
        unit="units",
        batches=batches,
        active_reservations=current_reserved,
        as_of_date=today,
    )

    if usable_calc.usable_quantity < transfer["quantity"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot approve transfer: donor usable stock has changed to "
                f"{usable_calc.usable_quantity}, which is insufficient for requested "
                f"quantity {transfer['quantity']}."
            ),
        )

    # 3. Atomically create reservation and update transfer state
    reservation_id = str(uuid.uuid4())
    user_identifier = current_user.get("username") or current_user.get("email", "unknown")

    transaction_statements = [
        (
            """
            INSERT INTO stock_reservations (
                reservation_id, transfer_id, phc_id, item_id, batch_number,
                reserved_quantity, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s);
            """,
            (
                reservation_id,
                transfer_id,
                transfer["from_phc_id"],
                transfer["item_id"],
                transfer["batch_number"],
                transfer["quantity"],
                now,
                now,
            ),
        ),
        (
            """
            UPDATE transfers
            SET status = 'approved',
                approved_by = %s,
                updated_at = %s
            WHERE transfer_id = %s;
            """,
            (user_identifier, now, transfer_id),
        ),
        (
            """
            INSERT INTO audit_events (
                entity_type, entity_id, action, actor_id, actor_role, details, created_at
            ) VALUES (%s, %s, 'approve', %s, %s, %s, %s);
            """,
            (
                "transfer",
                transfer_id,
                user_identifier,
                current_user.get("role"),
                json.dumps({
                    "reserved_quantity": transfer["quantity"],
                    "reservation_id": reservation_id,
                }),
                now,
            ),
        ),
    ]

    try:
        db.execute_transaction(transaction_statements)
    except Exception as e:
        logger.error("Failed to execute transfer approval transaction: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction error during transfer approval.",
        )

    updated = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    return _row_to_transfer_response(updated)


# ── 3. Reject Transfer ────────────────────────────────────────────────────────

@router.post(
    "/{transfer_id}/reject",
    response_model=TransferResponse,
    summary="Reject a transfer proposal with mandatory reason",
)
async def reject_transfer(
    transfer_id: str,
    payload: TransferRejectRequest,
    current_user: dict = Depends(require_roles(["admin", "manager"])),
):
    """Reject a proposed transfer."""
    transfer = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transfer '{transfer_id}' not found.",
        )

    current_state = TransferState(transfer["status"])
    validate_transition(current_state, TransferState.REJECTED)

    now = datetime.now(timezone.utc)
    user_identifier = current_user.get("username") or current_user.get("email", "unknown")

    try:
        db.execute_query(
            """
            UPDATE transfers
            SET status = 'rejected',
                rejection_reason = %s,
                updated_at = %s
            WHERE transfer_id = %s;
            """,
            (payload.reason, now, transfer_id),
        )
        db.execute_query(
            """
            INSERT INTO audit_events (
                entity_type, entity_id, action, actor_id, actor_role, details, created_at
            ) VALUES (%s, %s, 'reject', %s, %s, %s, %s);
            """,
            (
                "transfer",
                transfer_id,
                user_identifier,
                current_user.get("role"),
                json.dumps({"rejection_reason": payload.reason}),
                now,
            ),
        )
    except Exception as e:
        logger.error("Failed to reject transfer: %s", e)
        raise HTTPException(status_code=500, detail="Database error during transfer rejection.")

    updated = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    return _row_to_transfer_response(updated)


# ── 4. Dispatch Transfer ──────────────────────────────────────────────────────

@router.post(
    "/{transfer_id}/dispatch",
    response_model=TransferResponse,
    summary="Dispatch an approved transfer and deduct from donor physical stock",
)
async def dispatch_transfer(
    transfer_id: str,
    current_user: dict = Depends(require_roles(["admin", "manager"])),
):
    """
    Dispatch transfer:
    1. Validates status is APPROVED.
    2. Deducts quantity from donor's inventory row.
    3. Fulfills the stock reservation hold.
    4. Logs 'transferred_out' in inventory_transactions.
    5. Sets status to DISPATCHED.
    """
    transfer = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found.")

    current_state = TransferState(transfer["status"])
    validate_transition(current_state, TransferState.DISPATCHED)

    now = datetime.now(timezone.utc)
    user_identifier = current_user.get("username") or current_user.get("email", "unknown")
    txn_id = str(uuid.uuid4())

    statements = [
        # Deduct from donor inventory
        (
            """
            UPDATE inventory
            SET quantity = GREATEST(0, quantity - %s),
                updated_at = %s
            WHERE phc_id = %s AND item_id = %s AND batch_number = %s;
            """,
            (
                transfer["quantity"],
                now,
                transfer["from_phc_id"],
                transfer["item_id"],
                transfer["batch_number"],
            ),
        ),
        # Fulfill reservation
        (
            """
            UPDATE stock_reservations
            SET status = 'fulfilled',
                updated_at = %s
            WHERE transfer_id = %s AND status = 'active';
            """,
            (now, transfer_id),
        ),
        # Record inventory transaction
        (
            """
            INSERT INTO inventory_transactions (
                transaction_id, phc_id, item_id, batch_number,
                transaction_type, quantity, reference_id, remarks,
                transaction_date, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'transferred_out', %s, %s, %s, %s, %s, %s);
            """,
            (
                txn_id,
                transfer["from_phc_id"],
                transfer["item_id"],
                transfer["batch_number"],
                transfer["quantity"],
                transfer_id,
                f"Dispatched transfer to {transfer['to_phc_id']}",
                now,
                now,
                now,
            ),
        ),
        # Update transfer status
        (
            """
            UPDATE transfers
            SET status = 'dispatched',
                dispatched_by = %s,
                dispatched_at = %s,
                updated_at = %s
            WHERE transfer_id = %s;
            """,
            (user_identifier, now, now, transfer_id),
        ),
        # Audit log
        (
            """
            INSERT INTO audit_events (
                entity_type, entity_id, action, actor_id, actor_role, details, created_at
            ) VALUES (%s, %s, 'dispatch', %s, %s, %s, %s);
            """,
            (
                "transfer",
                transfer_id,
                user_identifier,
                current_user.get("role"),
                json.dumps({"dispatched_quantity": transfer["quantity"]}),
                now,
            ),
        ),
    ]

    try:
        db.execute_transaction(statements)
    except Exception as e:
        logger.error("Failed to execute transfer dispatch transaction: %s", e)
        raise HTTPException(
            status_code=500, detail="Database error during transfer dispatch."
        )

    updated = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    return _row_to_transfer_response(updated)


# ── 5. Receive Transfer ───────────────────────────────────────────────────────

@router.post(
    "/{transfer_id}/receive",
    response_model=TransferResponse,
    summary="Receive transfer at destination facility and update physical stock",
)
async def receive_transfer(
    transfer_id: str,
    payload: TransferReceiveRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Receive transfer:
    1. Validates status is DISPATCHED.
    2. Adds accepted quantity to destination inventory row.
    3. Logs 'transferred_in' in inventory_transactions.
    4. Handles discrepancies (if received_quantity != dispatched_quantity).
    5. Sets status to RECEIVED (or RECONCILED if exact match).
    """
    transfer = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found.")

    current_state = TransferState(transfer["status"])
    validate_transition(current_state, TransferState.RECEIVED)

    now = datetime.now(timezone.utc)
    user_identifier = current_user.get("username") or current_user.get("email", "unknown")
    txn_id = str(uuid.uuid4())
    received_qty = payload.received_quantity
    dispatched_qty = transfer["quantity"]

    final_status = (
        TransferState.RECONCILED.value
        if received_qty == dispatched_qty and not payload.discrepancy_reason
        else TransferState.RECEIVED.value
    )

    statements = [
        # UPSERT into destination facility inventory
        (
            """
            INSERT INTO inventory (
                inventory_id, phc_id, item_id, batch_number, quantity,
                expiry_date, timestamp, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s,
                CURRENT_DATE + INTERVAL '1 year', %s, %s, %s
            )
            ON CONFLICT (phc_id, item_id, batch_number)
            DO UPDATE SET
                quantity = inventory.quantity + EXCLUDED.quantity,
                updated_at = EXCLUDED.updated_at;
            """,
            (
                transfer["to_phc_id"],
                transfer["item_id"],
                transfer["batch_number"],
                received_qty,
                now,
                now,
                now,
            ),
        ),
        # Record inventory transaction
        (
            """
            INSERT INTO inventory_transactions (
                transaction_id, phc_id, item_id, batch_number,
                transaction_type, quantity, reference_id, remarks,
                transaction_date, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'transferred_in', %s, %s, %s, %s, %s, %s);
            """,
            (
                txn_id,
                transfer["to_phc_id"],
                transfer["item_id"],
                transfer["batch_number"],
                received_qty,
                transfer_id,
                f"Received transfer from {transfer['from_phc_id']}",
                now,
                now,
                now,
            ),
        ),
        # Update transfer status and received quantities
        (
            """
            UPDATE transfers
            SET status = %s,
                received_quantity = %s,
                discrepancy_reason = %s,
                received_by = %s,
                received_at = %s,
                updated_at = %s
            WHERE transfer_id = %s;
            """,
            (
                final_status,
                received_qty,
                payload.discrepancy_reason,
                user_identifier,
                now,
                now,
                transfer_id,
            ),
        ),
        # Audit log
        (
            """
            INSERT INTO audit_events (
                entity_type, entity_id, action, actor_id, actor_role, details, created_at
            ) VALUES (%s, %s, 'receive', %s, %s, %s, %s);
            """,
            (
                "transfer",
                transfer_id,
                user_identifier,
                current_user.get("role"),
                json.dumps({
                    "received_quantity": received_qty,
                    "dispatched_quantity": dispatched_qty,
                    "discrepancy_reason": payload.discrepancy_reason,
                }),
                now,
            ),
        ),
    ]

    try:
        db.execute_transaction(statements)
    except Exception as e:
        logger.error("Failed to execute transfer receipt transaction: %s", e)
        raise HTTPException(status_code=500, detail="Database error during transfer receipt.")

    updated = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    return _row_to_transfer_response(updated)


@router.post(
    "/{transfer_id}/reconcile",
    response_model=TransferResponse,
    summary="Reconcile a received transfer and settle discrepancies (Admin/Manager)",
)
async def reconcile_transfer(
    transfer_id: str,
    payload: dict = {},
    current_user: dict = Depends(require_roles(["admin", "manager"])),
):
    """
    Settle discrepancies and finalize transfer state machine at RECONCILED.
    """
    transfer = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found.")

    current_state = TransferState(transfer["status"])
    validate_transition(current_state, TransferState.RECONCILED)

    now = datetime.now(timezone.utc)
    user_str = current_user.get("username") or current_user.get("email", "unknown")
    notes = payload.get("reconciliation_notes") or payload.get("notes") or "Reconciled ledger"

    statements = [
        (
            """
            UPDATE transfers
            SET status = 'reconciled',
                updated_at = %s
            WHERE transfer_id = %s;
            """,
            (now, transfer_id),
        ),
        (
            """
            INSERT INTO audit_events (
                entity_type, entity_id, action, actor_id, actor_role, details, created_at
            ) VALUES ('transfer', %s, 'reconcile', %s, %s, %s, %s);
            """,
            (
                transfer_id,
                user_str,
                current_user.get("role"),
                json.dumps({"notes": notes, "settled_at": now.isoformat()}),
                now,
            ),
        ),
    ]

    try:
        db.execute_transaction(statements)
    except Exception as e:
        logger.error("Failed to reconcile transfer: %s", e)
        raise HTTPException(status_code=500, detail="Database error during transfer reconciliation.")

    updated = db.fetch_one("SELECT * FROM transfers WHERE transfer_id = %s", (transfer_id,))
    return _row_to_transfer_response(updated)


# ── 6. List Transfers ─────────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=list[TransferResponse],
    summary="List transfers with optional status and facility filters",
)
async def list_transfers(
    status_filter: Optional[str] = Query(None, alias="status"),
    phc_id: Optional[str] = Query(None, description="Filter by facility (source or destination)"),
    from_phc_id: Optional[str] = Query(None),
    to_phc_id: Optional[str] = Query(None),
    item_id: Optional[int] = Query(None),
):
    """Retrieve transfer records filtered by criteria."""
    query = """
    SELECT t.*,
           sf.facility_name AS from_facility_name,
           df.facility_name AS to_facility_name,
           m.name AS item_name
    FROM transfers t
    LEFT JOIN facilities sf ON t.from_phc_id = sf.phc_id
    LEFT JOIN facilities df ON t.to_phc_id = df.phc_id
    LEFT JOIN medicines m ON t.item_id = m.item_id
    WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND t.status = %s"
        params.append(status_filter.lower())

    if phc_id:
        query += " AND (t.from_phc_id = %s OR t.to_phc_id = %s)"
        params.extend([phc_id, phc_id])

    if from_phc_id:
        query += " AND t.from_phc_id = %s"
        params.append(from_phc_id)

    if to_phc_id:
        query += " AND t.to_phc_id = %s"
        params.append(to_phc_id)

    if item_id:
        query += " AND t.item_id = %s"
        params.append(item_id)

    query += " ORDER BY t.created_at DESC"

    try:
        rows = db.fetch_all(query, tuple(params) if params else None)
        return [_row_to_transfer_response(r) for r in rows]
    except Exception as e:
        logger.error("Failed to query transfers: %s", e)
        raise HTTPException(status_code=500, detail="Database error retrieving transfers.")


# ── 7. Get Transfer by ID ─────────────────────────────────────────────────────

@router.get(
    "/{transfer_id}",
    response_model=TransferResponse,
    summary="Get single transfer details by ID",
)
async def get_transfer(transfer_id: str):
    """Retrieve full details for a single transfer."""
    query = """
    SELECT t.*,
           sf.facility_name AS from_facility_name,
           df.facility_name AS to_facility_name,
           m.name AS item_name
    FROM transfers t
    LEFT JOIN facilities sf ON t.from_phc_id = sf.phc_id
    LEFT JOIN facilities df ON t.to_phc_id = df.phc_id
    LEFT JOIN medicines m ON t.item_id = m.item_id
    WHERE t.transfer_id = %s
    """
    row = db.fetch_one(query, (transfer_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Transfer not found.")
    return _row_to_transfer_response(row)


# ── 8. Evaluate Safe Donor Candidates ─────────────────────────────────────────

@router.get(
    "/candidates",
    summary="Query safe candidate donors for a facility deficit",
)
@router.get(
    "/candidates/evaluate",
    summary="Evaluate and rank safe donor candidates for a facility deficit",
)
async def evaluate_candidates(
    recipient_phc_id: Optional[str] = Query(None, description="Recipient facility ID"),
    to_phc_id: Optional[str] = Query(None, description="Recipient facility ID alias"),
    item_id: int = Query(..., description="Medicine item ID"),
    deficit: int = Query(50, gt=0, description="Projected deficit quantity needed"),
):
    """
    Deterministic donor evaluation endpoint.
    Returns ranked safe donor candidates without violating donors' safety reserves.
    """
    target_phc_id = recipient_phc_id or to_phc_id
    if not target_phc_id:
        raise HTTPException(status_code=422, detail="Missing recipient_phc_id or to_phc_id query parameter.")

    # 1. Fetch recipient facility details
    recip = db.fetch_one(
        "SELECT phc_id, facility_name, district, latitude, longitude FROM facilities WHERE phc_id = %s",
        (target_phc_id,),
    )
    if not recip:
        raise HTTPException(status_code=404, detail=f"Recipient PHC '{target_phc_id}' not found.")

    med = db.fetch_one("SELECT item_id, name, unit FROM medicines WHERE item_id = %s", (item_id,))
    if not med:
        raise HTTPException(status_code=404, detail=f"Medicine {item_id} not found.")

    # 2. Fetch all other active facilities
    other_facs = db.fetch_all(
        """
        SELECT phc_id, facility_name, district, latitude, longitude
        FROM facilities
        WHERE phc_id != %s AND operational_status = 'active'
        """,
        (target_phc_id,),
    )

    # 3. Build contexts for each candidate facility
    contexts = []
    for f in other_facs:
        fac_id = f["phc_id"]
        batches_raw = db.fetch_all(
            "SELECT batch_number, quantity, expiry_date FROM inventory WHERE phc_id = %s AND item_id = %s",
            (fac_id, item_id),
        )
        batches = [
            InventoryBatch(
                batch_number=b["batch_number"],
                quantity=b["quantity"],
                expiry_date=b["expiry_date"],
            )
            for b in batches_raw
        ]

        active_res = db.fetch_one(
            "SELECT COALESCE(SUM(reserved_quantity), 0) as total FROM stock_reservations WHERE phc_id = %s AND item_id = %s AND status = 'active'",
            (fac_id, item_id),
        )
        res_count = active_res["total"] if active_res else 0

        contexts.append(
            DonorFacilityContext(
                facility_id=fac_id,
                facility_name=f["facility_name"],
                district=f["district"],
                latitude=float(f["latitude"]),
                longitude=float(f["longitude"]),
                batches=batches,
                active_reservations=res_count,
                safety_reserve=50,
                projected_demand_over_horizon=20,
            )
        )

    # 4. Evaluate using pure domain engine
    proposal_res = evaluate_donor_candidates(
        recipient_facility_id=target_phc_id,
        recipient_facility_name=recip["facility_name"],
        recipient_district=recip["district"],
        recipient_lat=float(recip["latitude"]),
        recipient_lng=float(recip["longitude"]),
        item_id=item_id,
        item_name=med["name"],
        unit=med["unit"],
        recipient_deficit=deficit,
        candidate_contexts=contexts,
    )


    return {
        "recipient_facility_id": proposal_res.recipient_facility_id,
        "recipient_facility_name": proposal_res.recipient_facility_name,
        "item_id": proposal_res.item_id,
        "item_name": proposal_res.item_name,
        "unit": proposal_res.unit,
        "recipient_deficit": proposal_res.recipient_deficit,
        "has_safe_donor": proposal_res.has_safe_donor,
        "recommended_candidate": (
            {
                "facility_id": proposal_res.recommended_candidate.facility_id,
                "facility_name": proposal_res.recommended_candidate.facility_name,
                "district": proposal_res.recommended_candidate.district,
                "donor_safe_surplus": proposal_res.recommended_candidate.donor_safe_surplus,
                "transferable_quantity": proposal_res.recommended_candidate.transferable_quantity,
                "distance_km": proposal_res.recommended_candidate.distance_km,
                "rank": proposal_res.recommended_candidate.rank,
            }
            if proposal_res.recommended_candidate
            else None
        ),
        "recommended_quantity": proposal_res.recommended_quantity,
        "escalation_action": proposal_res.escalation_action,
        "candidates": [
            {
                "facility_id": c.facility_id,
                "facility_name": c.facility_name,
                "district": c.district,
                "current_usable_stock": c.current_usable_stock,
                "protected_reserve": c.protected_reserve,
                "donor_safe_surplus": c.donor_safe_surplus,
                "transferable_quantity": c.transferable_quantity,
                "distance_km": c.distance_km,
                "is_eligible": c.is_eligible,
                "rejection_reason": c.rejection_reason,
                "rank": c.rank,
            }
            for c in proposal_res.candidates
        ],
    }
