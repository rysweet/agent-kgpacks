"""
Pytest configuration and shared fixtures for backend tests.
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_db_path():
    """Path to test Kuzu database."""
    # Use existing test database from project root
    # Project root is 2 levels up from backend/tests/
    base_path = Path(__file__).parent.parent.parent
    db_path = base_path / "data" / "test_10_articles.db"

    if not db_path.exists():
        pytest.skip(f"Test database not found at {db_path}")

    return str(db_path)


@pytest.fixture(scope="session")
def setup_test_env(test_db_path):
    """Setup test environment with database path and disabled rate limiting."""
    # Set database path in config for tests
    os.environ["WIKIGR_DATABASE_PATH"] = test_db_path
    # Disable rate limiting during tests to avoid 429 responses
    os.environ["WIKIGR_RATE_LIMIT_ENABLED"] = "false"
    yield
    # Cleanup
    if "WIKIGR_DATABASE_PATH" in os.environ:
        del os.environ["WIKIGR_DATABASE_PATH"]
    if "WIKIGR_RATE_LIMIT_ENABLED" in os.environ:
        del os.environ["WIKIGR_RATE_LIMIT_ENABLED"]


@pytest.fixture
def connection_manager(setup_test_env):  # noqa: ARG001
    """Create connection manager instance."""
    from backend.config import settings
    from backend.db.connection import ConnectionManager

    # Override database path in settings
    settings.database_path = os.environ.get("WIKIGR_DATABASE_PATH")

    # Reset singleton instance to force reinitialization
    ConnectionManager._instance = None

    manager = ConnectionManager()
    yield manager

    # Cleanup
    manager.close()


@pytest.fixture
def client(setup_test_env):  # noqa: ARG001
    """Create FastAPI test client."""
    # Import app after environment is set up
    from backend.config import settings
    from backend.db.connection import ConnectionManager
    from backend.main import app

    # Override database path in settings
    settings.database_path = os.environ.get("WIKIGR_DATABASE_PATH")

    # Reset connection manager singleton
    ConnectionManager._instance = None

    return TestClient(app)


@pytest.fixture
def sample_article_title():
    """Sample article title for testing."""
    return "Artificial intelligence"


@pytest.fixture
def sample_category():
    """Sample category for testing."""
    # Query actual category from test database
    return "Computer Science"


@pytest.fixture
def invalid_article_title():
    """Non-existent article title for 404 tests."""
    return "NonExistentArticle12345XYZ"
