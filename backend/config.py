"""
Configuration management for WikiGR backend.

Loads configuration from parent config.yaml and provides settings.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    api_title: str = "WikiGR Visualization API"
    api_version: str = "1.0.0"
    api_description: str = "RESTful API for Wikipedia knowledge graph queries"

    # Server Settings
    host: str = "127.0.0.1"
    port: int = 8000

    # CORS Settings
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Database Settings
    database_path: str = ""

    model_config = {"env_prefix": "WIKIGR_"}


def load_config() -> dict[str, Any]:
    """
    Load configuration from parent config.yaml.

    Returns:
        Configuration dictionary
    """
    # Find config.yaml in project root (one level above backend/)
    backend_dir = Path(__file__).parent
    config_path = backend_dir.parent / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return config


def get_settings() -> Settings:
    """
    Get application settings.

    Returns:
        Settings instance with database path from config.yaml
    """
    import os

    # Check if database path is overridden by environment variable
    env_db_path = os.environ.get("WIKIGR_DATABASE_PATH")

    if env_db_path:
        settings = Settings()
        settings.database_path = env_db_path
        return settings

    # Load from config file
    config = load_config()

    # Get database path from config
    db_path = config.get("database", {}).get("path", "data/wikigr.db")

    # Resolve relative to project root
    backend_dir = Path(__file__).parent
    project_root = backend_dir.parent
    absolute_db_path = project_root / db_path

    settings = Settings()
    settings.database_path = str(absolute_db_path)

    return settings


# Global settings instance
settings = get_settings()
