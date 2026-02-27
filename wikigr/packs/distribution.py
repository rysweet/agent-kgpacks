"""Pack distribution - packaging and unpackaging operations.

This module provides functions for creating distributable pack archives (.tar.gz)
and extracting them for installation.
"""

import tarfile
import tempfile
from pathlib import Path

from wikigr.packs.manifest import load_manifest
from wikigr.packs.validator import validate_pack_structure


def _should_exclude(path: Path, base_dir: Path) -> bool:
    """Check if a path should be excluded from packaging.

    Excludes:
    - __pycache__ directories and .pyc files
    - Hidden files/directories starting with .
    - cache/ directory
    - Files ending with .tmp, .cache, .log

    Args:
        path: Path to check
        base_dir: Base pack directory

    Returns:
        True if path should be excluded, False otherwise
    """
    # Get relative path from base
    try:
        rel_path = path.relative_to(base_dir)
    except ValueError:
        return False

    # Check parts for excluded patterns
    for part in rel_path.parts:
        if part == "__pycache__":
            return True
        if part == "cache":
            return True
        if part.startswith(".") and part not in ["."]:
            return True

    # Check file extensions
    return path.is_file() and path.suffix in [".tmp", ".cache", ".log", ".pyc"]


def package_pack(pack_dir: Path, output_path: Path) -> Path:
    """Create .tar.gz archive from pack directory.

    Includes:
    - manifest.json
    - pack.db/ (Kuzu database directory)
    - skill.md
    - kg_config.json
    - README.md (if present)
    - eval/ (if present)

    Excludes:
    - __pycache__ directories
    - Hidden files/directories (starting with .)
    - cache/ directory
    - Temp files (.tmp, .cache, .log)

    Args:
        pack_dir: Path to pack directory
        output_path: Path for output .tar.gz file

    Returns:
        Path to created archive

    Raises:
        FileNotFoundError: If pack_dir doesn't exist
        ValueError: If pack structure is invalid
    """
    if not pack_dir.exists():
        raise FileNotFoundError(f"Pack directory not found: {pack_dir}")

    # Validate pack structure before packaging
    errors = validate_pack_structure(pack_dir)
    if errors:
        raise ValueError(f"Invalid pack structure: {'; '.join(errors)}")

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create tar.gz archive
    with tarfile.open(output_path, "w:gz") as tar:
        # Add all files/directories, filtering out excluded items
        for item in pack_dir.rglob("*"):
            if _should_exclude(item, pack_dir):
                continue

            # Calculate archive name (relative to pack_dir)
            arcname = str(item.relative_to(pack_dir))

            # Add to archive
            tar.add(item, arcname=arcname, recursive=False)

    return output_path


def unpackage_pack(archive_path: Path, install_dir: Path) -> Path:
    """Extract pack archive to installation directory.

    Args:
        archive_path: Path to .tar.gz pack archive
        install_dir: Base installation directory (e.g., ~/.wikigr/packs)

    Returns:
        Path to extracted pack directory (install_dir/pack_name/)

    Raises:
        FileNotFoundError: If archive doesn't exist
        tarfile.TarError: If archive is invalid
        ValueError: If extracted pack fails validation
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    # Create installation directory
    install_dir.mkdir(parents=True, exist_ok=True)

    # Extract to temporary directory first for validation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Extract archive
        with tarfile.open(archive_path, "r:gz") as tar:
            # Security check: ensure no absolute paths, parent refs, or symlinks
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    raise ValueError(f"Invalid archive member path: {member.name}")
                if member.issym() or member.islnk():
                    raise ValueError(
                        f"Symlinks/hardlinks not allowed in pack archives: {member.name}"
                    )

            # Extract all files
            tar.extractall(temp_path)

        # Validate extracted pack structure
        errors = validate_pack_structure(temp_path)
        if errors:
            raise ValueError(f"Pack validation failed: {'; '.join(errors)}")

        # Load manifest to get pack name
        manifest = load_manifest(temp_path)
        pack_name = manifest.name

        # Final installation path
        final_path = install_dir / pack_name

        # Move from temp to final location (atomic operation)
        if final_path.exists():
            # Remove existing installation
            import shutil

            shutil.rmtree(final_path)

        # Move extracted pack to final location
        import shutil

        shutil.move(str(temp_path), str(final_path))

    return final_path
