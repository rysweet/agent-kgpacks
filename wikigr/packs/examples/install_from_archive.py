#!/usr/bin/env python3
"""Example: Install a knowledge pack from an archive file.

This script demonstrates how to install a pack from a .tar.gz archive.
The pack is validated and extracted to the installation directory.
"""

from pathlib import Path

from wikigr.packs import PackInstaller


def main():
    """Install a physics pack from archive."""
    # Path to archive (created by package_example_pack.py)
    archive_path = Path.home() / ".wikigr/archives/physics-expert-1.0.0.tar.gz"

    # Installation directory
    install_dir = Path.home() / ".wikigr/packs"

    # Check if archive exists
    if not archive_path.exists():
        print(f"Archive not found: {archive_path}")
        print("Run package_example_pack.py first to create the archive.")
        return

    print(f"Installing pack from: {archive_path}")
    print(f"Installation directory: {install_dir}")

    # Create installer
    installer = PackInstaller(install_dir=install_dir)

    # Install pack
    pack_info = installer.install_from_file(archive_path)

    print("\n✓ Pack installed successfully!")
    print(f"  Name: {pack_info.name}")
    print(f"  Version: {pack_info.version}")
    print(f"  Path: {pack_info.path}")
    print(f"  Skill: {pack_info.skill_path}")

    # Display pack details
    print("\nPack details:")
    print(f"  Description: {pack_info.manifest.description}")
    print(f"  Articles: {pack_info.manifest.graph_stats.articles:,}")
    print(f"  Entities: {pack_info.manifest.graph_stats.entities:,}")
    print(f"  Relationships: {pack_info.manifest.graph_stats.relationships:,}")
    print(f"  Size: {pack_info.manifest.graph_stats.size_mb} MB")

    print("\nEvaluation scores:")
    print(f"  Accuracy: {pack_info.manifest.eval_scores.accuracy:.2%}")
    print(f"  Hallucination rate: {pack_info.manifest.eval_scores.hallucination_rate:.2%}")
    print(f"  Citation quality: {pack_info.manifest.eval_scores.citation_quality:.2%}")

    print("\nNext steps:")
    print(f"1. The pack is now available at: {pack_info.path}")
    print(f"2. The skill is at: {pack_info.skill_path}")
    print("3. Use discover_packs() to find this and other installed packs")
    print("4. Query the pack's knowledge graph using KG Agent")


if __name__ == "__main__":
    main()
