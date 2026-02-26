#!/usr/bin/env python3
"""Audit content quality of knowledge pack databases.

Compares article word counts across packs to identify thin content articles
(< 200 words) that may degrade Q&A accuracy.

Usage:
    python scripts/audit_pack_content.py data/packs/dotnet-expert/pack.db
    python scripts/audit_pack_content.py --all
    python scripts/audit_pack_content.py --compare dotnet-expert physics-expert
"""

import argparse
import logging
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import kuzu  # noqa: E402

logger = logging.getLogger(__name__)

THIN_CONTENT_THRESHOLD = 200
# Anchor to project root relative to this script file (scripts/ -> parent = project root)
PACKS_DIR = Path(__file__).parent.parent / "data" / "packs"


def open_db(db_path: Path) -> kuzu.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    db = kuzu.Database(str(db_path), read_only=True)
    return kuzu.Connection(db)


def query_article_word_counts(conn: kuzu.Connection) -> list[dict]:
    """Query articles ordered by word count ascending.

    Uses stored word_count on Article nodes; falls back to Section content.
    """
    try:
        result = conn.execute(
            "MATCH (a:Article) RETURN a.title AS title, a.word_count AS word_count "
            "ORDER BY a.word_count ASC"
        )
        rows = result.get_as_df()
        if not rows.empty and "word_count" in rows.columns:
            return rows[["title", "word_count"]].to_dict("records")
    except Exception as exc:
        logger.debug(
            "word_count column unavailable, falling back to Section content query: %s", exc
        )

    try:
        result = conn.execute(
            "MATCH (a:Article)-[:HAS_SECTION]->(s:Section) "
            "RETURN a.title AS title, s.content AS content"
        )
        rows = result.get_as_df()
        if rows.empty:
            return []
        rows["words"] = rows["content"].fillna("").apply(lambda t: len(str(t).split()))
        agg = rows.groupby("title")["words"].sum().reset_index()
        agg.columns = ["title", "word_count"]
        return agg.sort_values("word_count").to_dict("records")
    except Exception as exc:
        raise RuntimeError(f"Failed to query article word counts: {exc}") from exc


def compute_stats(word_counts: list[int]) -> dict:
    if not word_counts:
        return {"count": 0, "min": 0, "max": 0, "avg": 0, "median": 0}
    return {
        "count": len(word_counts),
        "min": min(word_counts),
        "max": max(word_counts),
        "avg": round(statistics.mean(word_counts), 1),
        "median": round(statistics.median(word_counts), 1),
    }


def audit_pack(db_path: Path, thin_threshold: int = THIN_CONTENT_THRESHOLD) -> dict:
    conn = open_db(db_path)
    articles = query_article_word_counts(conn)

    if not articles:
        return {
            "pack": db_path.parent.name,
            "db_path": str(db_path),
            "total_articles": 0,
            "thin_articles": [],
            "stats": compute_stats([]),
            "thin_count": 0,
            "thin_pct": 0.0,
        }

    word_counts = [int(a["word_count"] or 0) for a in articles]
    thin = [a for a in articles if int(a["word_count"] or 0) < thin_threshold]

    return {
        "pack": db_path.parent.name,
        "db_path": str(db_path),
        "total_articles": len(articles),
        "thin_articles": thin,
        "stats": compute_stats(word_counts),
        "thin_count": len(thin),
        "thin_pct": round(100 * len(thin) / len(articles), 1),
    }


def print_report(report: dict, thin_threshold: int = THIN_CONTENT_THRESHOLD) -> None:
    print(f"\n{'=' * 60}")
    print(f"Pack: {report['pack']}")
    print(f"Database: {report['db_path']}")
    print(f"{'=' * 60}")

    stats = report["stats"]
    print(f"\nArticle Statistics ({stats['count']} articles):")
    print(f"  Min word count : {stats['min']}")
    print(f"  Max word count : {stats['max']}")
    print(f"  Avg word count : {stats['avg']}")
    print(f"  Median word cnt: {stats['median']}")

    thin_count = report["thin_count"]
    thin_pct = report["thin_pct"]
    print(f"\nThin Content (< {thin_threshold} words): {thin_count} articles ({thin_pct}%)")

    if report["thin_articles"]:
        print("\nBottom 50 articles by word count:")
        for i, art in enumerate(report["thin_articles"][:50], 1):
            print(f"  {i:3}. [{int(art['word_count'] or 0):5} words] {art['title']}")


def print_comparison(reports: list[dict], thin_threshold: int = THIN_CONTENT_THRESHOLD) -> None:
    print(f"\n{'=' * 70}")
    print("Content Quality Comparison")
    print(f"{'=' * 70}")
    print(f"{'Pack':<25} {'Articles':>8} {'Thin':>6} {'Thin%':>6} {'Avg WC':>7} {'Median':>7}")
    print("-" * 70)
    for r in reports:
        s = r["stats"]
        print(
            f"{r['pack']:<25} {s['count']:>8} {r['thin_count']:>6} {r['thin_pct']:>5.1f}%"
            f" {s['avg']:>7.0f} {s['median']:>7.0f}"
        )
    print(f"\nThin content threshold: < {thin_threshold} words")


def find_all_pack_dbs() -> list[Path]:
    return sorted(PACKS_DIR.glob("*/pack.db"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit knowledge pack content quality")
    parser.add_argument("db_paths", nargs="*", help="Path(s) to pack.db files")
    parser.add_argument("--all", action="store_true", help="Audit all packs in data/packs/")
    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="PACK",
        help="Compare named packs (e.g., dotnet-expert physics-expert)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=THIN_CONTENT_THRESHOLD,
        help=f"Thin content threshold in words (default: {THIN_CONTENT_THRESHOLD})",
    )
    args = parser.parse_args()

    db_paths: list[Path] = []

    if args.all:
        db_paths = find_all_pack_dbs()
        if not db_paths:
            print(f"No pack databases found under {PACKS_DIR}/")
            sys.exit(1)
    elif args.compare:
        for pack_name in args.compare:
            candidate = PACKS_DIR / pack_name / "pack.db"
            if not candidate.exists():
                print(f"Warning: {candidate} not found, skipping")
            else:
                db_paths.append(candidate)
    elif args.db_paths:
        db_paths = [Path(p) for p in args.db_paths]
    else:
        parser.print_help()
        sys.exit(0)

    if not db_paths:
        print("No valid databases to audit.")
        sys.exit(1)

    reports = []
    for db_path in db_paths:
        try:
            report = audit_pack(db_path, thin_threshold=args.threshold)
            reports.append(report)
            print_report(report, thin_threshold=args.threshold)
        except FileNotFoundError as exc:
            print(f"Error: {exc}")
        except Exception as exc:
            print(f"Error auditing {db_path}: {exc}")

    if len(reports) > 1:
        print_comparison(reports, thin_threshold=args.threshold)


if __name__ == "__main__":
    main()
