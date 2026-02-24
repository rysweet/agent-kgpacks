"""Pack registry for managing installed knowledge packs.

This module provides the PackRegistry class for discovering, tracking, and
accessing installed knowledge packs.
"""

from pathlib import Path

from wikigr.packs.discovery import discover_packs
from wikigr.packs.models import PackInfo


class PackRegistry:
    """Registry of installed knowledge packs.

    The registry discovers and tracks all valid packs in the packs directory,
    providing quick access to pack information and metadata.

    Attributes:
        packs_dir: Directory containing installed packs
        packs: Dictionary mapping pack names to PackInfo objects
    """

    def __init__(self, packs_dir: Path = Path.home() / ".wikigr/packs"):
        """Initialize pack registry.

        Args:
            packs_dir: Directory containing installed packs
                       (default: ~/.wikigr/packs)
        """
        self.packs_dir = packs_dir
        self.packs: dict[str, PackInfo] = {}
        self.refresh()

    def refresh(self) -> None:
        """Refresh pack registry from filesystem.

        Scans the packs directory and updates the internal registry with
        all discovered packs. This method is called automatically on
        initialization and can be called manually to pick up new packs.
        """
        discovered = discover_packs(self.packs_dir)
        self.packs = {pack.name: pack for pack in discovered}

    def get_pack(self, name: str) -> PackInfo | None:
        """Get pack by name.

        Args:
            name: Pack name (e.g., "physics-expert")

        Returns:
            PackInfo object if pack exists, None otherwise
        """
        return self.packs.get(name)

    def list_packs(self) -> list[PackInfo]:
        """List all registered packs.

        Returns:
            List of PackInfo objects for all packs in the registry,
            sorted by name
        """
        return sorted(self.packs.values(), key=lambda p: p.name)

    def has_pack(self, name: str) -> bool:
        """Check if pack is registered.

        Args:
            name: Pack name (e.g., "physics-expert")

        Returns:
            True if pack exists in registry, False otherwise
        """
        return name in self.packs

    def count(self) -> int:
        """Get number of registered packs.

        Returns:
            Number of packs in the registry
        """
        return len(self.packs)
