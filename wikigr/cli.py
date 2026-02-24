"""
WikiGR CLI - Build Wikipedia knowledge graphs from topics.

Usage:
    wikigr create --topics topics.md [--db data/] [--target 500]
        Creates one database per topic under the --db directory.

    wikigr create --seeds seeds.json [--db data/my.db] [--target 1000]
        Creates a single database from a pre-generated seeds file.

    wikigr update --db data/kg.db --target 2000 [--max-depth 3] [--batch-size 10]
        Resumes expansion on an existing database to a new target count.

    wikigr update --db data/kg.db --add-seeds new_seeds.json --target 5000
        Injects additional seed articles and resumes expansion.

    wikigr status --db data/kg.db
        Shows database statistics (articles, sections, edges by state).
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_topics_file(path: str) -> list[str]:
    """Parse a topics file into a list of topic strings.

    Supports:
        - Plain text: one topic per line
        - Markdown bullets: lines starting with '- ', '* ', or '1. '
        - Ignores blank lines and lines starting with '#'
    """
    topics: list[str] = []

    with open(path) as f:
        for line in f:
            line = line.strip()

            # Skip blanks and markdown headers
            if not line or line.startswith("#"):
                continue

            # Strip markdown bullet prefixes
            line = re.sub(r"^[-*]\s+", "", line)
            line = re.sub(r"^\d+\.\s+", "", line)

            if line:
                topics.append(line)

    return topics


def create_schema(db_path: str) -> None:
    """Create Kuzu schema for a fresh WikiGR database.

    Uses FLOAT[384] for embeddings to match sentence-transformers float32 output.
    """
    import kuzu

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    conn.execute(
        "CREATE NODE TABLE Article(title STRING, category STRING, word_count INT32,"
        " expansion_state STRING, expansion_depth INT32, claimed_at TIMESTAMP,"
        " processed_at TIMESTAMP, retry_count INT32, PRIMARY KEY(title))"
    )
    conn.execute(
        "CREATE NODE TABLE Section(section_id STRING, title STRING, content STRING,"
        " word_count INT32, level INT32, embedding FLOAT[384], PRIMARY KEY(section_id))"
    )
    conn.execute("CREATE NODE TABLE Category(name STRING, article_count INT32, PRIMARY KEY(name))")
    conn.execute("CREATE REL TABLE HAS_SECTION(FROM Article TO Section, section_index INT32)")
    conn.execute("CREATE REL TABLE LINKS_TO(FROM Article TO Article, link_type STRING)")
    conn.execute("CREATE REL TABLE IN_CATEGORY(FROM Article TO Category)")
    conn.execute(
        "CALL CREATE_VECTOR_INDEX('Section', 'embedding_idx', 'embedding', metric := 'cosine')"
    )

    del conn
    del db

    logger.info(f"Schema created at {db_path}")


def _slugify(topic: str) -> str:
    """Convert a topic string to a filesystem-safe slug."""
    slug = topic.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _expand_seeds(seed_data: dict, db_path: str, args: argparse.Namespace) -> None:
    """Create a fresh DB and expand seeds into a knowledge graph."""
    seed_titles = [s["title"] for s in seed_data["seeds"]]
    if not seed_titles:
        print(f"  Skipping {db_path}: no seeds", file=sys.stderr)
        return

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # Remove stale DB files (with safety check)
    for suffix in ["", ".wal"]:
        p = Path(db_path + suffix)
        if p.exists():
            if p.is_symlink():
                p.unlink()
            elif p.is_dir():
                # Safety: only remove if it looks like a Kuzu database directory
                if any(p.iterdir()) and not any(
                    f.name in ("catalog", "data.kz") for f in p.iterdir()
                ):
                    print(
                        f"Warning: {p} exists but doesn't look like a Kuzu database. "
                        f"Remove it manually or use a different --db path.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                import shutil

                shutil.rmtree(p)
            else:
                p.unlink()

    print(f"Creating database at {db_path} ({len(seed_titles)} seeds)...")
    create_schema(db_path)

    from bootstrap.src.expansion.orchestrator import RyuGraphOrchestrator

    num_workers = getattr(args, "workers", 1)
    orch = RyuGraphOrchestrator(
        db_path=db_path,
        max_depth=args.max_depth,
        batch_size=args.batch_size,
        num_workers=num_workers,
    )
    orch.initialize_seeds(seed_titles)

    start_time = time.time()
    workers_msg = f", workers={num_workers}" if num_workers > 1 else ""
    print(f"Expanding to {args.target} articles (max_depth={args.max_depth}{workers_msg})...")

    try:
        stats = orch.expand_to_target(target_count=args.target)
        elapsed = time.time() - start_time
        print(f"  Done in {elapsed / 60:.1f} minutes -- {stats}")
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n  Interrupted after {elapsed / 60:.1f} minutes")
        raise
    finally:
        orch.close()


def _create_from_urls(args: argparse.Namespace) -> None:
    """Build a knowledge graph from a list of URLs using WebContentSource."""
    if not args.urls:
        print("Error: --urls is required when --source=web", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.urls):
        print(f"Error: URL file not found: {args.urls}", file=sys.stderr)
        sys.exit(1)

    # Read URLs from file
    with open(args.urls) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        print(f"Error: no URLs found in {args.urls}", file=sys.stderr)
        sys.exit(1)

    print(f"Building knowledge graph from {len(urls)} URLs...")

    from bootstrap.src.sources.web import WebContentSource

    source = WebContentSource()
    db_path = args.db if args.db.endswith(".db") else os.path.join(args.db, "web-kg.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # Create fresh database
    create_schema(db_path)

    import kuzu

    from bootstrap.src.embeddings import EmbeddingGenerator

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    embedder = EmbeddingGenerator()

    success = 0
    for url in urls:
        try:
            article = source.fetch_article(url)
            sections = source.parse_sections(article.content)
            if not sections:
                print(f"  Skipping (no sections): {url}")
                continue

            # Generate embeddings
            texts = [s["content"] for s in sections]
            embeddings = embedder.generate(texts, show_progress=False)

            # Insert article
            conn.execute(
                "CREATE (a:Article {title: $title, category: $category, word_count: $wc,"
                " expansion_state: 'loaded', expansion_depth: 0, claimed_at: NULL,"
                " processed_at: NULL, retry_count: 0})",
                {
                    "title": article.title,
                    "category": article.categories[0] if article.categories else "Web",
                    "wc": len(article.content.split()),
                },
            )

            # Insert sections
            for i, (section, embedding) in enumerate(zip(sections, embeddings)):
                section_id = f"{article.title}#{i}"
                conn.execute(
                    "MATCH (a:Article {title: $at}) CREATE (a)-[:HAS_SECTION {section_index: $idx}]->"
                    "(s:Section {section_id: $sid, title: $t, content: $c, embedding: $e, level: $l, word_count: $wc})",
                    {
                        "at": article.title,
                        "idx": i,
                        "sid": section_id,
                        "t": section["title"],
                        "c": section["content"],
                        "e": embedding.tolist(),
                        "l": section["level"],
                        "wc": len(section["content"].split()),
                    },
                )

            # Create link edges
            for link_url in article.links[:20]:
                try:
                    link_article = source.fetch_article(link_url)
                    # Check if target already exists
                    r = conn.execute(
                        "MATCH (a:Article {title: $t}) RETURN COUNT(a) AS c",
                        {"t": link_article.title},
                    )
                    if r.get_as_df().iloc[0]["c"] == 0:
                        conn.execute(
                            "CREATE (a:Article {title: $t, category: 'Web', word_count: 0,"
                            " expansion_state: 'discovered', expansion_depth: 1, claimed_at: NULL,"
                            " processed_at: NULL, retry_count: 0})",
                            {"t": link_article.title},
                        )
                except Exception:
                    pass  # Link targets are best-effort

            success += 1
            print(f"  Loaded: {article.title} ({len(sections)} sections)")
        except Exception as e:
            print(f"  Failed: {url} -- {e}")

    del conn, db
    print(f"\nLoaded {success}/{len(urls)} URLs into {db_path}")


def cmd_create(args: argparse.Namespace) -> None:
    """Execute the 'create' subcommand."""
    # Prevent sentence-transformers semaphore leak in long runs
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("JOBLIB_START_METHOD", "fork")
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

    # Web source mode
    if getattr(args, "source", "wikipedia") == "web":
        _create_from_urls(args)
        return

    if args.topics:
        if not os.path.isfile(args.topics):
            print(f"Error: topics file not found: {args.topics}", file=sys.stderr)
            sys.exit(1)
        topics = parse_topics_file(args.topics)
        if not topics:
            print(f"Error: no topics found in {args.topics}", file=sys.stderr)
            sys.exit(1)

        print(f"Generating seeds for {len(topics)} topics: {topics}")

        from wikigr.agent.seed_agent import SeedAgent

        agent = SeedAgent(seeds_per_topic=args.seeds_per_topic)
        seeds_by_topic = agent.generate_seeds_by_topic(topics)

        total = sum(d["metadata"]["total_seeds"] for d in seeds_by_topic.values())
        print(f"Generated {total} validated seeds across {len(topics)} topics")

        # Save all seeds if requested
        if args.seeds_output:
            out_dir = args.seeds_output
            os.makedirs(out_dir, exist_ok=True)
            for topic, seed_data in seeds_by_topic.items():
                path = os.path.join(out_dir, f"{_slugify(topic)}.json")
                with open(path, "w") as f:
                    json.dump(seed_data, f, indent=2)
            print(f"Seeds saved to {out_dir}/")

        if args.seeds_only:
            for topic, seed_data in seeds_by_topic.items():
                print(f"\n=== {topic} ({seed_data['metadata']['total_seeds']} seeds) ===")
                print(json.dumps(seed_data, indent=2))
            return

        # Build one DB per topic
        db_dir = args.db
        os.makedirs(db_dir, exist_ok=True)

        for topic, seed_data in seeds_by_topic.items():
            db_path = os.path.join(db_dir, f"{_slugify(topic)}.db")
            print(f"\n{'=' * 60}")
            print(f"Topic: {topic}")
            print(f"{'=' * 60}")
            _expand_seeds(seed_data, db_path, args)
            print(f"Knowledge graph ready: {db_path}")

        print(f"\nAll {len(topics)} knowledge graphs built in {db_dir}/")

    else:
        # --seeds: single seed file -> single DB
        with open(args.seeds) as f:
            seed_data = json.load(f)

        _expand_seeds(seed_data, args.db, args)
        print(f"\nKnowledge graph ready at: {args.db}")


def _get_db_stats(db_path: str) -> dict:
    """Query an existing Kuzu database for comprehensive statistics.

    Returns a dict with keys: loaded, discovered, claimed, processed,
    failed, total_articles, sections, edges.
    """
    import kuzu

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # Article counts by expansion state
    result = conn.execute("""
        MATCH (a:Article)
        WHERE a.expansion_state IS NOT NULL
        RETURN a.expansion_state AS state, COUNT(a) AS count
    """)
    df = result.get_as_df()

    stats: dict = {
        "discovered": 0,
        "claimed": 0,
        "loaded": 0,
        "processed": 0,
        "failed": 0,
        "total_articles": 0,
    }
    for _, row in df.iterrows():
        state = row["state"]
        count = int(row["count"])
        if state in stats:
            stats[state] = count
        stats["total_articles"] += count

    # Loaded = articles with actual content (word_count > 0)
    result = conn.execute("""
        MATCH (a:Article) WHERE a.word_count > 0
        RETURN COUNT(a) AS count
    """)
    stats["loaded_with_content"] = int(result.get_as_df().iloc[0]["count"])

    # Sections
    result = conn.execute("MATCH (s:Section) RETURN COUNT(s) AS count")
    stats["sections"] = int(result.get_as_df().iloc[0]["count"])

    # Edges (all relationship types)
    edge_count = 0
    for rel_table in ["HAS_SECTION", "LINKS_TO", "IN_CATEGORY"]:
        try:
            result = conn.execute(f"MATCH ()-[r:{rel_table}]->() RETURN COUNT(r) AS count")
            edge_count += int(result.get_as_df().iloc[0]["count"])
        except Exception as e:
            # Table may not exist in older schemas — safe to skip
            logger.debug(f"Edge count query failed for {rel_table}: {e}")
    stats["edges"] = edge_count

    # Categories
    try:
        result = conn.execute("MATCH (c:Category) RETURN COUNT(c) AS count")
        stats["categories"] = int(result.get_as_df().iloc[0]["count"])
    except Exception:
        stats["categories"] = 0

    del conn
    del db

    return stats


def cmd_update(args: argparse.Namespace) -> None:
    """Execute the 'update' subcommand: resume expansion on an existing database."""
    # Prevent sentence-transformers semaphore leak in long runs
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("JOBLIB_START_METHOD", "fork")
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

    db_path = args.db
    if not Path(db_path).exists():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    # Check current state
    import kuzu

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    result = conn.execute("MATCH (a:Article) WHERE a.word_count > 0 RETURN COUNT(a) AS count")
    current = int(result.get_as_df().iloc[0]["count"])
    print(f"Current articles: {current}, target: {args.target}")

    # Inject additional seeds if requested
    if args.add_seeds:
        seeds_path = args.add_seeds
        if not Path(seeds_path).exists():
            print(f"Error: seeds file not found: {seeds_path}", file=sys.stderr)
            del conn, db
            sys.exit(1)

        with open(seeds_path) as f:
            seed_data = json.load(f)

        seed_titles = [s["title"] for s in seed_data.get("seeds", [])]
        if not seed_titles:
            print("Warning: seeds file contains no seed entries", file=sys.stderr)
        else:
            added = 0
            for title in seed_titles:
                # Check if article already exists
                check = conn.execute(
                    "MATCH (a:Article {title: $title}) RETURN COUNT(a) AS count",
                    {"title": title},
                )
                if int(check.get_as_df().iloc[0]["count"]) > 0:
                    logger.info(f"Seed already exists, skipping: {title}")
                    continue

                # Determine category from seed data
                category = "General"
                for s in seed_data["seeds"]:
                    if s["title"] == title:
                        category = s.get("category", "General")
                        break

                conn.execute(
                    """
                    CREATE (a:Article {
                        title: $title,
                        category: $category,
                        word_count: 0,
                        expansion_state: 'discovered',
                        expansion_depth: 0,
                        claimed_at: NULL,
                        processed_at: NULL,
                        retry_count: 0
                    })
                    """,
                    {"title": title, "category": category},
                )
                added += 1

            print(f"Added {added} new seed articles from {seeds_path}")

    # Release the connection before the orchestrator opens its own
    del conn, db

    if current >= args.target:
        print("Already at or above target. Nothing to do.")
        return

    # Resume expansion
    from bootstrap.src.expansion.orchestrator import RyuGraphOrchestrator

    orch = RyuGraphOrchestrator(
        db_path=db_path,
        max_depth=args.max_depth,
        batch_size=args.batch_size,
        num_workers=getattr(args, "workers", 1),
    )

    start_time = time.time()
    remaining = args.target - current
    print(
        f"Expanding from {current} to {args.target} articles"
        f" ({remaining} remaining, max_depth={args.max_depth})..."
    )

    try:
        stats = orch.expand_to_target(target_count=args.target)
        elapsed = time.time() - start_time
        print(f"  Done in {elapsed / 60:.1f} minutes -- {stats}")
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n  Interrupted after {elapsed / 60:.1f} minutes")
        raise
    finally:
        orch.close()


def cmd_status(args: argparse.Namespace) -> None:
    """Execute the 'status' subcommand: show database statistics."""
    db_path = args.db
    if not Path(db_path).exists():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    stats = _get_db_stats(db_path)

    print(f"Database: {db_path}")
    print(f"{'=' * 50}")
    print(f"  Articles (total):       {stats['total_articles']:>8}")
    print(f"    Loaded (content):     {stats['loaded_with_content']:>8}")
    print(f"    Discovered (queued):  {stats['discovered']:>8}")
    print(f"    Claimed (in-flight):  {stats['claimed']:>8}")
    print(f"    Processed:            {stats['processed']:>8}")
    print(f"    Failed:               {stats['failed']:>8}")
    print(f"  Sections:               {stats['sections']:>8}")
    print(f"  Categories:             {stats['categories']:>8}")
    print(f"  Edges (total):          {stats['edges']:>8}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wikigr",
        description="WikiGR - Build Wikipedia knowledge graphs",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'create' subcommand
    create_parser = subparsers.add_parser(
        "create", help="Create a knowledge graph from topics or seeds"
    )

    # Input source (mutually exclusive)
    input_group = create_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--topics", type=str, help="Path to topics file (markdown or text)")
    input_group.add_argument("--seeds", type=str, help="Path to pre-generated seeds JSON")

    # Output and expansion options
    create_parser.add_argument(
        "--db",
        type=str,
        default="data",
        help="Database directory (--topics) or file path (--seeds)",
    )
    create_parser.add_argument(
        "--target", type=int, default=1000, help="Target article count per topic"
    )
    create_parser.add_argument("--max-depth", type=int, default=2, help="Max expansion depth")
    create_parser.add_argument(
        "--seeds-per-topic", type=int, default=10, help="Seeds to generate per topic"
    )
    create_parser.add_argument(
        "--seeds-only", action="store_true", help="Only generate seeds, don't expand"
    )
    create_parser.add_argument(
        "--seeds-output", type=str, help="Directory to save per-topic seed JSON files"
    )
    create_parser.add_argument("--batch-size", type=int, default=10, help="Expansion batch size")
    create_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel expansion workers (1 = sequential, max 10)",
    )
    create_parser.add_argument(
        "--source",
        type=str,
        choices=["wikipedia", "web"],
        default="wikipedia",
        help="Content source: 'wikipedia' (default) or 'web' for generic URLs",
    )
    create_parser.add_argument(
        "--urls",
        type=str,
        help="Path to file containing URLs (one per line). Required when --source=web",
    )
    create_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    create_parser.set_defaults(func=cmd_create)

    # 'update' subcommand
    update_parser = subparsers.add_parser("update", help="Resume expansion on an existing database")
    update_parser.add_argument(
        "--db", type=str, required=True, help="Path to existing Kuzu database"
    )
    update_parser.add_argument("--target", type=int, required=True, help="Target article count")
    update_parser.add_argument("--max-depth", type=int, default=3, help="Max expansion depth")
    update_parser.add_argument("--batch-size", type=int, default=10, help="Expansion batch size")
    update_parser.add_argument(
        "--add-seeds",
        type=str,
        default=None,
        help="Path to seeds JSON to inject before expanding",
    )
    update_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel expansion workers (default: 1)",
    )
    update_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    update_parser.set_defaults(func=cmd_update)

    # 'status' subcommand
    status_parser = subparsers.add_parser("status", help="Show database statistics")
    status_parser.add_argument(
        "--db", type=str, required=True, help="Path to existing Kuzu database"
    )
    status_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    args.func(args)


if __name__ == "__main__":
    main()
