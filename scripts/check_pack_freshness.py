#!/usr/bin/env python3
"""Check knowledge pack URL freshness by comparing HTTP headers against cached values.

Sends HEAD requests to every URL in a pack's urls.txt, compares ETag and
Last-Modified headers against a local freshness cache, and reports which URLs
have changed since the last check.

Usage:
    # Check one pack
    python scripts/check_pack_freshness.py data/packs/kubernetes-networking

    # Check all packs, output JSON summary
    python scripts/check_pack_freshness.py --all --json

    # Check with content hashing (slower, more accurate)
    python scripts/check_pack_freshness.py data/packs/rust-expert --content-hash
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_FILENAME = ".freshness_cache.json"
USER_AGENT = "WikiGR-FreshnessChecker/1.0"
DEFAULT_TIMEOUT = 15
DEFAULT_WORKERS = 8
MAX_RETRIES = 2
CHANGE_THRESHOLD = 0.20  # 20 % of URLs must change to trigger rebuild


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class URLStatus:
    url: str
    status_code: int
    etag: str | None
    last_modified: str | None
    content_hash: str | None
    changed: bool
    error: str | None


@dataclass
class PackFreshnessReport:
    pack_name: str
    pack_dir: str
    total_urls: int
    checked: int
    changed_urls: list[str]
    errored_urls: list[str]
    change_ratio: float
    needs_rebuild: bool
    checked_at: str
    details: list[URLStatus] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------


def load_cache(pack_dir: Path) -> dict:
    """Load the freshness cache for a pack. Returns empty dict on missing/corrupt file."""
    cache_path = pack_dir / CACHE_FILENAME
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(pack_dir: Path, cache: dict) -> None:
    """Persist freshness cache to disk."""
    cache_path = pack_dir / CACHE_FILENAME
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# URL loading (reuses convention from existing build scripts)
# ---------------------------------------------------------------------------


def load_urls(urls_file: Path) -> list[str]:
    """Load URLs from a pack's urls.txt, skipping comments and blanks."""
    if not urls_file.exists():
        return []
    with open(urls_file) as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#") and line.strip().startswith("http")
        ]


# ---------------------------------------------------------------------------
# Single-URL freshness check
# ---------------------------------------------------------------------------


