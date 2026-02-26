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

    Uses the shared schema definition from bootstrap.schema.ryugraph_schema.
    """
    from bootstrap.schema.ryugraph_schema import create_schema as _create_schema

    _create_schema(db_path, drop_existing=False)
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
    """Build a knowledge graph from a list of URLs using WebContentSource with BFS expansion."""
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

    print(f"Building knowledge graph from {len(urls)} seed URLs...")

    import kuzu

    from bootstrap.src.expansion.processor import ArticleProcessor
    from bootstrap.src.sources.web import WebContentSource

    # Get BFS parameters
    max_depth = getattr(args, "max_depth", 0)
    max_links = getattr(args, "max_links", len(urls))

    source = WebContentSource()
    db_path = args.db if args.db.endswith(".db") else os.path.join(args.db, "web-kg.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # Create fresh database
    create_schema(db_path)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # Initialize LLM extractor if ANTHROPIC_API_KEY is set
    llm_extractor = None
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from bootstrap.src.extraction.llm_extractor import LLMExtractor

            llm_extractor = LLMExtractor()
            print("  LLM extraction enabled (ANTHROPIC_API_KEY found)")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM extractor: {e}")

    # Initialize ArticleProcessor
    processor = ArticleProcessor(
        conn=conn,
        content_source=source,
        llm_extractor=llm_extractor,
    )

    # BFS expansion
    visited = set()
    queue = [(url, 0) for url in urls]  # (url, depth)
    success = 0
    failed = 0

    print(f"Starting BFS expansion (max_depth={max_depth}, max_links={max_links})...")

    while queue and len(visited) < max_links:
        url, depth = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        try:
            # Process article using ArticleProcessor
            success_flag, links, error = processor.process_article(
                title_or_url=url,
                category="Web",
                expansion_depth=depth,
            )

            if success_flag:
                success += 1
                print(
                    f"  [{success}/{max_links}] Loaded: {url} (depth={depth}, {len(links)} links)"
                )

                # Add links to queue if within depth limit
                if depth < max_depth and len(visited) < max_links:
                    for link_url in links:
                        if link_url not in visited:
                            queue.append((link_url, depth + 1))
            else:
                failed += 1
                print(f"  Failed: {url} -- {error}")

        except Exception as e:
            failed += 1
            print(f"  Failed: {url} -- {e}")
            logger.debug(f"Exception details for {url}: {e}", exc_info=True)

    del conn, db

    print(f"\nCompleted: {success} loaded, {failed} failed")
    print(f"Total URLs processed: {len(visited)}")
    print(f"Database: {db_path}")


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


def _update_from_urls(args: argparse.Namespace) -> None:
    """Update existing database with new URLs from web source."""
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

    print(f"Updating database with {len(urls)} seed URLs...")

    import kuzu

    from bootstrap.src.expansion.processor import ArticleProcessor
    from bootstrap.src.sources.web import WebContentSource

    # Get BFS parameters
    max_depth = getattr(args, "max_depth", 0)
    max_links = getattr(args, "max_links", len(urls))

    source = WebContentSource()
    db_path = args.db

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # Initialize LLM extractor if ANTHROPIC_API_KEY is set
    llm_extractor = None
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from bootstrap.src.extraction.llm_extractor import LLMExtractor

            llm_extractor = LLMExtractor()
            print("  LLM extraction enabled (ANTHROPIC_API_KEY found)")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM extractor: {e}")

    # Initialize ArticleProcessor
    processor = ArticleProcessor(
        conn=conn,
        content_source=source,
        llm_extractor=llm_extractor,
    )

    # Check which URLs already exist
    existing_titles = set()
    for url in urls:
        try:
            article = source.fetch_article(url)
            result = conn.execute(
                "MATCH (a:Article {title: $title}) RETURN COUNT(a) AS count",
                {"title": article.title},
            )
            if result.get_as_df().iloc[0]["count"] > 0:
                existing_titles.add(article.title)
                logger.info(f"Skipping existing article: {article.title}")
        except Exception as e:
            logger.debug(f"Failed to check URL {url}: {e}")

    print(
        f"  Found {len(existing_titles)} existing articles, processing {len(urls) - len(existing_titles)} new URLs"
    )

    # BFS expansion with duplicate detection
    visited = set()
    queue = [(url, 0) for url in urls]  # (url, depth)
    success = 0
    skipped = 0
    failed = 0

    print(f"Starting BFS expansion (max_depth={max_depth}, max_links={max_links})...")

    while queue and len(visited) < max_links:
        url, depth = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        try:
            # Check if article already exists (by title)
            article = source.fetch_article(url)
            result = conn.execute(
                "MATCH (a:Article {title: $title}) RETURN COUNT(a) AS count",
                {"title": article.title},
            )

            if result.get_as_df().iloc[0]["count"] > 0:
                skipped += 1
                print(f"  Skipping existing: {article.title}")
                continue

            # Process new article using ArticleProcessor
            success_flag, links, error = processor.process_article(
                title_or_url=url,
                category="Web",
                expansion_depth=depth,
            )

            if success_flag:
                success += 1
                print(
                    f"  [{success}/{max_links}] Added: {article.title} (depth={depth}, {len(links)} links)"
                )

                # Add links to queue if within depth limit
                if depth < max_depth and len(visited) < max_links:
                    for link_url in links:
                        if link_url not in visited:
                            queue.append((link_url, depth + 1))
            else:
                failed += 1
                print(f"  Failed: {url} -- {error}")

        except Exception as e:
            failed += 1
            print(f"  Failed: {url} -- {e}")
            logger.debug(f"Exception details for {url}: {e}", exc_info=True)

    del conn, db

    print(f"\nCompleted: {success} added, {skipped} skipped, {failed} failed")
    print(f"Total URLs processed: {len(visited)}")
    print(f"Database: {db_path}")


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

    # Web source mode
    if getattr(args, "source", "wikipedia") == "web":
        _update_from_urls(args)
        return

    # Wikipedia source mode (original logic)
    import kuzu

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    result = conn.execute("MATCH (a:Article) WHERE a.word_count > 0 RETURN COUNT(a) AS count")
    current = int(result.get_as_df().iloc[0]["count"])

    # Validate target is provided for Wikipedia source
    if not args.target:
        print("Error: --target is required for Wikipedia source updates", file=sys.stderr)
        del conn, db
        sys.exit(1)

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


def cmd_research_sources(args: argparse.Namespace) -> None:
    """Execute 'research-sources' subcommand: discover authoritative sources for a domain."""
    from datetime import datetime, timezone

    from wikigr.packs.seed_researcher import LLMSeedResearcher

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    print(f"Researching authoritative sources for: {args.domain}")
    print(f"Max sources: {args.max_sources}")

    researcher = LLMSeedResearcher()

    try:
        sources = researcher.discover_sources(args.domain, max_sources=args.max_sources)

        if not sources:
            print("No sources discovered.")
            return

        # Display results
        print(f"\n{'=' * 70}")
        print(f"Discovered {len(sources)} authoritative sources for '{args.domain}'")
        print(f"{'=' * 70}\n")

        for i, source in enumerate(sources, 1):
            print(f"{i}. {source.url}")
            print(f"   Authority: {source.authority_score:.2f}")
            print(f"   Type: {source.content_type}")
            print(f"   Estimated articles: {source.estimated_articles}")
            print(f"   Description: {source.description}")
            print()

        # Save to output file if requested
        if args.output:
            output_data = {
                "domain": args.domain,
                "discovered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "sources": [
                    {
                        "url": s.url,
                        "authority_score": s.authority_score,
                        "content_type": s.content_type,
                        "estimated_articles": s.estimated_articles,
                        "description": s.description,
                    }
                    for s in sources
                ],
            }

            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"Results saved to: {args.output}")

    except Exception as e:
        print(f"Error during source discovery: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pack_create(args: argparse.Namespace) -> None:
    """Execute 'pack create' subcommand."""
    from datetime import datetime, timezone

    from wikigr.agent.seed_agent import SeedAgent
    from wikigr.packs.manifest import GraphStats, PackManifest, save_manifest
    from wikigr.packs.skill_template import generate_skill_md

    # Auto-discovery mode
    if args.auto_discover:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("Error: ANTHROPIC_API_KEY required for --auto-discover", file=sys.stderr)
            sys.exit(1)

        print(f"Auto-discovering sources for domain: {args.auto_discover}")

        from wikigr.packs.seed_researcher import LLMSeedResearcher

        researcher = LLMSeedResearcher()

        # Discover sources
        try:
            sources = researcher.discover_sources(args.auto_discover, max_sources=10)
            print(f"Discovered {len(sources)} authoritative sources")

            # Extract URLs from top sources
            all_urls = []
            for source in sources[:3]:  # Use top 3 sources
                print(f"  Extracting URLs from {source.url}...")
                try:
                    urls = researcher.extract_article_urls(source.url, max_urls=50)
                    all_urls.extend(urls)
                    print(f"    Found {len(urls)} URLs")
                except Exception as e:
                    print(f"    Failed: {e}")
                    continue

            if not all_urls:
                print("Error: No URLs extracted from discovered sources", file=sys.stderr)
                sys.exit(1)

            print(f"\nTotal URLs extracted: {len(all_urls)}")

            # Create temporary URLs file
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                for url in all_urls:
                    f.write(url + "\n")
                temp_urls_path = f.name

            # Set up args for web source creation
            args.source = "web"
            args.urls = temp_urls_path
            args.topics = None  # Clear topics arg

            print(f"Creating pack from {len(all_urls)} discovered URLs...")

            # Continue with normal pack creation flow using web source
            # (handled below after topics parsing)

        except Exception as e:
            print(f"Error during auto-discovery: {e}", file=sys.stderr)
            sys.exit(1)

    # Parse topics (skip if auto-discover mode)
    if not args.auto_discover:
        if not os.path.isfile(args.topics):
            print(f"Error: topics file not found: {args.topics}", file=sys.stderr)
            sys.exit(1)

        topics = parse_topics_file(args.topics)
        if not topics:
            print(f"Error: no topics found in {args.topics}", file=sys.stderr)
            sys.exit(1)
    else:
        topics = [args.auto_discover]  # Use domain as topic

    # Create output directory
    output_dir = Path(args.output) / args.name
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Creating knowledge pack: {args.name}")
    print(f"  Topics: {topics}")
    print(f"  Target: {args.target} articles")
    print(f"  Output: {output_dir}")

    # Generate seeds
    print("\nGenerating seeds...")
    agent = SeedAgent(seeds_per_topic=10)
    seeds_by_topic = agent.generate_seeds_by_topic(topics)

    # Combine all seeds
    all_seeds = []
    for topic_seeds in seeds_by_topic.values():
        all_seeds.extend(topic_seeds["seeds"])

    # Create database
    db_path = output_dir / "pack.db"
    print(f"\nCreating database at {db_path}...")

    # Create temporary seeds file
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        seed_data = {"seeds": all_seeds, "metadata": {"total_seeds": len(all_seeds)}}
        json.dump(seed_data, f, indent=2)
        temp_seeds_path = f.name

    try:
        # Use existing expansion logic
        args_copy = argparse.Namespace(
            db=str(db_path),
            target=args.target,
            max_depth=2,
            batch_size=10,
            workers=1,
            verbose=False,
        )
        _expand_seeds(seed_data, str(db_path), args_copy)
    finally:
        os.unlink(temp_seeds_path)

    # Run LLM extraction if API key is available
    if os.getenv("ANTHROPIC_API_KEY"):
        print("\nRunning LLM knowledge extraction...")
        import kuzu

        from bootstrap.src.extraction.llm_extractor import get_extractor
        from bootstrap.src.wikipedia.api_client import WikipediaAPIClient
        from bootstrap.src.wikipedia.parser import parse_sections

        extractor = get_extractor()
        wiki_client = WikipediaAPIClient()
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        # Get all articles without entities
        result = conn.execute("MATCH (a:Article) RETURN a.title AS title")
        articles = [row["title"] for _, row in result.get_as_df().iterrows()]

        print(f"Extracting knowledge from {len(articles)} articles...")
        for i, title in enumerate(articles, 1):
            if i % 50 == 0:
                print(f"  Progress: {i}/{len(articles)} articles processed")

            try:
                # Fetch and parse article
                article = wiki_client.fetch_article(title)
                if not article or not article.wikitext:
                    continue

                sections = parse_sections(article.wikitext)
                if not sections:
                    continue

                # Extract knowledge
                extraction = extractor.extract_from_article(
                    title, sections, max_sections=5, domain="science"
                )

                # Insert entities, relationships, facts (same logic as build_physics_pack.py)
                for entity in extraction.entities:
                    conn.execute(
                        "MERGE (e:Entity {entity_id: $eid}) ON CREATE SET e.name = $name, e.type = $type",
                        {"eid": entity.name, "name": entity.name, "type": entity.type},
                    )
                    conn.execute(
                        "MATCH (a:Article {title: $title}), (e:Entity {entity_id: $eid}) MERGE (a)-[:HAS_ENTITY]->(e)",
                        {"title": title, "eid": entity.name},
                    )

                for rel in extraction.relationships:
                    conn.execute(
                        "MERGE (s:Entity {entity_id: $src}) ON CREATE SET s.name = $src, s.type = 'concept'",
                        {"src": rel.source},
                    )
                    conn.execute(
                        "MERGE (t:Entity {entity_id: $tgt}) ON CREATE SET t.name = $tgt, t.type = 'concept'",
                        {"tgt": rel.target},
                    )
                    conn.execute(
                        "MATCH (s:Entity {entity_id: $src}), (t:Entity {entity_id: $tgt}) MERGE (s)-[:ENTITY_RELATION {relation: $rel, context: $ctx}]->(t)",
                        {
                            "src": rel.source,
                            "tgt": rel.target,
                            "rel": rel.relation,
                            "ctx": rel.context,
                        },
                    )

                for idx, fact in enumerate(extraction.key_facts):
                    conn.execute(
                        "MATCH (a:Article {title: $title}) CREATE (a)-[:HAS_FACT]->(f:Fact {fact_id: $fid, content: $content})",
                        {"title": title, "fid": f"{title}:fact:{idx}", "content": fact},
                    )

            except Exception as e:
                logger.debug(f"Failed to extract knowledge from {title}: {e}")
                continue

        print("✓ Knowledge extraction complete")
    else:
        print("\nSkipping LLM extraction (ANTHROPIC_API_KEY not set)")

    # Get database stats (now accurate with entities/relationships)
    import kuzu

    db_for_stats = kuzu.Database(str(db_path))
    conn_stats = kuzu.Connection(db_for_stats)

    article_count = (
        conn_stats.execute("MATCH (a:Article) RETURN count(a) AS count")
        .get_as_df()
        .iloc[0]["count"]
    )
    entity_count = (
        conn_stats.execute("MATCH (e:Entity) RETURN count(e) AS count").get_as_df().iloc[0]["count"]
    )
    rel_count = (
        conn_stats.execute("MATCH ()-[r:ENTITY_RELATION]->() RETURN count(r) AS count")
        .get_as_df()
        .iloc[0]["count"]
    )

    # Create manifest
    manifest = PackManifest(
        name=args.name,
        version="1.0.0",
        description=f"Knowledge pack for {', '.join(topics)}",
        author=os.environ.get("USER", "unknown"),
        license="MIT",
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        topics=topics,
        graph_stats=GraphStats(
            articles=int(article_count),
            entities=int(entity_count),
            relationships=int(rel_count),
            size_mb=int(
                sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file()) / 1024 / 1024
            ),
        ),
        eval_scores=None,
    )

    manifest_path = output_dir / "manifest.json"
    save_manifest(manifest, manifest_path)
    print(f"Manifest created: {manifest_path}")

    # Generate skill.md
    skill_md_content = generate_skill_md(manifest)
    skill_path = output_dir / "skill.md"
    skill_path.write_text(skill_md_content)
    print(f"Skill created: {skill_path}")

    # Create kg_config.json
    kg_config = {
        "db_path": str(db_path),
        "topics": topics,
    }
    kg_config_path = output_dir / "kg_config.json"
    kg_config_path.write_text(json.dumps(kg_config, indent=2))
    print(f"KG config created: {kg_config_path}")

    # Create eval questions if provided
    if args.eval_questions and os.path.isfile(args.eval_questions):
        import shutil

        dest_eval = output_dir / "eval_questions.jsonl"
        shutil.copy(args.eval_questions, dest_eval)
        print(f"Eval questions copied: {dest_eval}")

    print(f"\nKnowledge pack created successfully at {output_dir}")


def cmd_pack_install(args: argparse.Namespace) -> None:
    """Execute 'pack install' subcommand."""
    from wikigr.packs.installer import PackInstaller

    installer = PackInstaller()

    source = args.source
    print(f"Installing pack from {source}...")

    try:
        if source.startswith("http://") or source.startswith("https://"):
            pack_info = installer.install_from_url(source)
        else:
            pack_info = installer.install_from_file(Path(source))

        print(f"Successfully installed: {pack_info.name} v{pack_info.version}")
        print(f"Location: {pack_info.path}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during installation: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pack_list(args: argparse.Namespace) -> None:
    """Execute 'pack list' subcommand."""
    from wikigr.packs.discovery import discover_packs

    # Use explicit path from environment
    packs_dir = Path(os.environ.get("HOME", Path.home().as_posix())) / ".wikigr/packs"
    packs = discover_packs(packs_dir)

    if not packs:
        if args.format == "json":
            print("[]")
        else:
            print("No packs installed.")
        return

    if args.format == "json":
        import json

        data = [
            {
                "name": pack.name,
                "version": pack.version,
                "description": pack.manifest.description,
                "topics": pack.manifest.topics or [],
                "path": str(pack.path),
            }
            for pack in packs
        ]
        print(json.dumps(data, indent=2))
    else:
        print(f"Installed knowledge packs ({len(packs)}):\n")
        for pack in packs:
            print(f"  {pack.name:<30} v{pack.version:<10} {pack.manifest.description}")


def cmd_pack_info(args: argparse.Namespace) -> None:
    """Execute 'pack info' subcommand."""
    from wikigr.packs.discovery import discover_packs

    # Use explicit path from environment
    packs_dir = Path(os.environ.get("HOME", Path.home().as_posix())) / ".wikigr/packs"
    packs = discover_packs(packs_dir)
    pack = next((p for p in packs if p.name == args.name), None)

    if not pack:
        print(f"Error: pack '{args.name}' not found", file=sys.stderr)
        sys.exit(1)

    print(f"Pack: {pack.name}")
    print(f"Version: {pack.version}")
    print(f"Description: {pack.manifest.description}")
    print(f"Author: {pack.manifest.author or 'N/A'}")
    print(f"License: {pack.manifest.license}")
    print(f"Created: {pack.manifest.created_at}")
    print(f"Topics: {', '.join(pack.manifest.topics or [])}")
    print(f"Path: {pack.path}")
    print("\nGraph Statistics:")
    print(f"  Articles: {pack.manifest.graph_stats.articles}")
    print(f"  Entities: {pack.manifest.graph_stats.entities}")
    print(f"  Relationships: {pack.manifest.graph_stats.relationships}")
    print(f"  Size: {pack.manifest.graph_stats.size_mb} MB")

    if args.show_eval_scores:
        eval_results_path = pack.path / "eval_results.json"
        if eval_results_path.exists():
            with open(eval_results_path) as f:
                results = json.load(f)

            print("\nEvaluation Scores:")
            kp_metrics = results.get("knowledge_pack", {})
            print(f"  Accuracy: {kp_metrics.get('accuracy', 0):.2f}")
            print(f"  Hallucination Rate: {kp_metrics.get('hallucination_rate', 0):.2f}")
            print(f"  Citation Quality: {kp_metrics.get('citation_quality', 0):.2f}")
            print(f"\n  Surpasses Training: {results.get('surpasses_training', False)}")
            print(f"  Surpasses Web: {results.get('surpasses_web', False)}")
        else:
            print("\nNo evaluation results available.")


def cmd_pack_eval(args: argparse.Namespace) -> None:
    """Execute 'pack eval' subcommand."""
    from wikigr.packs.discovery import discover_packs
    from wikigr.packs.eval import EvalRunner, load_questions_jsonl

    # Use explicit path from environment
    packs_dir = Path(os.environ.get("HOME", Path.home().as_posix())) / ".wikigr/packs"
    packs = discover_packs(packs_dir)
    pack = next((p for p in packs if p.name == args.name), None)

    if not pack:
        print(f"Error: pack '{args.name}' not found", file=sys.stderr)
        sys.exit(1)

    # Load questions
    questions_path = Path(args.questions) if args.questions else pack.path / "eval_questions.jsonl"

    if not questions_path.exists():
        print(f"Error: questions file not found: {questions_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading evaluation questions from {questions_path}...")
    questions = load_questions_jsonl(questions_path)
    print(f"Loaded {len(questions)} questions")

    # Run evaluation
    print("\nRunning three-baseline evaluation...")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    runner = EvalRunner(pack.path, api_key=api_key)
    result = runner.run_evaluation(questions)

    # Display results
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"\nKnowledge Pack: {result.pack_name}")
    print(f"Questions Tested: {result.questions_tested}")
    print(f"Timestamp: {result.timestamp}")

    print("\n--- Knowledge Pack Metrics ---")
    print(f"  Accuracy: {result.knowledge_pack.accuracy:.2f}")
    print(f"  Hallucination Rate: {result.knowledge_pack.hallucination_rate:.2f}")
    print(f"  Citation Quality: {result.knowledge_pack.citation_quality:.2f}")

    print("\n--- Training Baseline Metrics ---")
    print(f"  Accuracy: {result.training_baseline.accuracy:.2f}")
    print(f"  Hallucination Rate: {result.training_baseline.hallucination_rate:.2f}")
    print(f"  Citation Quality: {result.training_baseline.citation_quality:.2f}")

    print("\n--- Web Search Baseline Metrics ---")
    print(f"  Accuracy: {result.web_search_baseline.accuracy:.2f}")
    print(f"  Hallucination Rate: {result.web_search_baseline.hallucination_rate:.2f}")
    print(f"  Citation Quality: {result.web_search_baseline.citation_quality:.2f}")

    print("\n--- Comparison ---")
    print(f"  Surpasses Training: {'YES' if result.surpasses_training else 'NO'}")
    print(f"  Surpasses Web: {'YES' if result.surpasses_web else 'NO'}")

    # Save results if requested
    if args.save_results:
        from dataclasses import asdict

        results_path = pack.path / "eval_results.json"
        with open(results_path, "w") as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\nResults saved to {results_path}")


def cmd_pack_update(args: argparse.Namespace) -> None:
    """Execute 'pack update' subcommand."""
    from wikigr.packs.discovery import discover_packs
    from wikigr.packs.installer import PackInstaller

    # Use explicit path from environment
    packs_dir = Path(os.environ.get("HOME", Path.home().as_posix())) / ".wikigr/packs"
    packs = discover_packs(packs_dir)
    pack = next((p for p in packs if p.name == args.name), None)

    if not pack:
        print(f"Error: pack '{args.name}' not found", file=sys.stderr)
        sys.exit(1)

    print(f"Updating pack: {args.name}")
    print(f"Current version: {pack.version}")

    installer = PackInstaller()

    try:
        new_pack = installer.update(args.name, Path(args.from_archive))
        print(f"Successfully updated to version {new_pack.version}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during update: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pack_remove(args: argparse.Namespace) -> None:
    """Execute 'pack remove' subcommand."""
    from wikigr.packs.discovery import discover_packs
    from wikigr.packs.installer import PackInstaller

    # Use explicit path from environment
    packs_dir = Path(os.environ.get("HOME", Path.home().as_posix())) / ".wikigr/packs"
    packs = discover_packs(packs_dir)
    pack = next((p for p in packs if p.name == args.name), None)

    if not pack:
        print(f"Error: pack '{args.name}' not found", file=sys.stderr)
        sys.exit(1)

    # Confirm unless --force
    if not args.force:
        response = input(f"Remove pack '{args.name}'? (y/N): ")
        if response.lower() != "y":
            print("Cancelled.")
            return

    installer = PackInstaller()

    try:
        installer.uninstall(args.name)
        print(f"Successfully removed pack: {args.name}")
    except Exception as e:
        print(f"Error during removal: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_pack_validate(args: argparse.Namespace) -> None:
    """Execute 'pack validate' subcommand."""
    from wikigr.packs.validator import validate_pack_structure

    pack_path = Path(args.pack_dir)

    if not pack_path.exists():
        print(f"Error: directory not found: {pack_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Validating pack at {pack_path}...")

    errors = validate_pack_structure(pack_path, strict=args.strict)

    if not errors:
        print("Pack is valid.")
        sys.exit(0)
    else:
        print(f"Pack validation failed with {len(errors)} error(s):\n")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


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
    create_parser.add_argument(
        "--max-links",
        type=int,
        default=100,
        help="Maximum total pages to process (web source only, default: 100)",
    )
    create_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    create_parser.set_defaults(func=cmd_create)

    # 'update' subcommand
    update_parser = subparsers.add_parser("update", help="Resume expansion on an existing database")
    update_parser.add_argument(
        "--db", type=str, required=True, help="Path to existing Kuzu database"
    )
    update_parser.add_argument("--target", type=int, help="Target article count (Wikipedia source)")
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
    update_parser.add_argument(
        "--source",
        type=str,
        choices=["wikipedia", "web"],
        default="wikipedia",
        help="Content source: 'wikipedia' (default) or 'web' for generic URLs",
    )
    update_parser.add_argument(
        "--urls",
        type=str,
        help="Path to file containing URLs (one per line). Required when --source=web",
    )
    update_parser.add_argument(
        "--max-links",
        type=int,
        default=100,
        help="Maximum total pages to process (web source only, default: 100)",
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

    # 'research-sources' subcommand
    research_parser = subparsers.add_parser(
        "research-sources",
        help="Discover authoritative sources for a domain using LLM",
    )
    research_parser.add_argument("domain", type=str, help="Domain or topic to research")
    research_parser.add_argument(
        "--max-sources",
        type=int,
        default=10,
        help="Maximum number of sources to discover (default: 10)",
    )
    research_parser.add_argument(
        "--output", type=str, help="Path to save discovered sources as JSON"
    )
    research_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    research_parser.set_defaults(func=cmd_research_sources)

    # 'pack' subcommand group
    pack_parser = subparsers.add_parser("pack", help="Manage knowledge packs")
    pack_subparsers = pack_parser.add_subparsers(dest="pack_command", required=True)

    # pack create
    pack_create_parser = pack_subparsers.add_parser("create", help="Create a new knowledge pack")
    pack_create_parser.add_argument("--name", type=str, required=True, help="Pack name")
    pack_create_parser.add_argument(
        "--source",
        type=str,
        choices=["wikipedia", "web"],
        default="wikipedia",
        help="Content source",
    )
    # Make topics optional when using --auto-discover
    topics_group = pack_create_parser.add_mutually_exclusive_group(required=True)
    topics_group.add_argument("--topics", type=str, help="Path to topics file")
    topics_group.add_argument(
        "--auto-discover",
        type=str,
        metavar="DOMAIN",
        help="Auto-discover sources using LLM for given domain (e.g., '.NET programming')",
    )
    pack_create_parser.add_argument("--target", type=int, default=1000, help="Target article count")
    pack_create_parser.add_argument(
        "--eval-questions", type=str, help="Path to eval questions JSONL file"
    )
    pack_create_parser.add_argument("--output", type=str, required=True, help="Output directory")
    pack_create_parser.set_defaults(func=cmd_pack_create)

    # pack install
    pack_install_parser = pack_subparsers.add_parser("install", help="Install a knowledge pack")
    pack_install_parser.add_argument("source", type=str, help="Path to .tar.gz file or URL")
    pack_install_parser.set_defaults(func=cmd_pack_install)

    # pack list
    pack_list_parser = pack_subparsers.add_parser("list", help="List installed packs")
    pack_list_parser.add_argument(
        "--format", type=str, choices=["text", "json"], default="text", help="Output format"
    )
    pack_list_parser.set_defaults(func=cmd_pack_list)

    # pack info
    pack_info_parser = pack_subparsers.add_parser("info", help="Show detailed pack information")
    pack_info_parser.add_argument("name", type=str, help="Pack name")
    pack_info_parser.add_argument(
        "--show-eval-scores", action="store_true", help="Show evaluation scores"
    )
    pack_info_parser.set_defaults(func=cmd_pack_info)

    # pack eval
    pack_eval_parser = pack_subparsers.add_parser("eval", help="Evaluate pack quality")
    pack_eval_parser.add_argument("name", type=str, help="Pack name")
    pack_eval_parser.add_argument(
        "--questions", type=str, help="Path to custom questions JSONL file"
    )
    pack_eval_parser.add_argument(
        "--save-results", action="store_true", help="Save evaluation results"
    )
    pack_eval_parser.set_defaults(func=cmd_pack_eval)

    # pack update
    pack_update_parser = pack_subparsers.add_parser("update", help="Update a pack")
    pack_update_parser.add_argument("name", type=str, help="Pack name")
    pack_update_parser.add_argument(
        "--from", dest="from_archive", type=str, required=True, help="Path to new version archive"
    )
    pack_update_parser.set_defaults(func=cmd_pack_update)

    # pack remove
    pack_remove_parser = pack_subparsers.add_parser("remove", help="Remove a pack")
    pack_remove_parser.add_argument("name", type=str, help="Pack name")
    pack_remove_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    pack_remove_parser.set_defaults(func=cmd_pack_remove)

    # pack validate
    pack_validate_parser = pack_subparsers.add_parser("validate", help="Validate pack structure")
    pack_validate_parser.add_argument("pack_dir", type=str, help="Path to pack directory")
    pack_validate_parser.add_argument(
        "--strict", action="store_true", help="Enable strict validation"
    )
    pack_validate_parser.set_defaults(func=cmd_pack_validate)

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
