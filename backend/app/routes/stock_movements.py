"""
Stock Movements API Router.
Provides idempotent stock update ingestion for offline PWA sync clients.
Prevents duplicate application of operations across reloads and reconnections.
Enforces strict server-side authentication, facility authorization, and atomic concurrency-safe idempotency.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app import db
from app.domain.auth import get_current_user, verify_facility_access
from app.models.schemas import StockMovementRequest, StockMovementResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stock-movements", tags=["Stock Movements"])


@router.post(
    "",
    response_model=StockMovementResponse,
    status_code=status.HTTP_200_OK,
    summary="Record an idempotent stock movement event (offline sync compatible)",
)
async def record_stock_movement(
    payload: StockMovementRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Ingest a stock movement from a PHC client with guaranteed atomic idempotency.
    Enforces server-side authentication and facility worker authorization.
    If the same client_operation_id was previously accepted with the same payload,
    returns the original durable acknowledgement without applying the mutation a second time.
    If reused with a different payload, returns HTTP 409 Conflict.
    """
    # 1. Authorize actor against facility scope
    verify_facility_access(current_user, payload.phc_id)

    op_id = payload.client_operation_id
    now = datetime.now(timezone.utc)
    today_iso = now.date().isoformat()
    m_type = payload.movement_type.lower()
    qty = payload.quantity
    batch_num = payload.batch_number or "DEFAULT_BATCH"

    # 2. Check idempotency ledger first (Fast return of durable acknowledgement or conflict)
    cached_existing = db.fetch_one(
        "SELECT operation_id, response_payload, phc_id FROM processed_operations WHERE operation_id = %s",
        (op_id,),
    )
    if cached_existing:
        cached_data = json.loads(cached_existing["response_payload"])
        if cached_existing.get("phc_id") and cached_existing.get("phc_id") != payload.phc_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Idempotency conflict: Operation '{op_id}' was already executed for facility '{cached_existing['phc_id']}'.",
            )
        if "_request" in cached_data:
            req = cached_data["_request"]
            if (
                req.get("phc_id") != payload.phc_id
                or (payload.item_id is not None and req.get("item_id") != payload.item_id)
                or (payload.batch_number and req.get("batch_number") != batch_num)
                or req.get("movement_type") != m_type
                or req.get("quantity") != qty
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Idempotency conflict: Operation '{op_id}' was already executed "
                        f"with different payload parameters."
                    ),
                )
        logger.info("Idempotent replay detected for operation %s", op_id)
        cached_resp = {k: v for k, v in cached_data.items() if k != "_request"}
        return StockMovementResponse(**cached_resp)

    # 3. Resolve facility
    fac = db.fetch_one(
        "SELECT phc_id, facility_name, district FROM facilities WHERE phc_id = %s",
        (payload.phc_id,),
    )
    if not fac:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility '{payload.phc_id}' does not exist.",
        )

    # 4. Resolve medicine (by item_id or medicine_name)
    med = None
    item_id = payload.item_id
    if item_id is not None:
        med = db.fetch_one(
            "SELECT item_id, name, unit FROM medicines WHERE item_id = %s",
            (item_id,),
        )
    elif payload.medicine_name:
        med = db.fetch_one(
            """
            SELECT item_id, name, unit FROM medicines
            WHERE LOWER(name) = LOWER(%s) OR LOWER(generic_name) = LOWER(%s)
            LIMIT 1
            """,
            (payload.medicine_name.strip(), payload.medicine_name.strip()),
        )
        if med:
            item_id = med["item_id"]

    if not med or item_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medicine '{payload.medicine_name or payload.item_id}' does not exist.",
        )

    # 5. Expiry date resolution & validation (no invented expiry dates)
    expiry_to_use = payload.expiry_date
    if not expiry_to_use:
        existing_batch = db.fetch_one(
            "SELECT expiry_date FROM inventory WHERE item_id = %s AND batch_number = %s LIMIT 1",
            (item_id, batch_num),
        )
        if existing_batch and existing_batch.get("expiry_date"):
            expiry_to_use = str(existing_batch["expiry_date"])
        elif m_type in ("received", "transferred_in", "adjusted"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Missing required batch expiry_date for batch '{batch_num}'. "
                    f"Unknown required expiry dates must not be invented."
                ),
            )
        else:
            expiry_to_use = today_iso

    user_identifier = current_user.get("username") or current_user.get("email", "unknown")
    user_role = current_user.get("role", "worker")

    # 6. Atomic Idempotency Claim & Stock Ledger Execution
    try:
        with db.transaction_context() as conn:
            cur = conn.cursor()

            # Step A: Check for existing idempotency record
            db.execute_cursor(
                cur,
                "SELECT operation_id, response_payload, phc_id FROM processed_operations WHERE operation_id = %s",
                (op_id,),
            )
            existing = cur.fetchone()

            if existing:
                row_dict = dict(existing)
                cached_data = json.loads(row_dict["response_payload"])
                req = cached_data.get("_request", {})

                # Verify payload match
                if (
                    req.get("phc_id") != payload.phc_id
                    or req.get("item_id") != item_id
                    or req.get("batch_number") != batch_num
                    or req.get("movement_type") != m_type
                    or req.get("quantity") != qty
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Idempotency conflict: Operation '{op_id}' was already executed "
                            f"with different payload parameters."
                        ),
                    )

                logger.info("Idempotent replay detected for operation %s", op_id)
                cached_resp = {k: v for k, v in cached_data.items() if k != "_request"}
                return StockMovementResponse(**cached_resp)

            # Step B: Claim the idempotency key immediately within this transaction
            # Any concurrent request with same op_id will raise unique constraint error here
            claim_payload = json.dumps({"status": "processing", "_request": {
                "phc_id": payload.phc_id,
                "item_id": item_id,
                "batch_number": batch_num,
                "movement_type": m_type,
                "quantity": qty,
            }})
            db.execute_cursor(
                cur,
                """
                INSERT INTO processed_operations (
                    operation_id, endpoint, operation_type, phc_id, status_code, response_payload, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    op_id,
                    "/api/v1/stock-movements",
                    m_type,
                    payload.phc_id,
                    200,
                    claim_payload,
                    now.isoformat(),
                ),
            )

            # Step C: Read current stock for this batch
            db.execute_cursor(
                cur,
                """
                SELECT quantity FROM inventory
                WHERE phc_id = %s AND item_id = %s AND batch_number = %s
                """,
                (payload.phc_id, item_id, batch_num),
            )
            inv_row = cur.fetchone()
            current_qty = dict(inv_row)["quantity"] if inv_row else 0

            # Step D: Validate stock mutations
            if m_type in ("received", "transferred_in"):
                new_qty = current_qty + qty
            elif m_type in ("dispensed", "transferred_out", "expired"):
                if current_qty < qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient inventory for {m_type}: facility '{payload.phc_id}' has {current_qty} "
                            f"units of batch '{batch_num}', but requested {qty} units."
                        ),
                    )
                new_qty = current_qty - qty
            elif m_type == "adjusted":
                new_qty = qty
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported movement_type '{payload.movement_type}'.",
                )

            # Step E: Apply inventory mutation
            if inv_row:
                db.execute_cursor(
                    cur,
                    """
                    UPDATE inventory
                    SET quantity = %s,
                        timestamp = %s,
                        updated_at = %s
                    WHERE phc_id = %s AND item_id = %s AND batch_number = %s;
                    """,
                    (new_qty, payload.occurred_at.isoformat(), now.isoformat(), payload.phc_id, item_id, batch_num),
                )
            else:
                db.execute_cursor(
                    cur,
                    """
                    INSERT INTO inventory (
                        inventory_id, phc_id, item_id, batch_number, quantity,
                        expiry_date, timestamp, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        str(uuid.uuid4()),
                        payload.phc_id,
                        item_id,
                        batch_num,
                        new_qty,
                        expiry_to_use,
                        payload.occurred_at.isoformat(),
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )

            # Step F: Track daily consumption observations for ML demand forecasting (dispensed events only)
            if m_type == "dispensed":
                try:
                    db.execute_cursor(
                        cur,
                        """
                        INSERT INTO medicine_consumption (
                            consumption_id, phc_id, item_id, consumption_date, quantity_consumed, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (phc_id, item_id, consumption_date)
                        DO UPDATE SET
                            quantity_consumed = medicine_consumption.quantity_consumed + EXCLUDED.quantity_consumed,
                            updated_at = EXCLUDED.updated_at;
                        """,
                        (
                            str(uuid.uuid4()),
                            payload.phc_id,
                            item_id,
                            today_iso,
                            qty,
                            now.isoformat(),
                            now.isoformat(),
                        ),
                    )
                except Exception as cons_err:
                    logger.warning("Optional consumption table update skipped: %s", cons_err)

            # Step G: Append inventory transaction ledger entry
            txn_id = str(uuid.uuid4())
            db.execute_cursor(
                cur,
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
                    item_id,
                    batch_num,
                    m_type,
                    qty,
                    op_id,
                    payload.remarks or f"PWA sync: {m_type}",
                    payload.occurred_at.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

            # Step H: Append audit log entry
            db.execute_cursor(
                cur,
                """
                INSERT INTO audit_events (
                    event_id, entity_type, entity_id, action, actor_id, actor_role, details, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    str(uuid.uuid4()),
                    "inventory",
                    f"{payload.phc_id}:{item_id}:{batch_num}",
                    f"stock_movement_{m_type}",
                    user_identifier,
                    user_role,
                    json.dumps({
                        "quantity": qty,
                        "old_quantity": current_qty,
                        "new_quantity": new_qty,
                        "client_operation_id": op_id,
                    }),
                    now.isoformat(),
                ),
            )

            # Step I: Build final response and persist durable acknowledgement
            response = StockMovementResponse(
                client_operation_id=op_id,
                status="synced",
                message=f"Stock movement '{m_type}' recorded successfully.",
                current_usable_stock=new_qty,
                acknowledged_at=now,
            )

            final_stored = {
                **response.model_dump(),
                "_request": {
                    "phc_id": payload.phc_id,
                    "item_id": item_id,
                    "batch_number": batch_num,
                    "movement_type": m_type,
                    "quantity": qty,
                },
            }

            db.execute_cursor(
                cur,
                """
                UPDATE processed_operations
                SET response_payload = %s,
                    status_code = 200
                WHERE operation_id = %s;
                """,
                (json.dumps(final_stored, default=str), op_id),
            )

    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e).lower()
        if "unique" in err_msg or "primary key" in err_msg:
            # Concurrent race caught by primary key constraint on operation_id
            # Query the winning durable result
            winning = db.fetch_one(
                "SELECT response_payload FROM processed_operations WHERE operation_id = %s",
                (op_id,),
            )
            if winning:
                cached = json.loads(winning["response_payload"])
                req = cached.get("_request", {})
                if req and (
                    req.get("phc_id") != payload.phc_id
                    or req.get("item_id") != item_id
                    or req.get("movement_type") != m_type
                    or req.get("quantity") != qty
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Idempotency conflict: Operation '{op_id}' was already executed with different payload parameters.",
                    )
                cached_resp = {k: v for k, v in cached.items() if k != "_request"}
                return StockMovementResponse(**cached_resp)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concurrent operation conflict on '{op_id}'. Please retry.",
            )

        logger.error("Stock movement transaction failure: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction failure during stock movement.",
        )

    return response
