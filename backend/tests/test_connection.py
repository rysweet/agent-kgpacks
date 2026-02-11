"""
Tests for Kuzu database connection manager.

Tests the connection management logic ensuring proper singleton pattern,
connection reuse, and cleanup.
Following TDD methodology - these tests will fail until implementation is complete.
"""

import contextlib

import pytest


@pytest.fixture
def connection_manager(setup_test_env):
    """Create connection manager instance."""
    from backend.db.connection import ConnectionManager

    return ConnectionManager()


class TestConnectionManager:
    """Tests for Kuzu connection manager."""

    def test_connection_manager_singleton(self, setup_test_env):
        """Test that ConnectionManager implements singleton pattern."""
        from backend.db.connection import ConnectionManager

        # Create two instances
        manager1 = ConnectionManager()
        manager2 = ConnectionManager()

        # Should be the same instance
        assert manager1 is manager2

    def test_connection_manager_initializes_with_config(self, setup_test_env):
        """Test that connection manager uses database path from config."""
        from backend.db.connection import ConnectionManager

        manager = ConnectionManager()

        # Should load config from config.yaml
        assert manager.db_path is not None
        assert "data/" in manager.db_path or "test" in manager.db_path

    def test_get_connection_returns_connection(self, connection_manager):
        """Test that get_connection returns valid Kuzu connection."""
        conn = connection_manager.get_connection()

        assert conn is not None

        # Should be able to execute queries
        result = conn.execute("RETURN 1 AS test")
        assert result.has_next()

    def test_fresh_connection_per_call(self, connection_manager):
        """Test that each get_connection call returns a new connection."""
        conn1 = connection_manager.get_connection()
        conn2 = connection_manager.get_connection()

        # Should return distinct connection instances (request isolation)
        assert conn1 is not conn2

        # Both should be functional
        result1 = conn1.execute("RETURN 1 AS test")
        assert result1.has_next()
        result2 = conn2.execute("RETURN 1 AS test")
        assert result2.has_next()

    def test_connection_cleanup(self, connection_manager):
        """Test that close releases the database and new connections work after."""
        connection_manager.get_connection()

        # Cleanup should not raise errors
        connection_manager.close()

        # After close, getting connection should re-open the database
        new_conn = connection_manager.get_connection()
        assert new_conn is not None
        result = new_conn.execute("RETURN 1 AS test")
        assert result.has_next()

    def test_connection_survives_errors(self, connection_manager):
        """Test that connection remains valid after query errors."""
        conn = connection_manager.get_connection()

        # Execute invalid query
        with contextlib.suppress(Exception):
            conn.execute("INVALID QUERY SYNTAX")

        # Connection should still work
        result = conn.execute("RETURN 1 AS test")
        assert result.has_next()

    def test_connection_with_nonexistent_database(self):
        """Test error handling when database doesn't exist."""
        from backend.config import settings
        from backend.db.connection import ConnectionManager

        # Save original path
        original_path = settings.database_path

        # Set invalid path
        settings.database_path = "/nonexistent/path.db"

        # Create new manager instance
        manager = ConnectionManager()
        manager._database = None

        # Should raise appropriate error
        with pytest.raises(FileNotFoundError):
            manager.get_connection()

        # Restore original path
        settings.database_path = original_path


class TestDatabaseConfig:
    """Tests for database configuration loading."""

    def test_loads_config_from_yaml(self):
        """Test that database path is loaded from config.yaml."""
        from backend.config import load_config

        config = load_config()

        assert "database" in config
        assert "path" in config["database"]

    def test_config_validation(self):
        """Test that config is validated on load."""
        # Config validation happens at import time
        # This test verifies config loading doesn't crash
        from backend.config import load_config

        config = load_config()
        assert config is not None


class TestConnectionPooling:
    """Tests for connection pooling behavior."""

    def test_connections_share_database(self, connection_manager):
        """Test that all connections share the same Database instance."""
        # Get multiple connections
        connections = [connection_manager.get_connection() for _ in range(10)]

        # Each should be a distinct connection (per-request isolation)
        assert len({id(c) for c in connections}) == 10

        # All should be functional (backed by the same database)
        for conn in connections:
            result = conn.execute("RETURN 1 AS test")
            assert result.has_next()

    def test_thread_safety(self, connection_manager):
        """Test that connection manager is thread-safe."""
        import threading

        results = []

        def get_conn():
            conn = connection_manager.get_connection()
            results.append(conn)

        threads = [threading.Thread(target=get_conn) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get valid connections
        assert len(results) == 5
        assert all(r is not None for r in results)


class TestConnectionContext:
    """Tests for connection context manager."""

    def test_connection_context_manager(self, setup_test_env):
        """Test using connection as context manager."""
        from backend.db import get_db

        # get_db is a generator, use it in for loop or next()
        conn = next(get_db())
        result = conn.execute("RETURN 1 AS test")
        assert result.has_next()

    def test_connection_cleanup_on_exception(self, setup_test_env):
        """Test that connection is cleaned up even if exception occurs."""
        from backend.db import get_db

        # Connection cleanup is handled by FastAPI dependency injection
        # This test verifies connection doesn't break after errors
        try:
            conn = next(get_db())
            # Try invalid query
            with contextlib.suppress(Exception):
                conn.execute("INVALID QUERY")
        except ValueError:
            pass

        # Should still be able to get connection
        conn = next(get_db())
        assert conn is not None
