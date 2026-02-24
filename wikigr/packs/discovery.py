"""Pack discovery and validation.

This module provides functions to discover installed knowledge packs and
validate their structure.
"""

from pathlib import Path

from wikigr.packs.manifest import load_manifest
from wikigr.packs.models import PackInfo
from wikigr.packs.validator import validate_pack_structure


def is_valid_pack(pack_dir: Path) -> bool:
    """Check if directory contains a valid knowledge pack.

    A valid pack must have:
    - manifest.json (valid JSON with required fields)
    - pack.db/ (Kuzu database directory)
    - skill.md (Claude Code skill file)
    - kg_config.json (KG Agent configuration)

    Args:
        pack_dir: Path to potential pack directory

    Returns:
        True if pack_dir contains a valid pack, False otherwise
    """
    if not pack_dir.is_dir():
        return False

    errors = validate_pack_structure(pack_dir)
    return len(errors) == 0


def discover_packs(packs_dir: Path = Path.home() / ".wikigr/packs") -> list[PackInfo]:
    """Discover all installed knowledge packs.

    Scans the packs directory for valid pack subdirectories and returns
    PackInfo objects for each discovered pack.

    Args:
        packs_dir: Directory containing installed packs
                   (default: ~/.wikigr/packs)

    Returns:
        List of PackInfo objects for all valid packs found
        (empty list if packs_dir doesn't exist or contains no valid packs)
    """
    if not packs_dir.exists() or not packs_dir.is_dir():
        return []

    packs = []

    # Scan for subdirectories that are valid packs
    for item in packs_dir.iterdir():
        if not item.is_dir():
            continue

        if not is_valid_pack(item):
            continue

        # Load pack information
        try:
            manifest = load_manifest(item)
            skill_path = item / "skill.md"

            pack_info = PackInfo(
                name=manifest.name,
                version=manifest.version,
                path=item.resolve(),  # Make absolute
                manifest=manifest,
                skill_path=skill_path.resolve(),  # Make absolute
            )
            packs.append(pack_info)
        except Exception:
            # Skip packs that fail to load
            continue

    return packs
