#!/usr/bin/env python3
"""CLI tool for browsing, searching, and installing knowledge packs.

Usage:
    python scripts/install_pack.py list
    python scripts/install_pack.py search kubernetes
    python scripts/install_pack.py info physics-expert
    python scripts/install_pack.py install kubernetes-networking
    python scripts/install_pack.py install kubernetes-networking --target ~/.claude/packs/
"""

import argparse
import json
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "data" / "pack_registry.json"
LOCAL_PACKS_DIR = PROJECT_ROOT / "data" / "packs"
DEFAULT_INSTALL_DIR = Path.home() / ".wikigr" / "packs"


def load_registry() -> dict:
    """Load pack registry, generating it on-the-fly if missing."""
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            return json.load(f)

    # Fall back: scan local packs directly
    print("Registry not found, scanning local packs...", file=sys.stderr)
    from generate_pack_registry import generate_registry

    return generate_registry(LOCAL_PACKS_DIR)


def fmt_size(mb: float) -> str:
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def fmt_accuracy(entry: dict) -> str:
    if "eval_accuracy" in entry:
        return f"{entry['eval_accuracy']:.0f}%"
    return "n/a"


def print_pack_table(packs: list[dict], title: str = "Available Packs") -> None:
    """Print packs in a formatted table."""
    if not packs:
        print("No packs found.")
        return

    # Column widths
    name_w = max(len(p["name"]) for p in packs)
    name_w = max(name_w, 4)  # minimum "Name"

    print(f"\n  {title}")
    print(f"  {'=' * (name_w + 50)}")
    header = f"  {'Name':<{name_w}}  {'Articles':>8}  {'Size':>7}  {'Eval':>5}  Description"
    print(header)
    print(f"  {'-' * (name_w + 50)}")

    for p in packs:
        desc = p["description"]
        # Truncate long descriptions
        max_desc = 50
        if len(desc) > max_desc:
            desc = desc[: max_desc - 3] + "..."
        line = (
            f"  {p['name']:<{name_w}}  "
            f"{p['articles']:>8}  "
            f"{fmt_size(p['size_mb']):>7}  "
            f"{fmt_accuracy(p):>5}  "
            f"{desc}"
        )
        print(line)

    print(f"\n  Total: {len(packs)} packs\n")


def cmd_list(args: argparse.Namespace) -> None:
    """List all available packs."""
    registry = load_registry()
    packs = registry.get("packs", [])

    if args.sort == "name":
        packs.sort(key=lambda p: p["name"])
    elif args.sort == "size":
        packs.sort(key=lambda p: p["size_mb"], reverse=True)
    elif args.sort == "articles":
        packs.sort(key=lambda p: p["articles"], reverse=True)

    print_pack_table(packs)


def cmd_search(args: argparse.Namespace) -> None:
    """Search packs by keyword."""
    registry = load_registry()
    query = args.query.lower()

    matches = []
    for p in registry.get("packs", []):
        searchable = " ".join(
            [
                p["name"],
                p["description"],
                " ".join(p.get("tags", [])),
            ]
        ).lower()
        if query in searchable:
            matches.append(p)

    print_pack_table(matches, title=f"Packs matching '{args.query}'")


def cmd_info(args: argparse.Namespace) -> None:
    """Show detailed information about a pack."""
    registry = load_registry()
    pack = None
    for p in registry.get("packs", []):
        if p["name"] == args.pack_name:
            pack = p
            break

    if pack is None:
        print(f"Pack not found: {args.pack_name}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Pack: {pack['name']}")
    print(f"  {'=' * 50}")
    print(f"  Description : {pack['description']}")
    print(f"  Version     : {pack.get('version', '1.0.0')}")
    print(f"  Articles    : {pack['articles']}")
    print(f"  Size        : {fmt_size(pack['size_mb'])}")
    print(f"  Eval        : {fmt_accuracy(pack)}")
    print(f"  Has eval Q  : {'yes' if pack.get('has_eval') else 'no'}")
    print(f"  License     : {pack.get('license', 'MIT')}")
    print(f"  Tags        : {', '.join(pack.get('tags', []))}")
    print(f"  Download    : {pack.get('download_url', 'n/a')}")
    print()


def install_from_local(pack_name: str, target_dir: Path) -> Path:
    """Install pack by copying from local data/packs directory."""
    source = LOCAL_PACKS_DIR / pack_name
    if not source.exists():
        return None

    dest = target_dir / pack_name
    if dest.exists():
        shutil.rmtree(dest)

    # Copy pack contents (manifest, pack.db, eval)
    shutil.copytree(source, dest)
    return dest


def install_from_url(url: str, pack_name: str, target_dir: Path) -> Path:
    """Download and extract pack from URL."""
    import tarfile

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        print(f"  Downloading {url} ...")
        urllib.request.urlretrieve(url, tmp_path)

        dest = target_dir / pack_name
        dest.mkdir(parents=True, exist_ok=True)

        print("  Extracting...")
        with tarfile.open(tmp_path, "r:gz") as tar:
            # Security: validate paths before extraction
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in member.name:
                    raise ValueError(f"Unsafe path in archive: {member.name}")
            tar.extractall(path=target_dir, filter="data")

        return dest
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def cmd_install(args: argparse.Namespace) -> None:
    """Install a pack."""
    registry = load_registry()
    pack_name = args.pack_name

    # Find pack in registry
    pack = None
    for p in registry.get("packs", []):
        if p["name"] == pack_name:
            pack = p
            break

    if pack is None:
        print(f"Pack not found in registry: {pack_name}", file=sys.stderr)
        sys.exit(1)

    target_dir = Path(args.target) if args.target else DEFAULT_INSTALL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Installing: {pack_name}")
    print(f"  Target    : {target_dir}")
    print(f"  Size      : {fmt_size(pack['size_mb'])}")

    # Try local first, then fall back to URL download
    dest = install_from_local(pack_name, target_dir)
    if dest:
        print("  Source    : local copy")
    else:
        url = pack.get("download_url")
        if not url:
            print("  No download URL available and pack not found locally.", file=sys.stderr)
            sys.exit(1)
        dest = install_from_url(url, pack_name, target_dir)

    # Verify installation
    manifest_path = dest / "manifest.json"
    if manifest_path.exists():
        print(f"  Installed : {dest}")
        print("  Status    : OK")
    else:
        print(f"  Warning: manifest.json not found at {dest}", file=sys.stderr)
        print("  Status    : partial (no manifest)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Browse, search, and install knowledge packs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_parser = subparsers.add_parser("list", help="List all available packs")
    list_parser.add_argument(
        "--sort",
        choices=["name", "size", "articles"],
        default="name",
        help="Sort order (default: name)",
    )

    # search
    search_parser = subparsers.add_parser("search", help="Search packs by keyword")
    search_parser.add_argument("query", help="Search keyword")

    # info
    info_parser = subparsers.add_parser("info", help="Show pack details")
    info_parser.add_argument("pack_name", help="Pack name")

    # install
    install_parser = subparsers.add_parser("install", help="Install a pack")
    install_parser.add_argument("pack_name", help="Pack name to install")
    install_parser.add_argument(
        "--target",
        help=f"Target directory (default: {DEFAULT_INSTALL_DIR})",
    )

    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "search": cmd_search,
        "info": cmd_info,
        "install": cmd_install,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
