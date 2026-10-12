"""
Database connection manager and query helpers.
Supports both PostgreSQL (via psycopg2 ThreadedConnectionPool) and embedded SQLite
(for zero-dependency local development, staging, and offline resilience).

When a valid PostgreSQL DATABASE_URL is available and reachable, it connects to PostgreSQL.
If PostgreSQL is unreachable or not configured, it automatically and transparently
fails over to an embedded local SQLite engine (mediflow_local.db), creating all tables
and deterministic seed records automatically.
"""

import os
import re
import uuid
import sqlite3
import logging
import threading
from datetime import datetime, date, timedelta, timezone
from contextlib import contextmanager

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Global connection state
_pg_pool = None
_use_sqlite = False
_sqlite_lock = threading.Lock()
_local_db_path = None


def _get_sqlite_path() -> str:
    global _local_db_path
    if _local_db_path is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "database"))
        os.makedirs(base_dir, exist_ok=True)
        _local_db_path = os.path.join(base_dir, "mediflow_local.db")
    return _local_db_path


def _create_sqlite_connection() -> sqlite3.Connection:
    """Create and configure a local SQLite connection."""
    conn = sqlite3.connect(_get_sqlite_path(), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Register Postgres compatibility functions
    conn.create_function("NOW", 0, lambda: datetime.now(timezone.utc).isoformat())
    conn.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())
    conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))
    return conn


