"""
Inventory management routes.

Provides CRUD endpoints for healthcare supply items
(masks, gloves, syringes, medications, etc.).

Security:
- Every SQL statement uses parameterised queries (``%s`` placeholders).
- Multi-table operations (medicine + inventory) execute inside a single
  PostgreSQL transaction with automatic rollback on failure.
- Foreign-key references (PHC, medicine) are validated before INSERT.
- Negative quantities are rejected before reaching the database.
- Duplicate medicine names are caught via the UNIQUE constraint.

Response payloads are kept **identical** to the previous version
so the React frontend continues to work without changes.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query

from app.models.schemas import SupplyItem, SupplyItemCreate, StockUpdate
from app import db


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _verify_phc_exists(phc_id: str) -> None:
    """Raise 400 if *phc_id* does not exist in the ``facilities`` table."""
    try:
        check = db.fetch_one(
            "SELECT phc_id FROM facilities WHERE phc_id = %s", (phc_id,)
        )
    except Exception as e:
        logger.error("Failed to verify PHC %s: %s", phc_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to verify facility"
        )
    if not check:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid PHC ID '{phc_id}'. Facility does not exist.",
        )


def _classify_db_error(exc: Exception) -> HTTPException:
    """Map a psycopg2 exception to the most appropriate HTTPException."""
    msg = str(exc).lower()
    if "unique constraint" in msg or "duplicate key" in msg:
        return HTTPException(status_code=409, detail="Duplicate entry — record already exists")
    if "foreign key constraint" in msg:
        return HTTPException(status_code=400, detail="Invalid reference (PHC or medicine)")
    if "not-null constraint" in msg:
        return HTTPException(status_code=400, detail="Missing required field")
    return HTTPException(status_code=500, detail="Database operation failed")


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[SupplyItem], summary="List all supply items")
async def list_items(
    category: str | None = Query(None, description="Filter by category"),
    low_stock: bool = Query(False, description="Show only items below reorder level"),
):
    """List all supply items with aggregated quantity from inventory.

    Uses a single JOIN + GROUP BY — no N+1 queries.
    """
    try:
        query = """
        SELECT
            m.item_id   AS id,
            m.name,
            m.category,
            COALESCE(SUM(i.quantity), 0) AS quantity,
            m.unit,
            m.reorder_level,
            m.supplier,
            COALESCE(MAX(i.updated_at), m.updated_at) AS last_updated
        FROM medicines m
        LEFT JOIN inventory i ON m.item_id = i.item_id
        GROUP BY m.item_id
        ORDER BY m.item_id
        """
        records = db.fetch_all(query)
    except Exception as e:
        logger.error("Failed to list items: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve inventory items")

    if category:
        records = [
            r for r in records if r["category"].lower() == category.lower()
        ]
    if low_stock:
        records = [r for r in records if r["quantity"] <= r["reorder_level"]]

    return records


@router.get("/{item_id}", response_model=SupplyItem, summary="Get a single supply item")
async def get_item(item_id: int):
    """Fetch a single supply item by its medicine ID."""
    try:
        query = """
        SELECT
            m.item_id   AS id,
            m.name,
            m.category,
            COALESCE(SUM(i.quantity), 0) AS quantity,
            m.unit,
            m.reorder_level,
            m.supplier,
            COALESCE(MAX(i.updated_at), m.updated_at) AS last_updated
        FROM medicines m
        LEFT JOIN inventory i ON m.item_id = i.item_id
        WHERE m.item_id = %s
        GROUP BY m.item_id
        """
        record = db.fetch_one(query, (item_id,))
    except Exception as e:
        logger.error("Failed to fetch item %d: %s", item_id, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve item")

    if not record:
        raise HTTPException(status_code=404, detail="Item not found")
    return record


@router.post("/", response_model=SupplyItem, status_code=201, summary="Add a new supply item")
async def create_item(item_in: SupplyItemCreate):
    """Add a new medicine to the catalogue.

    When ``quantity > 0``, an inventory row is also created atomically
    (using PHC-001 / DEFAULT_BATCH) inside a **single** transaction.
    If the default PHC does not exist in the database the medicine is
    still created but no inventory row is added.
    """
    med_query = """
    INSERT INTO medicines (name, category, unit, reorder_level, supplier)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING item_id, updated_at
    """

    if item_in.quantity > 0:
        # ── Transactional: medicine + initial inventory ──────────────────
        inv_query = """
        INSERT INTO inventory (phc_id, item_id, batch_number, quantity, offline_sync_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (phc_id, item_id, batch_number)
        DO UPDATE SET quantity = EXCLUDED.quantity, updated_at = NOW()
        """
        try:
            # Check if the default PHC exists before attempting inventory
            default_phc = "PHC-001"
            phc_check = db.fetch_one(
                "SELECT phc_id FROM facilities WHERE phc_id = %s",
                (default_phc,),
            )

            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        med_query,
                        (
                            item_in.name,
                            item_in.category,
                            item_in.unit,
                            item_in.reorder_level,
                            item_in.supplier,
                        ),
                    )
                    row = cur.fetchone()  # (item_id, updated_at)
                    if not row:
                        conn.rollback()
                        raise HTTPException(
                            status_code=500, detail="Failed to create medicine"
                        )

                    item_id, updated_at = row[0], row[1]

                    # Only create inventory if the default PHC exists
                    if phc_check:
                        cur.execute(
                            inv_query,
                            (
                                default_phc,
                                item_id,
                                "DEFAULT_BATCH",
                                item_in.quantity,
                                str(uuid.uuid4()),
                            ),
                        )
                    else:
                        logger.warning(
                            "Default PHC '%s' not found; creating medicine "
                            "without inventory row.",
                            default_phc,
                        )

                    conn.commit()

        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "unique constraint" in error_msg or "duplicate key" in error_msg:
                logger.warning("Duplicate medicine name: %s", item_in.name)
                raise HTTPException(
                    status_code=409, detail="Medicine name already exists"
                )
            logger.error("Failed to create item with inventory: %s", e)
            raise _classify_db_error(e)
    else:
        # ── Medicine only, no inventory row ──────────────────────────────
        try:
            res = db.fetch_one(
                med_query,
                (
                    item_in.name,
                    item_in.category,
                    item_in.unit,
                    item_in.reorder_level,
                    item_in.supplier,
                ),
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "unique constraint" in error_msg or "duplicate key" in error_msg:
                logger.warning("Duplicate medicine name: %s", item_in.name)
                raise HTTPException(
                    status_code=409, detail="Medicine name already exists"
                )
            logger.error("Failed to create item: %s", e)
            raise _classify_db_error(e)

        if not res:
            raise HTTPException(
                status_code=500, detail="Failed to create medicine"
            )
        item_id = res["item_id"]
        updated_at = res["updated_at"]

    return {
        "id": item_id,
        "name": item_in.name,
        "category": item_in.category,
        "quantity": item_in.quantity,
        "unit": item_in.unit,
        "reorder_level": item_in.reorder_level,
        "supplier": item_in.supplier,
        "last_updated": updated_at,
    }


@router.put("/{item_id}", response_model=SupplyItem, summary="Update a supply item")
async def update_item(item_id: int, item_in: SupplyItemCreate):
    """Update the catalogue entry for an existing medicine."""
    update_query = """
    UPDATE medicines
    SET name = %s, category = %s, unit = %s,
        reorder_level = %s, supplier = %s, updated_at = NOW()
    WHERE item_id = %s
    RETURNING updated_at
    """
    try:
        updated = db.fetch_one(
            update_query,
            (
                item_in.name,
                item_in.category,
                item_in.unit,
                item_in.reorder_level,
                item_in.supplier,
                item_id,
            ),
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "unique constraint" in error_msg or "duplicate key" in error_msg:
            logger.warning("Duplicate medicine name on update: %s", item_in.name)
            raise HTTPException(
                status_code=409, detail="Medicine name already exists"
            )
        logger.error("Failed to update item %d: %s", item_id, e)
        raise _classify_db_error(e)

    if not updated:
        raise HTTPException(status_code=404, detail="Item not found")

    # Aggregate the total quantity across all PHC inventory rows
    qty_query = (
        "SELECT COALESCE(SUM(quantity), 0) AS quantity "
        "FROM inventory WHERE item_id = %s"
    )
    qty_res = db.fetch_one(qty_query, (item_id,))

    return {
        "id": item_id,
        "name": item_in.name,
        "category": item_in.category,
        "quantity": int(qty_res["quantity"]) if qty_res else 0,
        "unit": item_in.unit,
        "reorder_level": item_in.reorder_level,
        "supplier": item_in.supplier,
        "last_updated": updated["updated_at"],
    }


@router.delete("/{item_id}", status_code=204, summary="Delete a supply item")
async def delete_item(item_id: int):
    """Delete a medicine from the catalogue.

    Returns 400 if inventory records still reference the item.
    """
    try:
        # Prevent deleting a medicine that still has inventory rows
        check_inv = "SELECT COUNT(*) AS cnt FROM inventory WHERE item_id = %s"
        cnt_res = db.fetch_one(check_inv, (item_id,))
        if cnt_res and int(cnt_res["cnt"]) > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete — inventory records reference this item. "
                       "Remove inventory first.",
            )

        check_med = "SELECT item_id FROM medicines WHERE item_id = %s"
        if not db.fetch_one(check_med, (item_id,)):
            raise HTTPException(status_code=404, detail="Item not found")

        del_query = "DELETE FROM medicines WHERE item_id = %s"
        db.execute_query(del_query, (item_id,))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete item %d: %s", item_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete item")


# ── PHC Stock Endpoints ──────────────────────────────────────────────────────

@router.post(
    "/update",
    tags=["PHC Stock"],
    summary="Log a stock update for a PHC",
    response_description="Acknowledgement that the update was received",
)
async def update_stock(
    update: StockUpdate,
    x_client_operation_id: str | None = Header(None, alias="X-Client-Operation-Id"),
):
    """Log a medicine stock update for a PHC with exact-once idempotency deduplication.

    Performs an UPSERT into inventory **and** logs an
    ``inventory_transactions`` record, all inside one transaction.
    """
    client_op_id = update.client_operation_id or x_client_operation_id
    if client_op_id:
        try:
            check_op = db.fetch_one(
                "SELECT operation_id, response_payload FROM processed_operations WHERE operation_id = %s",
                (client_op_id,),
            )
            if check_op:
                logger.info("Idempotent deduplication hit for operation %s", client_op_id)
                if check_op.get("response_payload"):
                    return json.loads(check_op["response_payload"])
                return {
                    "status": "success",
                    "message": "Stock logged (cached idempotency ack)",
                    "client_operation_id": client_op_id,
                }
        except Exception as e:
            logger.warning("Idempotency check query failed: %s", e)

    # 1. Verify PHC exists
    _verify_phc_exists(update.phc_id)

    # 2. Lookup medicine by name
    try:
        med_query = "SELECT item_id FROM medicines WHERE name = %s"
        med = db.fetch_one(med_query, (update.medicine_name,))
    except Exception as e:
        logger.error("Failed to lookup medicine '%s': %s", update.medicine_name, e)
        raise HTTPException(status_code=500, detail="Failed to lookup medicine")

    if not med:
        raise HTTPException(
            status_code=404,
            detail=f"Medicine '{update.medicine_name}' not found",
        )

    item_id = med["item_id"]

    # 3. Resolve batch number (use existing or default)
    try:
        batch_query = (
            "SELECT batch_number FROM inventory "
            "WHERE phc_id = %s AND item_id = %s LIMIT 1"
        )
        batch_res = db.fetch_one(batch_query, (update.phc_id, item_id))
    except Exception as e:
        logger.error("Failed to lookup batch: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process update")

    batch_number = batch_res["batch_number"] if batch_res else "DEFAULT_BATCH"

    # 4. UPSERT inventory + INSERT transaction (single transaction)
    upsert_inv = """
    INSERT INTO inventory (phc_id, item_id, batch_number, quantity, offline_sync_id)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (phc_id, item_id, batch_number)
    DO UPDATE SET quantity   = EXCLUDED.quantity,
                  updated_at = NOW()
    """

    insert_txn = """
    INSERT INTO inventory_transactions
        (phc_id, item_id, batch_number, transaction_type, quantity,
         reference_id, remarks, offline_sync_id)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    sync_id = client_op_id or str(uuid.uuid4())
    queries_params = [
        (
            upsert_inv,
            (update.phc_id, item_id, batch_number, update.quantity, sync_id),
        ),
        (
            insert_txn,
            (
                update.phc_id,
                item_id,
                batch_number,
                "adjusted",
                update.quantity,
                str(uuid.uuid4()),
                "PHC Stock Update via API",
                sync_id,
            ),
        ),
    ]

    try:
        db.execute_transaction(queries_params)
    except Exception as e:
        logger.error("Failed to update stock: %s", e)
        raise _classify_db_error(e)

    # 5. Record operation for exact-once deduplication
    ack_data = {
        "status": "success",
        "message": "Stock logged",
        "client_operation_id": client_op_id,
    }
    if client_op_id:
        try:
            db.execute_query(
                """
                INSERT INTO processed_operations (operation_id, endpoint, operation_type, phc_id, status_code, response_payload, created_at)
                VALUES (%s, '/api/v1/inventory/update', 'inventory_update', %s, 200, %s, NOW())
                ON CONFLICT (operation_id) DO NOTHING;
                """,
                (client_op_id, update.phc_id, json.dumps(ack_data)),
            )
        except Exception as e:
            logger.warning("Failed to record processed_operation: %s", e)

    return ack_data



@router.get(
    "/status/{phc_id}",
    tags=["PHC Stock"],
    summary="Get current stock levels for a PHC",
    response_description=(
        "A mapping of medicine name to its current stock details "
        "(quantity, unit, reorder_level, status)"
    ),
)
async def get_phc_stock_status(phc_id: str):
    """Return the current stock levels for all medicines at a given PHC.

    Uses a single LEFT JOIN to avoid N+1 queries.  Unknown PHC IDs
    return default (zero) stock values rather than a 404 so the
    frontend can render an empty state.
    """
    try:
        query = """
        SELECT
            m.name,
            COALESCE(SUM(i.quantity), 0) AS quantity,
            m.unit,
            m.reorder_level
        FROM medicines m
        LEFT JOIN inventory i ON m.item_id = i.item_id AND i.phc_id = %s
        GROUP BY m.name, m.unit, m.reorder_level
        ORDER BY m.name
        """
        records = db.fetch_all(query, (phc_id,))
    except Exception as e:
        logger.error("Failed to fetch stock for %s: %s", phc_id, e)
        raise HTTPException(
            status_code=500, detail="Failed to retrieve stock status"
        )

    stock_dict: dict[str, dict] = {}
    last_updated_date = datetime.now(timezone.utc).isoformat()

    for r in records:
        q = int(r["quantity"])
        rl = int(r["reorder_level"])

        if q == 0:
            status = "critical"
        elif q <= rl:
            status = "low"
        else:
            status = "adequate"

        stock_dict[r["name"]] = {
            "quantity": q,
            "unit": r["unit"],
            "reorder_level": rl,
            "status": status,
        }

    return {
        "phc_id": phc_id.upper(),
        "stock": stock_dict,
        "last_updated": last_updated_date,
    }
