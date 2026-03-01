#!/usr/bin/env python3
"""Validate URLs in pack urls.txt files. Removes hallucinated/dead URLs.

Usage:
    python scripts/validate_pack_urls.py data/packs/dotnet-expert/urls.txt
    python scripts/validate_pack_urls.py --all  # Validate all packs
"""

import argparse
import concurrent.futures
import sys
from pathlib import Path

import requests


def check_url(url: str, timeout: int = 10, retries: int = 2) -> tuple[str, int, str]:
    """Check if URL is reachable. Returns (url, status_code, reason).

    Retries on 429 (rate limit) with exponential backoff.
    Treats 429 as VALID (the URL exists, just rate-limited).
    """
    import time as _time

    for attempt in range(retries + 1):
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 429:
                # Rate limited - URL is valid, just throttled
                if attempt < retries:
                    _time.sleep(2**attempt)
                    continue
                return (url, 200, "ok (rate-limited but valid)")
            return (url, r.status_code, "ok" if r.status_code < 400 else f"HTTP {r.status_code}")
        except requests.ConnectionError:
            return (url, 0, "connection_error")
        except requests.Timeout:
            if attempt < retries:
                _time.sleep(1)
                continue
            return (url, 0, "timeout")
        except Exception as e:
            return (url, 0, str(e)[:60])
    return (url, 0, "max_retries")


def load_urls(path: Path) -> list[str]:
    with open(path) as f:
        return [
            stripped
            for line in f
            if (stripped := line.strip())
            and not stripped.startswith("#")
            and stripped.startswith("https://")
        ]


def validate_file(urls_path: Path, fix: bool = False, workers: int = 10) -> dict:
    urls = load_urls(urls_path)
    print(f"Validating {len(urls)} URLs from {urls_path}...")

    results = {"valid": [], "invalid": []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_url, url): url for url in urls}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            url, status, reason = future.result()
            if status < 400 and status > 0:
                results["valid"].append(url)
            else:
                results["invalid"].append((url, status, reason))
                print(f"  ❌ [{status}] {url} ({reason})")
            if i % 50 == 0:
                print(f"  ... checked {i}/{len(urls)}")

    print(f"\nResults: {len(results['valid'])} valid, {len(results['invalid'])} invalid")

    if fix and results["invalid"]:
        # Rewrite urls.txt with only valid URLs, preserving comments
        with open(urls_path) as f:
            lines = f.readlines()
        invalid_urls = {u for u, _, _ in results["invalid"]}
        with open(urls_path, "w") as f:
            removed = 0
            for line in lines:
                stripped = line.strip()
                if stripped in invalid_urls:
                    f.write(f"# REMOVED (404): {stripped}\n")
                    removed += 1
                else:
                    f.write(line)
        print(f"Fixed: commented out {removed} invalid URLs in {urls_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Validate pack URLs")
    parser.add_argument("urls_file", nargs="?", help="Path to urls.txt")
    parser.add_argument("--all", action="store_true", help="Validate all packs")
    parser.add_argument("--fix", action="store_true", help="Remove invalid URLs from file")
    parser.add_argument("--workers", type=int, default=10, help="Concurrent workers")
    args = parser.parse_args()

    if args.all:
        for urls_file in sorted(Path("data/packs").glob("*/urls.txt")):
            print(f"\n{'=' * 60}")
            validate_file(urls_file, fix=args.fix, workers=args.workers)
    elif args.urls_file:
        validate_file(Path(args.urls_file), fix=args.fix, workers=args.workers)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