def check_url(
    url: str,
    cached_entry: dict,
    content_hash: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> URLStatus:
    """Send a HEAD (or GET for content hashing) request and compare against cache."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            if content_hash:
                resp = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=True,
                )
            else:
                resp = requests.head(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=True,
                )

            if resp.status_code == 429:
                # Rate limited -- back off, treat as unchanged if last attempt
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)
                    continue
                return URLStatus(
                    url=url,
                    status_code=200,
                    etag=cached_entry.get("etag"),
                    last_modified=cached_entry.get("last_modified"),
                    content_hash=cached_entry.get("content_hash"),
                    changed=False,
                    error="rate-limited, assumed unchanged",
                )

            if resp.status_code >= 400:
                return URLStatus(
                    url=url,
                    status_code=resp.status_code,
                    etag=None,
                    last_modified=None,
                    content_hash=None,
                    changed=False,
                    error=f"HTTP {resp.status_code}",
                )

            etag = resp.headers.get("ETag")
            last_mod = resp.headers.get("Last-Modified")
            c_hash = None
            if content_hash and resp.status_code == 200:
                c_hash = hashlib.sha256(resp.content).hexdigest()

            # Determine if changed
            changed = _is_changed(cached_entry, etag, last_mod, c_hash)

            return URLStatus(
                url=url,
                status_code=resp.status_code,
                etag=etag,
                last_modified=last_mod,
                content_hash=c_hash,
                changed=changed,
                error=None,
            )

        except requests.Timeout:
            if attempt < MAX_RETRIES:
                time.sleep(1)
                continue
            return URLStatus(
                url=url,
                status_code=0,
                etag=None,
                last_modified=None,
                content_hash=None,
                changed=False,
                error="timeout",
            )
        except requests.ConnectionError:
            return URLStatus(
                url=url,
                status_code=0,
                etag=None,
                last_modified=None,
                content_hash=None,
                changed=False,
                error="connection_error",
            )
        except Exception as e:
            return URLStatus(
                url=url,
                status_code=0,
                etag=None,
                last_modified=None,
                content_hash=None,
                changed=False,
                error=str(e)[:80],
            )

    # Should not reach here, but be safe
    return URLStatus(
        url=url,
        status_code=0,
        etag=None,
        last_modified=None,
        content_hash=None,
        changed=False,
        error="max_retries",
    )


def _is_changed(
    cached: dict,
    etag: str | None,
    last_modified: str | None,
    content_hash: str | None,
) -> bool:
    """Compare current response headers against cached values.

    Returns True if we detect a change, False if unchanged or no cached data
    to compare against (first run is always 'unchanged' to avoid spurious rebuilds).
    """
    if not cached:
        # First time checking this URL -- nothing to compare against
        return False

    # Content hash is the strongest signal
    if content_hash and cached.get("content_hash"):
        return content_hash != cached["content_hash"]

    # ETag comparison
    if etag and cached.get("etag"):
        return etag != cached["etag"]

    # Last-Modified comparison
    if last_modified and cached.get("last_modified"):
        return last_modified != cached["last_modified"]

    # No comparable headers available -- assume unchanged
    return False


# ---------------------------------------------------------------------------
# Pack-level freshness check
# ---------------------------------------------------------------------------


def check_pack_freshness(
    pack_dir: Path,
    use_content_hash: bool = False,
    workers: int = DEFAULT_WORKERS,
    threshold: float = CHANGE_THRESHOLD,
) -> PackFreshnessReport:
    """Check all URLs in a pack and return a freshness report."""
    pack_name = pack_dir.name
    urls_file = pack_dir / "urls.txt"
    urls = load_urls(urls_file)

    if not urls:
        return PackFreshnessReport(
            pack_name=pack_name,
            pack_dir=str(pack_dir),
            total_urls=0,
            checked=0,
            changed_urls=[],
            errored_urls=[],
            change_ratio=0.0,
            needs_rebuild=False,
            checked_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    cache = load_cache(pack_dir)
    results: list[URLStatus] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                check_url,
                url,
                cache.get(url, {}),
                use_content_hash,
            ): url
            for url in urls
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Update cache with fresh data
    for r in results:
        if r.error is None and r.status_code < 400:
            entry: dict = {}
            if r.etag:
                entry["etag"] = r.etag
            if r.last_modified:
                entry["last_modified"] = r.last_modified
            if r.content_hash:
                entry["content_hash"] = r.content_hash
            entry["checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            cache[r.url] = entry

    save_cache(pack_dir, cache)

    changed = [r.url for r in results if r.changed]
    errored = [r.url for r in results if r.error is not None]
    checked_count = len(results) - len(errored)
    change_ratio = len(changed) / max(checked_count, 1)

    return PackFreshnessReport(
        pack_name=pack_name,
        pack_dir=str(pack_dir),
        total_urls=len(urls),
        checked=checked_count,
        changed_urls=changed,
        errored_urls=errored,
        change_ratio=round(change_ratio, 4),
        needs_rebuild=change_ratio >= threshold,
        checked_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        details=results,
    )


# ---------------------------------------------------------------------------
# Multi-pack runner
# ---------------------------------------------------------------------------


def discover_packs(packs_root: Path) -> list[Path]:
    """Find all pack directories that have a urls.txt."""
    return sorted(d.parent for d in packs_root.glob("*/urls.txt"))


def check_all_packs(
    packs_root: Path,
    use_content_hash: bool = False,
    workers: int = DEFAULT_WORKERS,
    threshold: float = CHANGE_THRESHOLD,
) -> list[PackFreshnessReport]:
    """Check freshness of all packs under packs_root."""
    reports = []
    for pack_dir in discover_packs(packs_root):
        report = check_pack_freshness(pack_dir, use_content_hash, workers, threshold)
        reports.append(report)
    return reports


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check knowledge pack URL freshness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("pack_dir", nargs="?", help="Path to a single pack directory")
    parser.add_argument("--all", action="store_true", help="Check all packs under data/packs/")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--content-hash", action="store_true", help="Use content hashing (slower)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Concurrent workers")
    parser.add_argument(
        "--threshold",
        type=float,
        default=CHANGE_THRESHOLD,
        help=f"Change ratio to trigger rebuild (default: {CHANGE_THRESHOLD})",
    )
    args = parser.parse_args()

    if not args.all and not args.pack_dir:
        parser.print_help()
        return 1

    if args.all:
        reports = check_all_packs(
            Path("data/packs"),
            use_content_hash=args.content_hash,
            workers=args.workers,
            threshold=args.threshold,
        )
    else:
        pack_path = Path(args.pack_dir)
        if not pack_path.is_dir():
            print(f"Error: {pack_path} is not a directory", file=sys.stderr)
            return 1
        reports = [
            check_pack_freshness(
                pack_path,
                use_content_hash=args.content_hash,
                workers=args.workers,
                threshold=args.threshold,
            )
        ]

    if args.json:
        output = []
        for r in reports:
            d = asdict(r)
            # Remove verbose details from JSON summary by default
            d.pop("details", None)
            output.append(d)
        print(json.dumps(output, indent=2))
    else:
        for r in reports:
            status = "REBUILD" if r.needs_rebuild else "OK"
            print(
                f"[{status}] {r.pack_name}: "
                f"{len(r.changed_urls)}/{r.checked} changed "
                f"({r.change_ratio:.0%}), "
                f"{len(r.errored_urls)} errors"
            )
            if r.changed_urls:
                for url in r.changed_urls:
                    print(f"  changed: {url}")

    # Exit 0 if no rebuilds needed, 1 if any pack needs rebuild
    needs_any = any(r.needs_rebuild for r in reports)
    return 1 if needs_any else 0


if __name__ == "__main__":
    sys.exit(main())
