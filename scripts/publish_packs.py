#!/usr/bin/env python3
"""Publish pre-built knowledge packs as GitHub release assets.

Creates a GitHub release and uploads pack.db files as downloadable assets.
Users can then install packs without building them locally.

Usage:
    python scripts/publish_packs.py --tag v0.4.1
    python scripts/publish_packs.py --tag v0.4.1 --packs rust-expert,go-expert
    python scripts/publish_packs.py --tag v0.4.1 --dry-run
"""

import argparse
import json
import logging
import subprocess
import tarfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PACKS_DIR = Path("data/packs")


def find_publishable_packs(filter_names: list[str] | None = None) -> list[dict]:
    """Find packs that have both pack.db and manifest.json."""
    packs = []
    for pack_dir in sorted(PACKS_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue
        if not (pack_dir / "pack.db").exists():
            continue
        if not (pack_dir / "manifest.json").exists():
            continue
        if filter_names and pack_dir.name not in filter_names:
            continue
        manifest = json.loads((pack_dir / "manifest.json").read_text())
        packs.append(
            {
                "name": pack_dir.name,
                "dir": pack_dir,
                "manifest": manifest,
                "articles": manifest.get("graph_stats", {}).get("articles", 0),
            }
        )
    return packs


def create_pack_archive(pack_dir: Path, output_dir: Path) -> Path:
    """Create a .tar.gz archive of a pack for distribution."""
    name = pack_dir.name
    archive_path = output_dir / f"{name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        # Include pack.db, manifest.json, urls.txt, skill.md if they exist
        for filename in ("pack.db", "manifest.json", "urls.txt", "skill.md"):
            filepath = pack_dir / filename
            if filepath.exists():
                tar.add(filepath, arcname=f"{name}/{filename}")
        # Include eval directory if it exists
        eval_dir = pack_dir / "eval"
        if eval_dir.exists():
            for eval_file in eval_dir.iterdir():
                if eval_file.is_file():
                    tar.add(eval_file, arcname=f"{name}/eval/{eval_file.name}")
    return archive_path


def main():
    parser = argparse.ArgumentParser(description="Publish packs as GitHub release assets")
    parser.add_argument("--tag", required=True, help="Release tag (e.g., v0.4.1)")
    parser.add_argument("--packs", help="Comma-separated pack names (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Create archives but don't publish")
    args = parser.parse_args()

    filter_names = args.packs.split(",") if args.packs else None
    packs = find_publishable_packs(filter_names)
    logger.info(f"Found {len(packs)} packs to publish")

    # Create output directory
    output_dir = Path("dist/packs")
    output_dir.mkdir(parents=True, exist_ok=True)

    archives = []
    for pack in packs:
        logger.info(f"  Archiving {pack['name']} ({pack['articles']} articles)...")
        archive = create_pack_archive(pack["dir"], output_dir)
        size_mb = archive.stat().st_size / (1024 * 1024)
        archives.append({"name": pack["name"], "path": archive, "size_mb": size_mb})
        logger.info(f"    → {archive.name} ({size_mb:.1f} MB)")

    if args.dry_run:
        logger.info(f"\nDRY RUN: {len(archives)} archives created in {output_dir}")
        total_mb = sum(a["size_mb"] for a in archives)
        logger.info(f"Total size: {total_mb:.1f} MB")
        return

    # Create GitHub release
    logger.info(f"\nCreating GitHub release {args.tag}...")
    release_notes = f"# Knowledge Packs Release {args.tag}\n\n"
    release_notes += f"{len(archives)} pre-built knowledge packs.\n\n"
    release_notes += "## Install\n\n```bash\n"
    release_notes += "# Download and install a pack\n"
    release_notes += f"gh release download {args.tag} -p 'rust-expert.tar.gz'\n"
    release_notes += "wikigr pack install rust-expert.tar.gz\n```\n\n"
    release_notes += "## Packs\n\n| Pack | Articles | Size |\n|------|----------|------|\n"
    for a in archives:
        release_notes += f"| {a['name']} | {next(p['articles'] for p in packs if p['name'] == a['name'])} | {a['size_mb']:.1f} MB |\n"

    try:
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                args.tag,
                "--title",
                f"Knowledge Packs {args.tag}",
                "--notes",
                release_notes,
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        logger.warning(f"Release {args.tag} may already exist, trying to upload assets...")

    # Upload archives as release assets
    for archive in archives:
        logger.info(f"  Uploading {archive['name']}...")
        try:
            subprocess.run(
                ["gh", "release", "upload", args.tag, str(archive["path"]), "--clobber"],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"  Failed to upload {archive['name']}: {e}")

    logger.info(f"\nPublished {len(archives)} packs to release {args.tag}")


if __name__ == "__main__":
    main()
