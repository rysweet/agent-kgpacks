"""Shared fixtures for WikiGR tests."""

import shutil
from pathlib import Path

import kuzu
import pytest


@pytest.fixture
def in_memory_db():
    """Provide an in-memory Kuzu database for fast tests."""
    db = kuzu.Database()
    conn = kuzu.Connection(db)
    yield conn


@pytest.fixture
def schema_db(tmp_path):
    """Provide a temp database with schema created."""
    from bootstrap.schema.ryugraph_schema import create_schema

    db_path = str(tmp_path / "test.db")
    create_schema(db_path, drop_existing=True)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    yield conn
    # Cleanup handled by tmp_path
