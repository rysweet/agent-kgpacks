"""
WikiGR CLI - Build Wikipedia knowledge graphs from topics.

Usage:
    wikigr create --topics topics.md [--db data/] [--target 500]
        Creates one database per topic under the --db directory.

    wikigr create --seeds seeds.json [--db data/my.db] [--target 1000]
        Creates a single database from a pre-generated seeds file.
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

    orch = RyuGraphOrchestrator(
        db_path=db_path,
        max_depth=args.max_depth,
        batch_size=args.batch_size,
    )
    orch.initialize_seeds(seed_titles)

    start_time = time.time()
    print(f"Expanding to {args.target} articles (max_depth={args.max_depth})...")

    try:
        stats = orch.expand_to_target(target_count=args.target)
        elapsed = time.time() - start_time
        print(f"  Done in {elapsed / 60:.1f} minutes — {stats}")
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n  Interrupted after {elapsed / 60:.1f} minutes")
        raise
    finally:
        orch.close()


def cmd_create(args: argparse.Namespace) -> None:
    """Execute the 'create' subcommand."""
    # Prevent sentence-transformers semaphore leak in long runs
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("JOBLIB_START_METHOD", "fork")
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

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
    create_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    create_parser.set_defaults(func=cmd_create)

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
