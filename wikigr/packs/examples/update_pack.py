#!/usr/bin/env python3
"""Example: Update an installed pack while preserving eval results.

This script demonstrates how to update an existing pack installation to a newer
version while preserving any evaluation results you've generated.
"""

from pathlib import Path

from wikigr.packs import PackInstaller


def main():
    """Update physics pack to newer version."""
    # Archive for new version
    new_archive = Path.home() / ".wikigr/archives/physics-expert-2.0.0.tar.gz"

    # Installation directory
    install_dir = Path.home() / ".wikigr/packs"

    # Check if new archive exists
    if not new_archive.exists():
        print(f"Archive not found: {new_archive}")
        print("This example requires a newer version archive.")
        return

    # Check if pack is currently installed
    pack_name = "physics-expert"
    pack_path = install_dir / pack_name

    if not pack_path.exists():
        print(f"Pack '{pack_name}' is not currently installed.")
        print("Run install_from_archive.py first.")
        return

    # Show current version
    from wikigr.packs import load_manifest

    current_manifest = load_manifest(pack_path)
    print(f"Current version: {current_manifest.version}")
    print(f"Pack path: {pack_path}")

    # Check for eval results
    eval_results_dir = pack_path / "eval" / "results"
    if eval_results_dir.exists():
        num_results = len(list(eval_results_dir.rglob("*.json")))
        print(f"Found {num_results} evaluation result file(s)")
        print("These will be preserved during the update.")
    else:
        print("No evaluation results to preserve.")

    print(f"\nUpdating to new version from: {new_archive}")

    # Create installer
    installer = PackInstaller(install_dir=install_dir)

    # Update pack
    pack_info = installer.update(pack_name, new_archive)

    print("\n✓ Pack updated successfully!")
    print(f"  Name: {pack_info.name}")
    print(f"  New version: {pack_info.version}")
    print(f"  Path: {pack_info.path}")

    # Verify eval results preserved
    if eval_results_dir.exists():
        num_results_after = len(list((pack_info.path / "eval" / "results").rglob("*.json")))
        print(f"\nEvaluation results preserved: {num_results_after} file(s)")

    print("\nUpdate details:")
    print(f"  Articles: {pack_info.manifest.graph_stats.articles:,}")
    print(f"  Entities: {pack_info.manifest.graph_stats.entities:,}")
    print(f"  Relationships: {pack_info.manifest.graph_stats.relationships:,}")

    print("\nNext steps:")
    print("1. Test the updated pack with your queries")
    print("2. Run evaluations if needed")
    print("3. Compare performance with previous version")


if __name__ == "__main__":
    main()
