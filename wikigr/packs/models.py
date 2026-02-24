"""Pack information data models.

This module provides data models for pack discovery and registry operations.
"""

from dataclasses import dataclass
from pathlib import Path

from wikigr.packs.manifest import PackManifest


@dataclass
class PackInfo:
    """Information about an installed knowledge pack.

    Attributes:
        name: Pack name (e.g., "physics-expert")
        version: Semantic version (e.g., "1.0.0")
        path: Absolute path to pack directory
        manifest: Complete PackManifest object
        skill_path: Absolute path to skill.md file
    """

    name: str
    version: str
    path: Path
    manifest: PackManifest
    skill_path: Path

    def __post_init__(self):
        """Validate paths are absolute."""
        if not self.path.is_absolute():
            raise ValueError(f"Pack path must be absolute: {self.path}")
        if not self.skill_path.is_absolute():
            raise ValueError(f"Skill path must be absolute: {self.skill_path}")
