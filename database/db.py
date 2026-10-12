import os
import logging
from contextlib import contextmanager
from psycopg2 import pool, DatabaseError
from psycopg2.extras import RealDictCursor, register_uuid
from dotenv import load_dotenv

register_uuid()

logger = logging.getLogger(__name__)

# Global connection pool
_connection_pool = None

def get_pool():
    """
    Initialize and return a threaded PostgreSQL connection pool.
    Reads connection details from the DATABASE_URL environment variable.

    Supabase requires SSL connections, so ``sslmode=require`` is
    appended automatically when it is not already present in the URL.
    """
    global _connection_pool
    if _connection_pool is None:
        # Load environment variables automatically
        load_dotenv()
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            db_url = db_url.strip()

        if not db_url:
            db_url = (
                "postgresql://postgres.podedwtxajduajsjqzar:orv%26nj0yer%21"
                "@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
            )

        # Supabase requires SSL — ensure sslmode is set
        if "sslmode" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url += f"{separator}sslmode=require"

        try:
            # Using ThreadedConnectionPool to handle concurrent web requests (FastAPI) properly
            _connection_pool = pool.ThreadedConnectionPool(1, 20, db_url)
            if _connection_pool:
                logger.info("Successfully created PostgreSQL connection pool (Supabase)")
        except DatabaseError as e:
            logger.error(f"Error creating connection pool: {e}")
            raise
    return _connection_pool

@contextmanager
def get_connection():
    """
    Context manager to acquire a database connection from the pool
    and safely return it when done. Also handles transactions.
    """
    conn_pool = get_pool()
    conn = None
    try:
        conn = conn_pool.getconn()
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn_pool.putconn(conn)

def execute_query(query: str, params: tuple = None) -> None:
    """
    Execute an INSERT, UPDATE, or DELETE query and commit the transaction.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(query, params)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to execute query: {query}. Error: {e}")
                raise

def fetch_one(query: str, params: tuple = None) -> dict:
    """
    Execute a SELECT query and fetch a single record as a dictionary.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                cursor.execute(query, params)
                record = cursor.fetchone()
                return dict(record) if record else None
            except Exception as e:
                logger.error(f"Failed to fetch one record: {query}. Error: {e}")
                raise

def fetch_all(query: str, params: tuple = None) -> list:
    """
    Execute a SELECT query and fetch all records as a list of dictionaries.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            try:
                cursor.execute(query, params)
                records = cursor.fetchall()
                return [dict(record) for record in records]
            except Exception as e:
                logger.error(f"Failed to fetch records: {query}. Error: {e}")
                raise

def close_pool():
    """
    Close all connections in the pool gracefully.
    """
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        logger.info("PostgreSQL connection pool closed.")
        _connection_pool = None
