"""
LadybugDB database connection management.

Provides singleton connection manager with dependency injection for FastAPI.
"""

import contextlib
import logging
import threading
from collections.abc import Generator
from pathlib import Path

import real_ladybug as kuzu

from backend.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Singleton connection manager for LadybugDB database.

    Keeps a single Database instance (thread-safe) and creates a new
    Connection per request to avoid sharing a non-thread-safe connection
    across concurrent async handlers.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize connection manager."""
        if self._initialized:
            return

        # Always read from settings (can be overridden by env var)
        self._database = None
        self._initialized = True

    @property
    def db_path(self):
        """Get database path from settings (allows runtime override)."""
        return settings.database_path

    def _get_database(self) -> kuzu.Database:
        """Get or create Database instance (thread-safe singleton)."""
        if self._database is None:
            with self._lock:
                if self._database is None:
                    db_path = Path(self.db_path)

                    if not db_path.exists():
                        raise FileNotFoundError(f"Database not found: {db_path}")

                    logger.info(f"Opening LadybugDB database: {db_path}")
                    self._database = kuzu.Database(str(db_path))

        return self._database

    def get_connection(self) -> kuzu.Connection:
        """
        Create a new LadybugDB connection for each request.

        Returns:
            Fresh LadybugDB Connection instance with extensions loaded
        """
        database = self._get_database()
        logger.debug("Creating new LadybugDB connection for request")
        conn = kuzu.Connection(database)
        _load_extensions(conn)
        return conn

    def close(self):
        """Close database (release Database instance)."""
        if self._database is not None:
            self._database = None
            logger.info("Closed LadybugDB database")


def _load_extensions(conn: kuzu.Connection) -> None:
    """Load required LadybugDB extensions (vector, fts) on a connection."""
    for ext in ("VECTOR", "FTS"):
        try:
            conn.execute(f"LOAD EXTENSION {ext};")
        except Exception:
            with contextlib.suppress(Exception):
                conn.execute(f"INSTALL {ext}; LOAD EXTENSION {ext};")


# Global connection manager instance
_manager = ConnectionManager()


def get_db() -> Generator[kuzu.Connection, None, None]:
    """
    FastAPI dependency for database connection.

    Creates a fresh connection per request so concurrent async handlers
    do not share a single non-thread-safe connection.

    Yields:
        Fresh LadybugDB Connection instance
    """
    conn = _manager.get_connection()
    try:
        yield conn
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        try:
            conn.close()
        except Exception as close_err:
            logger.debug(f"Connection close error (non-fatal): {close_err}")
