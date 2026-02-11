"""
Kuzu database connection management.

Provides singleton connection manager with dependency injection for FastAPI.
"""

import logging
import threading
from collections.abc import Generator
from pathlib import Path

import kuzu

from backend.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Singleton connection manager for Kuzu database.

    Ensures single Database instance is shared across application.
    Connections are thread-safe and reusable.
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
        self._connection = None
        self._initialized = True

    @property
    def db_path(self):
        """Get database path from settings (allows runtime override)."""
        return settings.database_path

    def _get_database(self) -> kuzu.Database:
        """Get or create Database instance."""
        if self._database is None:
            db_path = Path(self.db_path)

            if not db_path.exists():
                raise FileNotFoundError(f"Database not found: {db_path}")

            logger.info(f"Opening Kuzu database: {db_path}")
            self._database = kuzu.Database(str(db_path))

        return self._database

    def get_connection(self) -> kuzu.Connection:
        """
        Get Kuzu connection.

        Returns:
            Kuzu Connection instance
        """
        if self._connection is None:
            database = self._get_database()
            self._connection = kuzu.Connection(database)
            logger.debug("Created new Kuzu connection")

        return self._connection

    def close(self):
        """Close database connection."""
        if self._connection is not None:
            self._connection = None
            logger.info("Closed Kuzu connection")

        if self._database is not None:
            self._database = None
            logger.info("Closed Kuzu database")


# Global connection manager instance
_manager = ConnectionManager()


def get_db() -> Generator[kuzu.Connection, None, None]:
    """
    FastAPI dependency for database connection.

    Yields:
        Kuzu Connection instance
    """
    conn = _manager.get_connection()
    try:
        yield conn
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
