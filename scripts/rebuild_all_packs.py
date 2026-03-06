#!/usr/bin/env python3
"""Rebuild all knowledge packs with LadybugDB.

Deletes old Kuzu-format pack.db directories and rebuilds each pack
using the updated build scripts that use real_ladybug (LadybugDB).

Runs builds in parallel batches to maximize throughput while
respecting Anthropic API rate limits.

Usage:
    python scripts/rebuild_all_packs.py [--workers 4] [--test-mode]
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/rebuild_all_packs.log"),
    ],
)
logger = logging.getLogger(__name__)

# All build scripts (excluding the generic template and ladybugdb which is already built)
SCRIPTS_DIR = Path("scripts")
PACKS_DIR = Path("data/packs")


def find_build_scripts() -> list[Path]:
    """Find all pack build scripts."""
    scripts = sorted(SCRIPTS_DIR.glob("build_*_pack.py"))
    # Exclude the generic template and already-built ladybugdb
    exclude = {"build_pack_from_issue.py", "build_ladybugdb_expert_pack.py"}
    return [s for s in scripts if s.name not in exclude]


def rebuild_pack(script_path: Path, test_mode: bool = False) -> dict:
    """Rebuild a single pack by deleting old DB and running build script."""
    pack_name = script_path.name.replace("build_", "").replace("_pack.py", "").replace("_", "-")
    start = time.time()

    # Find the pack directory (naming may differ slightly)
    possible_dirs = [
        PACKS_DIR / pack_name,
        PACKS_DIR / f"{pack_name}-expert",
    ]
    pack_dir = None
    for d in possible_dirs:
        if d.exists():
            pack_dir = d
            break

    # Delete old pack.db and any leftover WAL/lock files from Kuzu
    if pack_dir:
        db_path = pack_dir / "pack.db"
        if db_path.exists():
            if db_path.is_dir():
                shutil.rmtree(db_path)
            else:
                db_path.unlink()
        # Also clean up WAL and lock files that Kuzu leaves behind
        for pattern in ("pack.db.wal", "pack.db.lock", ".wal", ".lock"):
            for f in pack_dir.glob(pattern):
                f.unlink()
        logger.info(f"[{pack_name}] Cleaned old database files")

    # Run build script
    cmd = [sys.executable, str(script_path)]
    if test_mode:
        cmd.append("--test-mode")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min timeout per pack
            env={**os.environ, "TOKENIZERS_PARALLELISM": "false", "LOKY_MAX_CPU_COUNT": "1"},
        )
        elapsed = time.time() - start

        if result.returncode == 0:
            logger.info(f"[{pack_name}] Built successfully in {elapsed:.0f}s")
            return {"pack": pack_name, "status": "success", "elapsed": elapsed}
        else:
            stderr_tail = result.stderr[-500:] if result.stderr else ""
            logger.error(f"[{pack_name}] Build failed (exit {result.returncode}): {stderr_tail}")
            return {"pack": pack_name, "status": "failed", "elapsed": elapsed, "error": stderr_tail}
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        logger.error(f"[{pack_name}] Build timed out after {elapsed:.0f}s")
        return {"pack": pack_name, "status": "timeout", "elapsed": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        from wikigr.utils import sanitize_error

        logger.error(f"[{pack_name}] Build error: {sanitize_error(str(e))}")
        return {
            "pack": pack_name,
            "status": "error",
            "elapsed": elapsed,
            "error": sanitize_error(str(e)),
        }


def main():
    parser = argparse.ArgumentParser(description="Rebuild all knowledge packs with LadybugDB")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers (default: 4)")
    parser.add_argument("--test-mode", action="store_true", help="Build 5-URL packs for testing")
    args = parser.parse_args()

    Path("logs").mkdir(exist_ok=True)
    scripts = find_build_scripts()
    total = len(scripts)

    logger.info(f"Rebuilding {total} packs with {args.workers} workers")
    if args.test_mode:
        logger.info("TEST MODE: 5 URLs per pack")

    results = []
    start_all = time.time()

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(rebuild_pack, script, args.test_mode): script for script in scripts
        }
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            status = result["status"]
            name = result["pack"]
            elapsed = result["elapsed"]
            logger.info(f"[{i}/{total}] {name}: {status} ({elapsed:.0f}s)")

    total_elapsed = time.time() - start_all
    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] != "success"]

    logger.info(f"\n{'='*60}")
    logger.info(f"REBUILD COMPLETE: {len(successes)}/{total} succeeded in {total_elapsed:.0f}s")
    if failures:
        logger.info(f"FAILURES ({len(failures)}):")
        for f in failures:
            logger.info(f"  - {f['pack']}: {f['status']}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
