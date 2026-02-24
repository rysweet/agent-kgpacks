"""Pack structure validation.

This module provides functions to validate the complete structure of a
knowledge pack, including directory layout, required files, and content validity.
"""

import json
from pathlib import Path

from wikigr.packs.manifest import load_manifest, validate_manifest


def validate_pack_structure(pack_dir: Path) -> list[str]:
    """Validate complete pack structure.

    Checks:
    - manifest.json exists and is valid
    - pack.db directory exists (Kuzu database)
    - skill.md exists
    - kg_config.json exists and is valid JSON
    - Optional: eval/ directory and README.md

    Args:
        pack_dir: Path to pack directory

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check manifest.json
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        errors.append("Required file missing: manifest.json")
    else:
        # Validate manifest content
        try:
            manifest = load_manifest(pack_dir)
            manifest_errors = validate_manifest(manifest)
            errors.extend(manifest_errors)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in manifest.json: {e}")
        except Exception as e:
            errors.append(f"Error loading manifest.json: {e}")

    # Check pack.db (must be a directory for Kuzu)
    pack_db_path = pack_dir / "pack.db"
    if not pack_db_path.exists():
        errors.append("Required database missing: pack.db")
    elif not pack_db_path.is_dir():
        errors.append("pack.db must be a directory (Kuzu database)")

    # Check skill.md
    skill_path = pack_dir / "skill.md"
    if not skill_path.exists():
        errors.append("Required file missing: skill.md")

    # Check kg_config.json
    kg_config_path = pack_dir / "kg_config.json"
    if not kg_config_path.exists():
        errors.append("Required file missing: kg_config.json")
    else:
        # Validate it's valid JSON
        try:
            with open(kg_config_path) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in kg_config.json: {e}")

    # Optional files/directories (no error if missing)
    # - README.md
    # - eval/

    return errors
