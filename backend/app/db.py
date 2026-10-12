"""
PostgreSQL connection pool and query helpers.

Provides thread-safe connection pooling via psycopg2's
ThreadedConnectionPool, along with convenience functions for
executing queries, fetching data, and running multi-statement
transactions.

All queries use parameterized SQL.  Connections are always returned
to the pool regardless of success or failure.
"""

import os
import logging
from contextlib import contextmanager

from psycopg2 import pool, DatabaseError, InterfaceError
from psycopg2.extras import RealDictCursor, register_uuid
from dotenv import load_dotenv

register_uuid()

logger = logging.getLogger(__name__)

# Global connection pool — initialised lazily on first use.
_connection_pool = None


def get_pool():
    """
    Initialise and return a threaded PostgreSQL connection pool.

    Reads the ``DATABASE_URL`` environment variable (loaded via
    ``python-dotenv``).  Falls back to a placeholder that reminds
    the developer to configure Supabase credentials.

    Supabase requires SSL connections, so ``sslmode=require`` is
    appended automatically when it is not already present in the URL.
    """
    global _connection_pool
    if _connection_pool is None:
        load_dotenv()
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            db_url = db_url.strip()

        if not db_url:
            db_url = (
                "postgresql://postgres.podedwtxajduajsjqzar:orv%26nj0yer%21"
                "@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
            )
            logger.warning(
                "DATABASE_URL not found in environment; using fallback. "
                "Set DATABASE_URL in your .env with your Supabase credentials."
            )

        # Supabase requires SSL — ensure sslmode is set
        if "sslmode" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url += f"{separator}sslmode=require"

        try:
            _connection_pool = pool.ThreadedConnectionPool(1, 20, db_url)
            if _connection_pool:
                logger.info("Successfully created PostgreSQL connection pool (Supabase)")
        except DatabaseError as e:
            logger.error("Error creating connection pool: %s", e)
            raise
    return _connection_pool


@contextmanager
def get_connection():
    """
    Context manager — acquire a connection from the pool, yield it,
    and guarantee it is returned afterwards.

    On any exception the connection is rolled back before re-raising.
    Only genuine database errors are logged here; application-level
    exceptions (e.g. HTTPException) propagate silently so callers can
    handle them without misleading log noise.
    """
    conn_pool = get_pool()
    conn = None
    try:
        conn = conn_pool.getconn()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        # Log only database-layer errors; let app exceptions propagate quietly.
        if isinstance(e, (DatabaseError, InterfaceError)):
            logger.error("Database error: %s", e)
        raise
    finally:
        if conn:
            conn_pool.putconn(conn)


def execute_query(query: str, params: tuple = None) -> None:
    """
    Execute an INSERT / UPDATE / DELETE and commit.

    Rolls back automatically on failure.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(query, params)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(
                    "Failed to execute query: %s | Error: %s", query, e
                )
                raise


def execute_transaction(queries_and_params: list[tuple[str, tuple]]) -> None:
    """
    Execute a series of queries inside **one** transaction.

    Commits only when every statement succeeds.  Rolls back entirely
    on any failure.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                for query, params in queries_and_params:
                    cursor.execute(query, params)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("Transaction failed, rolled back. Error: %s", e)
                raise


def fetch_one(query: str, params: tuple = None) -> dict | None:
    """
    Execute a SELECT and return a single row as a ``dict``.

    Returns ``None`` when no row matches.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                cursor.execute(query, params)
                record = cursor.fetchone()
                return dict(record) if record else None
            except Exception as e:
                logger.error(
                    "Failed to fetch one: %s | Error: %s", query, e
                )
                raise


def fetch_all(query: str, params: tuple = None) -> list[dict]:
    """
    Execute a SELECT and return all rows as a list of ``dict``s.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                cursor.execute(query, params)
                records = cursor.fetchall()
                return [dict(record) for record in records]
            except Exception as e:
                logger.error(
                    "Failed to fetch all: %s | Error: %s", query, e
                )
                raise


def close_pool() -> None:
    """
    Close every connection in the pool.

    Called during application shutdown via the FastAPI lifespan hook.
    """
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        logger.info("PostgreSQL connection pool closed.")
        _connection_pool = None
