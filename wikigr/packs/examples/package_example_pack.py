#!/usr/bin/env python3
"""Example: Package a knowledge pack into a distributable archive.

This script demonstrates how to create a .tar.gz archive from a pack directory.
The archive can then be shared, distributed, or installed on other systems.
"""

from pathlib import Path

from wikigr.packs import package_pack


def main():
    """Package a physics pack into a distributable archive."""
    # Path to pack directory (from Phase 2 examples)
    pack_dir = Path(__file__).parent / "physics-expert"

    # Check if pack exists
    if not pack_dir.exists():
        print(f"Pack directory not found: {pack_dir}")
        print("Run create_physics_pack_with_skill.py first to create the pack.")
        return

    # Output archive path
    output_path = Path.home() / ".wikigr/archives/physics-expert-1.0.0.tar.gz"

    print(f"Packaging pack from: {pack_dir}")
    print(f"Output archive: {output_path}")

    # Package the pack
    archive_path = package_pack(pack_dir, output_path)

    print("\n✓ Pack packaged successfully!")
    print(f"  Archive: {archive_path}")
    print(f"  Size: {archive_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Verify archive contents
    import tarfile

    print("\nArchive contents:")
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                size_kb = member.size / 1024
                print(f"  {member.name:<40} {size_kb:>8.1f} KB")
            elif member.isdir():
                print(f"  {member.name}/ (directory)")

    print("\nNext steps:")
    print("1. Share the archive with others")
    print("2. Install on another system using install_from_archive.py")
    print("3. Upload to a pack registry (when available)")


if __name__ == "__main__":
    main()
