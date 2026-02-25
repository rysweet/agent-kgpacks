#!/usr/bin/env python3
"""
Package Physics Expert Knowledge Pack for distribution.

This script validates the pack structure and creates a distributable tarball.

Usage:
    python scripts/package_physics_pack.py [--output OUTPUT_DIR]

Options:
    --output DIR    Output directory for tarball (default: data/packs/dist)
"""

import argparse
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from wikigr.packs.manifest import load_manifest  # noqa: E402
from wikigr.packs.validator import validate_pack_structure  # noqa: E402

PACK_DIR = Path("data/packs/physics-expert")
DEFAULT_OUTPUT_DIR = Path("data/packs/dist")

# Pack name validation pattern
PACK_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def validate_pack_name(name: str) -> None:
    """Validate pack name contains only safe characters.

    Args:
        name: Pack name to validate

    Raises:
        ValueError: If pack name contains unsafe characters
    """
    if not PACK_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid pack name: {name}. "
            "Must contain only alphanumeric characters, hyphens, and underscores."
        )


def validate_pack(pack_dir: Path) -> bool:
    """Validate pack structure before packaging.

    Args:
        pack_dir: Path to pack directory

    Returns:
        True if valid, False if errors found
    """
    logger.info(f"Validating pack structure: {pack_dir}")

    errors = validate_pack_structure(pack_dir, strict=False)

    if errors:
        logger.error("Pack validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    logger.info("Pack validation passed")
    return True


def create_tarball(pack_dir: Path, output_dir: Path) -> Path:
    """Create distributable tarball of the pack.

    Args:
        pack_dir: Path to pack directory
        output_dir: Directory to save tarball

    Returns:
        Path to created tarball

    Raises:
        ValueError: If pack name contains unsafe characters
    """
    # Load manifest to get version
    manifest = load_manifest(pack_dir)
    version = manifest.version
    pack_name = manifest.name

    # Validate pack name to prevent command injection
    validate_pack_name(pack_name)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate tarball name with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tarball_name = f"{pack_name}-{version}-{timestamp}.tar.gz"
    tarball_path = output_dir / tarball_name

    logger.info(f"Creating tarball: {tarball_path}")

    # Files to include
    include_files = [
        "pack.db/",
        "manifest.json",
        "README.md",
        "skill.md",
        "kg_config.json",
        "topics.txt",
        "eval/",
    ]

    # Build tar command
    # Use -C to change to parent directory, then specify relative paths
    tar_args = ["tar", "-czf", str(tarball_path), "-C", str(pack_dir.parent)]

    # Add each file/directory relative to pack_dir.parent
    pack_name_dir = pack_dir.name
    for item in include_files:
        item_path = pack_dir / item
        if item_path.exists():
            tar_args.append(f"{pack_name_dir}/{item}")
        else:
            logger.warning(f"Skipping missing item: {item}")

    # Execute tar command
    try:
        subprocess.run(tar_args, check=True, capture_output=True)
        logger.info(f"Tarball created: {tarball_path}")

        # Show file size
        size_mb = tarball_path.stat().st_size / (1024 * 1024)
        logger.info(f"Tarball size: {size_mb:.2f} MB")

        return tarball_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create tarball: {e}")
        logger.error(f"stderr: {e.stderr.decode()}")
        raise


def verify_tarball(tarball_path: Path) -> bool:
    """Verify tarball contents.

    Args:
        tarball_path: Path to tarball

    Returns:
        True if verification passed
    """
    logger.info(f"Verifying tarball: {tarball_path}")

    try:
        # List contents
        result = subprocess.run(
            ["tar", "-tzf", str(tarball_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        contents = result.stdout.strip().split("\n")
        logger.info(f"Tarball contains {len(contents)} files/directories")

        # Check for required files (pack.db can be file or directory)
        required_files = [
            "manifest.json",
            "skill.md",
            "kg_config.json",
        ]

        missing = []
        for required in required_files:
            # Check if any content line contains the required file
            found = any(required in line for line in contents)
            if not found:
                missing.append(required)

        # Special check for pack.db (can be file or directory)
        pack_db_found = any("pack.db" in line for line in contents)
        if not pack_db_found:
            missing.append("pack.db")

        if missing:
            logger.error("Required files missing from tarball:")
            for item in missing:
                logger.error(f"  - {item}")
            return False

        logger.info("Tarball verification passed")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to verify tarball: {e}")
        return False


def generate_checksums(tarball_path: Path) -> None:
    """Generate SHA256 checksum file.

    Args:
        tarball_path: Path to tarball
    """
    import hashlib

    logger.info("Generating checksums...")

    # Calculate SHA256
    sha256 = hashlib.sha256()
    with open(tarball_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)

    checksum = sha256.hexdigest()

    # Write checksum file
    checksum_path = tarball_path.with_suffix(".tar.gz.sha256")
    with open(checksum_path, "w") as f:
        f.write(f"{checksum}  {tarball_path.name}\n")

    logger.info(f"Checksum saved: {checksum_path}")
    logger.info(f"SHA256: {checksum}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Package Physics Expert Knowledge Pack for distribution"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for tarball (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    try:
        # Validate pack
        if not validate_pack(PACK_DIR):
            logger.error("Pack validation failed. Fix errors before packaging.")
            sys.exit(1)

        # Create tarball
        tarball_path = create_tarball(PACK_DIR, args.output)

        # Verify tarball
        if not verify_tarball(tarball_path):
            logger.error("Tarball verification failed.")
            sys.exit(1)

        # Generate checksums
        generate_checksums(tarball_path)

        logger.info("Packaging complete!")
        logger.info(f"Distributable tarball: {tarball_path}")
        logger.info(f"Checksum file: {tarball_path.with_suffix('.tar.gz.sha256')}")

    except KeyboardInterrupt:
        logger.info("Packaging interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Packaging failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
