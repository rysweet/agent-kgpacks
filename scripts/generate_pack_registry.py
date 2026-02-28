#!/usr/bin/env python3
"""Generate pack registry index from local pack manifests.

Scans data/packs/*/manifest.json, reads metadata and pack.db sizes,
and writes a consolidated registry JSON to data/pack_registry.json.

Usage:
    python scripts/generate_pack_registry.py
    python scripts/generate_pack_registry.py --output /path/to/registry.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = PROJECT_ROOT / "data" / "packs"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "pack_registry.json"

GITHUB_RELEASE_BASE = "https://github.com/rysweet/agent-kgpacks/releases/download/v1"


def get_pack_db_size_mb(pack_dir: Path) -> float:
    """Return pack.db size in MB, handling both file and directory forms."""
    db_path = pack_dir / "pack.db"
    if not db_path.exists():
        return 0.0
    if db_path.is_dir():
        total = sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())
    else:
        total = db_path.stat().st_size
    return round(total / (1024 * 1024), 1)


def extract_tags(manifest_data: dict) -> list[str]:
    """Extract tags from manifest, handling both old and new formats."""
    if "tags" in manifest_data:
        return manifest_data["tags"]
    # Derive tags from name and domain for packs that lack explicit tags
    tags = []
    name = manifest_data.get("name", "")
    for part in name.split("-"):
        if part not in ("expert", "advanced", "internals"):
            tags.append(part)
    domain = manifest_data.get("domain", "")
    if domain and domain not in tags:
        tags.append(domain)
    return tags


def extract_articles(manifest_data: dict) -> int:
    """Extract article count from either format."""
    if "graph_stats" in manifest_data:
        return manifest_data["graph_stats"].get("articles", 0)
    return manifest_data.get("article_count", 0)


def extract_eval_accuracy(manifest_data: dict) -> float | None:
    """Extract eval accuracy as a percentage (0-100), or None if not evaluated."""
    if "eval_scores" in manifest_data:
        scores = manifest_data["eval_scores"]
        acc = scores.get("accuracy", 0.0)
        if acc > 0:
            # Accuracy is stored as 0.0-1.0, convert to percentage
            return round(acc * 100, 1)
    return None


def has_eval_questions(pack_dir: Path) -> bool:
    """Check whether the pack has eval questions."""
    eval_dir = pack_dir / "eval"
    if not eval_dir.exists():
        return False
    return any(
        f.name in ("questions.json", "questions.jsonl") for f in eval_dir.iterdir() if f.is_file()
    )


def build_registry_entry(pack_dir: Path) -> dict | None:
    """Build a single registry entry from a pack directory."""
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        return None

    with open(manifest_path) as f:
        data = json.load(f)

    name = data.get("name", pack_dir.name)
    size_mb = get_pack_db_size_mb(pack_dir)

    entry = {
        "name": name,
        "description": data.get("description", ""),
        "version": data.get("version", "1.0.0"),
        "articles": extract_articles(data),
        "size_mb": size_mb,
        "tags": extract_tags(data),
        "has_eval": has_eval_questions(pack_dir),
        "license": data.get("license", "MIT"),
        "download_url": f"{GITHUB_RELEASE_BASE}/{name}.tar.gz",
    }

    accuracy = extract_eval_accuracy(data)
    if accuracy is not None:
        entry["eval_accuracy"] = accuracy

    return entry


def generate_registry(packs_dir: Path) -> dict:
    """Scan packs directory and produce full registry dict."""
    entries = []
    for pack_dir in sorted(packs_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        if pack_dir.name in ("dist", "__pycache__"):
            continue
        entry = build_registry_entry(pack_dir)
        if entry is not None:
            entries.append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "pack_count": len(entries),
        "packs": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate pack registry index from local manifests"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    if not PACKS_DIR.exists():
        print(f"Error: packs directory not found: {PACKS_DIR}", file=sys.stderr)
        sys.exit(1)

    registry = generate_registry(PACKS_DIR)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")

    print(f"Registry generated: {args.output}")
    print(f"  Packs indexed: {registry['pack_count']}")


if __name__ == "__main__":
    main()
