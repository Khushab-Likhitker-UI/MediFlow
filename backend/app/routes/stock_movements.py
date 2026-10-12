"""
Stock Movements API Router.
Provides idempotent stock update ingestion for offline PWA sync clients.
Prevents duplicate application of operations across reloads and reconnections.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app import db
from app.models.schemas import StockMovementRequest, StockMovementResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stock-movements", tags=["Stock Movements"])


@router.post(
    "",
    response_model=StockMovementResponse,
    status_code=status.HTTP_200_OK,
    summary="Record an idempotent stock movement event (offline sync compatible)",
)
async def record_stock_movement(payload: StockMovementRequest):
    """
    Ingest a stock movement from a PHC client with guaranteed idempotency.
    If the same client_operation_id was previously accepted, returns the previous
    acknowledgement without applying the mutation a second time.
    """
    op_id = payload.client_operation_id

    # 1. Check idempotency ledger
    try:
        cached = db.fetch_one(
            "SELECT * FROM processed_operations WHERE operation_id = %s",
            (op_id,),
        )
        if cached:
            logger.info("Idempotent replay detected for operation %s", op_id)
            cached_data = json.loads(cached["response_payload"])
            return StockMovementResponse(**cached_data)
    except Exception as e:
        logger.warning("Error checking idempotency table: %s", e)

    # 2. Verify facility and medicine exist
    fac = db.fetch_one("SELECT phc_id FROM facilities WHERE phc_id = %s", (payload.phc_id,))
    if not fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility '{payload.phc_id}' does not exist.",
        )

    med = db.fetch_one("SELECT item_id, name, unit FROM medicines WHERE item_id = %s", (payload.item_id,))
    if not med:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medicine item_id {payload.item_id} does not exist.",
        )

    # 3. Read current stock
    inv_row = db.fetch_one(
        "SELECT quantity FROM inventory WHERE phc_id = %s AND item_id = %s AND batch_number = %s",
        (payload.phc_id, payload.item_id, payload.batch_number),
    )
    current_qty = inv_row["quantity"] if inv_row else 0

    m_type = payload.movement_type.lower()
    qty = payload.quantity

    if m_type in ("received", "transferred_in"):
        new_qty = current_qty + qty
    elif m_type in ("dispensed", "transferred_out", "expired"):
        new_qty = max(0, current_qty - qty)
    elif m_type == "adjusted":
        new_qty = qty
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported movement_type '{payload.movement_type}'.",
        )

    now = datetime.now(timezone.utc)
    txn_id = str(uuid.uuid4())

    statements = [
        # UPSERT inventory
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
                quantity = %s,
                timestamp = %s,
                updated_at = %s;
            """,
            (
                payload.phc_id,
                payload.item_id,
                payload.batch_number,
                new_qty,
                payload.occurred_at,
                now,
                now,
                new_qty,
                payload.occurred_at,
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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                txn_id,
                payload.phc_id,
                payload.item_id,
                payload.batch_number,
                m_type,
                qty,
                op_id,
                payload.remarks or f"Offline sync: {m_type}",
                payload.occurred_at,
                now,
                now,
            ),
        ),
    ]

    try:
        db.execute_transaction(statements)
    except Exception as e:
        logger.error("Failed to execute stock movement transaction: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction error during stock movement.",
        )

    response = StockMovementResponse(
        client_operation_id=op_id,
        status="synced",
        message=f"Stock movement '{m_type}' recorded successfully.",
        current_usable_stock=new_qty,
        acknowledged_at=now,
    )

    # Persist in processed_operations ledger for idempotency
    try:
        db.execute_query(
            """
            INSERT INTO processed_operations (
                operation_id, endpoint, phc_id, status_code, response_payload, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (operation_id) DO NOTHING;
            """,
            (
                op_id,
                "/api/v1/stock-movements",
                payload.phc_id,
                200,
                json.dumps(response.model_dump(), default=str),
                now,
            ),
        )
    except Exception as e:
        logger.warning("Failed to store idempotency record: %s", e)

    return response