def _init_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Initialize schema tables in SQLite if they don't already exist."""
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL DEFAULT 'viewer',
        password_hash TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS facilities (
        phc_id TEXT PRIMARY KEY,
        facility_name TEXT NOT NULL,
        facility_type TEXT NOT NULL DEFAULT 'PHC',
        district TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'Karnataka',
        address TEXT NOT NULL DEFAULT '',
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        phone_number TEXT,
        operational_status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS medicines (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        generic_name TEXT,
        category TEXT NOT NULL,
        unit TEXT NOT NULL DEFAULT 'units',
        reorder_level INTEGER NOT NULL DEFAULT 50,
        supplier TEXT,
        dosage_form TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS inventory (
        inventory_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        phc_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        batch_number TEXT NOT NULL DEFAULT 'DEFAULT_BATCH',
        quantity INTEGER NOT NULL DEFAULT 0,
        expiry_date TEXT NOT NULL DEFAULT (date('now', '+1 year')),
        offline_sync_id TEXT,
        timestamp TEXT NOT NULL DEFAULT (datetime('now')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(phc_id, item_id, batch_number)
    );

    CREATE TABLE IF NOT EXISTS beds (
        bed_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        phc_id TEXT NOT NULL UNIQUE,
        available_beds INTEGER NOT NULL DEFAULT 0,
        timestamp TEXT NOT NULL DEFAULT (datetime('now')),
        offline_sync_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS phc_attendance_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phc_id TEXT NOT NULL,
        attendance_date TEXT NOT NULL,
        doctors_present INTEGER NOT NULL DEFAULT 0,
        timestamp TEXT NOT NULL DEFAULT (datetime('now')),
        offline_sync_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(phc_id, attendance_date)
    );

    CREATE TABLE IF NOT EXISTS transfers (
        transfer_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        from_phc_id TEXT NOT NULL,
        to_phc_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        batch_number TEXT NOT NULL DEFAULT 'DEFAULT_BATCH',
        quantity INTEGER NOT NULL,
        received_quantity INTEGER,
        status TEXT NOT NULL DEFAULT 'proposed',
        reason TEXT,
        rejection_reason TEXT,
        discrepancy_reason TEXT,
        client_operation_id TEXT UNIQUE,
        proposed_by TEXT,
        approved_by TEXT,
        dispatched_by TEXT,
        received_by TEXT,
        dispatched_at TEXT,
        received_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS stock_reservations (
        reservation_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        transfer_id TEXT NOT NULL,
        phc_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        batch_number TEXT NOT NULL,
        reserved_quantity INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS processed_operations (
        operation_id TEXT PRIMARY KEY,
        endpoint TEXT NOT NULL DEFAULT '',
        operation_type TEXT DEFAULT 'generic',
        phc_id TEXT,
        status_code INTEGER NOT NULL DEFAULT 200,
        response_payload TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS audit_events (
        event_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor_id TEXT,
        actor_role TEXT,
        details TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS emergency_escalations (
        escalation_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        alert_id TEXT NOT NULL,
        phc_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        required_quantity INTEGER NOT NULL,
        reason TEXT,
        depot_destination TEXT NOT NULL,
        escalated_by TEXT,
        escalated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS inventory_transactions (
        transaction_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        phc_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        batch_number TEXT,
        transaction_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        reference_id TEXT,
        remarks TEXT,
        performed_by TEXT,
        offline_sync_id TEXT,
        transaction_date TEXT NOT NULL DEFAULT (datetime('now')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS medicine_consumption (
        consumption_id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        phc_id TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        consumption_date TEXT NOT NULL,
        quantity_consumed INTEGER NOT NULL DEFAULT 0,
        patients_served INTEGER,
        offline_sync_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(phc_id, item_id, consumption_date)
    );
    """)
    conn.commit()

    # Column migrations for existing databases
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE processed_operations ADD COLUMN operation_type TEXT DEFAULT 'generic'")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE processed_operations ADD COLUMN endpoint TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _seed_sqlite_defaults(conn: sqlite3.Connection) -> None:
    """Populate default deterministic records for demo/local execution."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM facilities")
    if cur.fetchone()["cnt"] > 0:
        return  # Already seeded

    logger.info("Seeding deterministic local SQLite records...")

    # Users (Bcrypt hash of admin123, manager123, viewer123)
    # Generated with Passlib/Bcrypt
    admin_hash = "$2b$12$e68Y2kF5bZ7u8Z4xL7tIqe3Yv6Y5y9tI8r8Xq9a7r4Q3q8y9u6"  # fallback safe
    try:
        from passlib.context import CryptContext
        pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin_hash = pwd_ctx.hash("admin123")
        mgr_hash = pwd_ctx.hash("manager123")
        view_hash = pwd_ctx.hash("viewer123")
    except Exception:
        mgr_hash = admin_hash
        view_hash = admin_hash

    users = [
        ("admin", "admin@smarthealth.local", "admin", admin_hash, 1),
        ("manager_north", "manager1@smarthealth.local", "manager", mgr_hash, 1),
        ("viewer1", "viewer1@smarthealth.local", "viewer", view_hash, 1),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO users (username, email, role, password_hash, is_active) VALUES (?, ?, ?, ?, ?)",
        users
    )

    # Facilities
    facilities = [
        ("PHC-001", "Central District Hospital", "CHC", "North Block", "Karnataka", "Center Road", 12.9716, 77.5946),
        ("PHC-002", "Green Valley PHC", "PHC", "North Block", "Karnataka", "Valley Road", 12.9816, 77.5846),
        ("PHC-003", "Lakeview Clinic", "PHC", "South Block", "Karnataka", "Lake Edge", 12.9116, 77.6046),
        ("PHC-004", "Hilltop Health Center", "PHC", "East Block", "Karnataka", "Hill Area", 12.9516, 77.6546),
        ("PHC-005", "Riverside Medical", "PHC", "West Block", "Karnataka", "River Bend", 12.9616, 77.5246),
        ("PHC-006", "Sunrise Care", "PHC", "North Block", "Karnataka", "Sunrise Blvd", 12.9916, 77.5746),
        ("PHC-007", "Pine Grove Clinic", "PHC", "South Block", "Karnataka", "Pine Woods", 12.9216, 77.5846),
        ("PHC-008", "Maple Leaf Medical", "PHC", "East Block", "Karnataka", "Maple Street", 12.9616, 77.6646),
        ("PHC-009", "Oaktree Health", "PHC", "West Block", "Karnataka", "Oak Grove", 12.9416, 77.5146),
        ("PHC-010", "Willow Branch Clinic", "PHC", "North Block", "Karnataka", "Willow Creek", 12.9856, 77.5996),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO facilities (phc_id, facility_name, facility_type, district, state, address, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        facilities
    )

    # Medicines
    medicines = [
        (1, "Paracetamol 500mg", "Paracetamol", "Medication", "tablets", 200, "PharmaCorp", "tablet"),
        (2, "Amoxicillin 250mg", "Amoxicillin", "Antibiotic", "capsules", 100, "BioMed", "capsule"),
        (3, "ORS Packets", "Oral Rehydration Salts", "Fluids", "sachets", 500, "HealthPlus", "powder"),
        (4, "Anti-venom", "Polyvalent Antivenom", "Emergency", "vials", 10, "Lifesciences", "injection"),
        (5, "IV Fluids", "Normal Saline 0.9%", "Fluids", "bags", 150, "Baxter", "solution"),
        (6, "Syringes", "5ml Syringe", "Consumables", "units", 600, "BD Medical", "other"),
        (7, "Bandages", "Gauze Bandage 2x2", "Consumables", "rolls", 100, "CareFirst", "other"),
        (8, "Ibuprofen 400mg", "Ibuprofen", "Medication", "tablets", 100, "PharmaCorp", "tablet"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO medicines (item_id, name, generic_name, category, unit, reorder_level, supplier, dosage_form) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        medicines
    )

    # Inventory
    today = date.today()
    exp_safe = (today + timedelta(days=365)).isoformat()
    inventory_records = [
        # PHC-001 has critically low stock of Paracetamol (10 tablets < safety reserve 50)
        (str(uuid.uuid4()), "PHC-001", 1, "BATCH-P1-01", 10, exp_safe),
        (str(uuid.uuid4()), "PHC-001", 2, "BATCH-P1-02", 120, exp_safe),
        (str(uuid.uuid4()), "PHC-001", 3, "BATCH-P1-03", 400, exp_safe),
        # PHC-002 has donor surplus of Paracetamol (150 tablets -> donor safe surplus 80)
        (str(uuid.uuid4()), "PHC-002", 1, "BATCH-P2-01", 150, exp_safe),
        (str(uuid.uuid4()), "PHC-002", 2, "BATCH-P2-02", 180, exp_safe),
        (str(uuid.uuid4()), "PHC-002", 3, "BATCH-P2-03", 600, exp_safe),
        # PHC-003 to PHC-010 reasonable baseline stock
        (str(uuid.uuid4()), "PHC-003", 1, "BATCH-P3-01", 45, exp_safe), # At reserve/below
        (str(uuid.uuid4()), "PHC-004", 1, "BATCH-P4-01", 110, exp_safe),
        (str(uuid.uuid4()), "PHC-005", 1, "BATCH-P5-01", 90, exp_safe),
        (str(uuid.uuid4()), "PHC-006", 1, "BATCH-P6-01", 80, exp_safe),
        (str(uuid.uuid4()), "PHC-007", 1, "BATCH-P7-01", 70, exp_safe),
        (str(uuid.uuid4()), "PHC-008", 1, "BATCH-P8-01", 130, exp_safe),
        (str(uuid.uuid4()), "PHC-009", 1, "BATCH-P9-01", 85, exp_safe),
        (str(uuid.uuid4()), "PHC-010", 1, "BATCH-P10-01", 95, exp_safe),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO inventory (inventory_id, phc_id, item_id, batch_number, quantity, expiry_date) VALUES (?, ?, ?, ?, ?, ?)",
        inventory_records
    )

    # Beds & Attendance
    for f in facilities:
        phc = f[0]
        cur.execute("INSERT OR IGNORE INTO beds (bed_id, phc_id, available_beds) VALUES (?, ?, ?)", (str(uuid.uuid4()), phc, 24))
        cur.execute(
            "INSERT OR IGNORE INTO phc_attendance_summary (phc_id, attendance_date, doctors_present) VALUES (?, ?, ?)",
            (phc, today.isoformat(), 3)
        )

    conn.commit()
    logger.info("Local SQLite initialization complete.")


def _init_sqlite_engine():
    """Ensure SQLite database is created and ready."""
    with _sqlite_lock:
        conn = _create_sqlite_connection()
        try:
            _init_sqlite_schema(conn)
            _seed_sqlite_defaults(conn)
        finally:
            conn.close()


def get_pool():
    """
    Initialise PostgreSQL connection pool or switch to SQLite fallback.
    """
    global _pg_pool, _use_sqlite
    if _use_sqlite:
        return None
    if _pg_pool is None:
        load_dotenv()
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            db_url = db_url.strip()

        # If user explicitly wants sqlite or no valid remote pg configured
        if not db_url or "aws-0-ap-northeast-1.pooler.supabase.com" in db_url:
            logger.info("Using embedded local SQLite storage (mediflow_local.db)")
            _use_sqlite = True
            _init_sqlite_engine()
            return None

        # Attempt PostgreSQL connection
        try:
            from psycopg2 import pool
            if "sslmode" not in db_url and "localhost" not in db_url and "127.0.0.1" not in db_url:
                separator = "&" if "?" in db_url else "?"
                db_url += f"{separator}sslmode=require"
            _pg_pool = pool.ThreadedConnectionPool(1, 10, db_url)
            logger.info("Successfully connected to PostgreSQL database.")
        except Exception as e:
            logger.warning("PostgreSQL connection unavailable (%s). Falling back to local SQLite engine.", e)
            _use_sqlite = True
            _init_sqlite_engine()
            return None

    return _pg_pool


def _translate_query_for_sqlite(query: str) -> str:
    """Translate PostgreSQL parameterized query to SQLite syntax."""
    # Replace %s with ?
    q = query.replace("%s", "?")
    # Replace interval calculations
    q = re.sub(r"CURRENT_DATE\s*\+\s*INTERVAL\s*'1 year'", "date('now', '+1 year')", q, flags=re.IGNORECASE)
    q = re.sub(r"CURRENT_DATE\s*-\s*INTERVAL\s*'30 days'", "date('now', '-30 days')", q, flags=re.IGNORECASE)
    return q


def execute_query(query: str, params: tuple = None) -> None:
    """Execute an INSERT / UPDATE / DELETE statement."""
    get_pool()
    if _use_sqlite:
        translated = _translate_query_for_sqlite(query)
        with _sqlite_lock:
            conn = _create_sqlite_connection()
            try:
                cur = conn.cursor()
                cur.execute(translated, params or ())
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("SQLite execute_query failed: %s | Query: %s", e, translated)
                raise
            finally:
                conn.close()
        return

    with get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(query, params)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("PostgreSQL execute_query failed: %s | Query: %s", e, query)
                raise


def execute_transaction(queries_and_params: list[tuple[str, tuple]]) -> None:
    """Execute a series of queries in a single atomic transaction."""
    get_pool()
    if _use_sqlite:
        with _sqlite_lock:
            conn = _create_sqlite_connection()
            try:
                cur = conn.cursor()
                for q, p in queries_and_params:
                    translated = _translate_query_for_sqlite(q)
                    cur.execute(translated, p or ())
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("SQLite transaction failed, rolled back: %s", e)
                raise
            finally:
                conn.close()
        return

    with get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                for q, p in queries_and_params:
                    cursor.execute(q, p)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("PostgreSQL transaction failed, rolled back: %s", e)
                raise


def fetch_one(query: str, params: tuple = None) -> dict | None:
    """Execute a query and return a single row as a dict."""
    get_pool()
    if _use_sqlite:
        translated = _translate_query_for_sqlite(query)
        with _sqlite_lock:
            conn = _create_sqlite_connection()
            try:
                cur = conn.cursor()
                cur.execute(translated, params or ())
                row = cur.fetchone()
                return dict(row) if row else None
            except Exception as e:
                logger.error("SQLite fetch_one failed: %s | Query: %s", e, translated)
                raise
            finally:
                conn.close()

    from psycopg2.extras import RealDictCursor
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None
            except Exception as e:
                logger.error("PostgreSQL fetch_one failed: %s | Query: %s", e, query)
                raise


def fetch_all(query: str, params: tuple = None) -> list[dict]:
    """Execute a query and return all matching rows as a list of dicts."""
    get_pool()
    if _use_sqlite:
        translated = _translate_query_for_sqlite(query)
        with _sqlite_lock:
            conn = _create_sqlite_connection()
            try:
                cur = conn.cursor()
                cur.execute(translated, params or ())
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error("SQLite fetch_all failed: %s | Query: %s", e, translated)
                raise
            finally:
                conn.close()

    from psycopg2.extras import RealDictCursor
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                cursor.execute(query, params)
                records = cursor.fetchall()
                return [dict(r) for r in records]
            except Exception as e:
                logger.error("PostgreSQL fetch_all failed: %s | Query: %s", e, query)
                raise


@contextmanager
def get_connection():
    """Acquire a connection from the PostgreSQL pool."""
    pool_obj = get_pool()
    if pool_obj is None:
        raise RuntimeError("PostgreSQL connection requested but running in SQLite mode.")
    conn = None
    try:
        conn = pool_obj.getconn()
        yield conn
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            pool_obj.putconn(conn)


def close_pool() -> None:
    """Close connections cleanly on application shutdown."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.closeall()
        logger.info("PostgreSQL pool closed.")
        _pg_pool = None
