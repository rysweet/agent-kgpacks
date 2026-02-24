"""Pack installer for installing, uninstalling, and updating packs.

This module provides the PackInstaller class for managing pack installations.
"""

import shutil
import tempfile
import urllib.request
from pathlib import Path

from wikigr.packs.distribution import unpackage_pack
from wikigr.packs.manifest import load_manifest
from wikigr.packs.models import PackInfo


class PackInstaller:
    """Installer for knowledge packs.

    Handles installation, uninstallation, and updates of knowledge packs.

    Attributes:
        install_dir: Base directory for pack installations (default: ~/.wikigr/packs)
    """

    def __init__(self, install_dir: Path | None = None):
        """Initialize pack installer.

        Args:
            install_dir: Base directory for pack installations.
                        Defaults to ~/.wikigr/packs if not specified.
        """
        self.install_dir = install_dir or (Path.home() / ".wikigr/packs")

    def install_from_file(self, archive_path: Path) -> PackInfo:
        """Install pack from .tar.gz file.

        Args:
            archive_path: Path to pack archive file

        Returns:
            PackInfo for installed pack

        Raises:
            FileNotFoundError: If archive doesn't exist
            ValueError: If pack validation fails
            tarfile.TarError: If archive is invalid
        """
        # Unpackage to install directory
        pack_path = unpackage_pack(archive_path, self.install_dir)

        # Load manifest and create PackInfo
        manifest = load_manifest(pack_path)
        pack_info = PackInfo(
            name=manifest.name,
            version=manifest.version,
            path=pack_path,
            manifest=manifest,
            skill_path=pack_path / "skill.md",
        )

        return pack_info

    def install_from_url(self, url: str) -> PackInfo:
        """Install pack from URL (download then install).

        Args:
            url: URL to pack archive (.tar.gz)

        Returns:
            PackInfo for installed pack

        Raises:
            urllib.error.URLError: If download fails
            FileNotFoundError: If downloaded file not found
            ValueError: If pack validation fails
        """
        # Download to temporary file
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            # Download pack archive
            urllib.request.urlretrieve(url, tmp_path)

            # Install from downloaded file
            return self.install_from_file(tmp_path)
        finally:
            # Cleanup temporary file
            if tmp_path.exists():
                tmp_path.unlink()

    def uninstall(self, pack_name: str) -> bool:
        """Remove installed pack.

        Args:
            pack_name: Name of pack to uninstall

        Returns:
            True if pack was uninstalled, False if pack wasn't installed
        """
        pack_path = self.install_dir / pack_name

        if not pack_path.exists():
            return False

        # Remove pack directory
        shutil.rmtree(pack_path)
        return True

    def update(self, pack_name: str, archive_path: Path) -> PackInfo:
        """Update existing pack (preserves eval results).

        Args:
            pack_name: Name of pack to update
            archive_path: Path to new pack archive

        Returns:
            PackInfo for updated pack

        Raises:
            FileNotFoundError: If pack not installed or archive doesn't exist
            ValueError: If new pack validation fails
        """
        pack_path = self.install_dir / pack_name

        if not pack_path.exists():
            raise FileNotFoundError(f"Pack not installed: {pack_name}")

        # Preserve eval results if they exist
        eval_results_dir = pack_path / "eval" / "results"
        saved_results = None

        if eval_results_dir.exists():
            # Copy eval results to temp location
            with tempfile.TemporaryDirectory() as tmp_dir:
                saved_results = Path(tmp_dir) / "results"
                shutil.copytree(eval_results_dir, saved_results)

                # Install new version (this will remove old installation)
                pack_info = self.install_from_file(archive_path)

                # Restore eval results
                new_eval_dir = pack_info.path / "eval"
                new_eval_dir.mkdir(exist_ok=True)
                new_results_dir = new_eval_dir / "results"

                if new_results_dir.exists():
                    shutil.rmtree(new_results_dir)

                shutil.copytree(saved_results, new_results_dir)

                return pack_info
        else:
            # No eval results to preserve, just install new version
            return self.install_from_file(archive_path)
