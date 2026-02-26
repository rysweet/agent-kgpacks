#!/usr/bin/env python3
"""
Build DotNet Expert Knowledge Pack from URLs.

This script reads DotNet documentation URLs from urls.txt and builds a
complete knowledge graph with LLM-based extraction using the web content pipeline.

Expected runtime: 15-20 hours (300+ URLs with LLM extraction)
Estimated cost: ~$40-60 (Haiku at ~$0.25/1M input tokens)

Usage:
    python scripts/build_dotnet_pack.py [--test-mode]

Options:
    --test-mode     Build a small 10-URL pack for testing (5-10 minutes)

Note:
    This script follows the same pattern as build_physics_pack.py but uses WebContentSource
    instead of Wikipedia API for fetching documentation.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Disable tokenizers parallelism warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import kuzu  # noqa: E402

from bootstrap.schema.ryugraph_schema import create_schema  # noqa: E402
from bootstrap.src.embeddings.generator import EmbeddingGenerator  # noqa: E402
from bootstrap.src.extraction.llm_extractor import get_extractor  # noqa: E402
from bootstrap.src.sources.web import WebContentSource  # noqa: E402

PACK_DIR = Path("data/packs/dotnet-expert")
URLS_FILE = PACK_DIR / "urls.txt"
DB_PATH = PACK_DIR / "pack.db"
MANIFEST_PATH = PACK_DIR / "manifest.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/build_dotnet_pack.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_urls(urls_file: Path, limit: int | None = None) -> list[str]:
    """Load URLs from urls.txt file.

    Args:
        urls_file: Path to urls.txt
        limit: Optional limit on number of URLs (for testing)

    Returns:
        List of URLs
    """
    with open(urls_file) as f:
        urls = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#") and line.strip().startswith("http")
        ]

    if limit:
        urls = urls[:limit]
        logger.info(f"Limited to {limit} URLs for testing")

    logger.info(f"Loaded {len(urls)} URLs from {urls_file}")
    return urls


def process_url(
    url: str,
    conn: kuzu.Connection,
    web_source: WebContentSource,
    embedder: EmbeddingGenerator,
    extractor,
) -> bool:
    """Process a single URL with LLM extraction.

    Args:
        url: URL to process
        conn: Kuzu database connection
        web_source: Web content source
        embedder: Embedding generator
        extractor: LLM extractor

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create article title from URL
        title = url.split("/")[-1].replace(".html", "").replace("-", " ").title()
        if not title:
            title = url.split("/")[-2].replace("-", " ").title()

        # Check if article already exists
        result = conn.execute(
            "MATCH (a:Article {title: $title}) RETURN a.title AS title",
            {"title": title},
        )
        if not result.get_as_df().empty:
            logger.info(f"Skipping {title} (already exists)")
            return True

        # Fetch content from URL
        article = web_source.fetch_article(url)
        if not article or not article.content:
            logger.warning(f"No content for {url}")
            return False

        # Parse into sections
        # For web content, we'll treat the markdown as sections by splitting on headers
        sections = []
        current_section = {"title": "Introduction", "content": ""}

        for line in article.content.split("\n"):
            if line.startswith("#"):
                if current_section["content"].strip():
                    sections.append(current_section)
                title_text = line.lstrip("#").strip()
                current_section = {"title": title_text, "content": ""}
            else:
                current_section["content"] += line + "\n"

        if current_section["content"].strip():
            sections.append(current_section)

        if not sections:
            logger.warning(f"No sections for {url}")
            return False

        # Extract knowledge with LLM
        extraction = extractor.extract_from_article(
            title=title,
            sections=sections,
            max_sections=5,
            domain="programming",  # DotNet documentation is programming domain
        )

        # Create article node
        word_count = sum(len(s["content"].split()) for s in sections)
        conn.execute(
            "CREATE (a:Article {title: $title, category: $category, word_count: $wc})",
            {
                "title": title,
                "category": "DotNet Programming",
                "wc": word_count,
            },
        )

        # Add entities
        for entity in extraction.entities:
            entity_name = entity.name
            entity_type = entity.type

            # Create entity if not exists (use name as entity_id)
            conn.execute(
                "MERGE (e:Entity {entity_id: $entity_id}) "
                "ON CREATE SET e.name = $name, e.type = $type",
                {"entity_id": entity_name, "name": entity_name, "type": entity_type},
            )

            # Link article to entity
            conn.execute(
                "MATCH (a:Article {title: $title}), (e:Entity {entity_id: $entity_id}) "
                "MERGE (a)-[:HAS_ENTITY]->(e)",
                {"title": title, "entity_id": entity_name},
            )

        # Add relationships
        for rel in extraction.relationships:
            source = rel.source
            target = rel.target
            relation = rel.relation
            context = rel.context

            # Ensure both entities exist
            conn.execute(
                "MERGE (e:Entity {entity_id: $entity_id}) ON CREATE SET e.name = $name, e.type = 'concept'",
                {"entity_id": source, "name": source},
            )
            conn.execute(
                "MERGE (e:Entity {entity_id: $entity_id}) ON CREATE SET e.name = $name, e.type = 'concept'",
                {"entity_id": target, "name": target},
            )

            # Create relationship
            conn.execute(
                "MATCH (s:Entity {entity_id: $source}), (t:Entity {entity_id: $target}) "
                "MERGE (s)-[:ENTITY_RELATION {relation: $rel, context: $ctx}]->(t)",
                {"source": source, "target": target, "rel": relation, "ctx": context},
            )

        # Add facts
        for idx, fact in enumerate(extraction.key_facts):
            fact_id = f"{title}:fact:{idx}"
            conn.execute(
                "MATCH (a:Article {title: $title}) "
                "CREATE (a)-[:HAS_FACT]->(f:Fact {fact_id: $fact_id, content: $content})",
                {"title": title, "fact_id": fact_id, "content": fact},
            )

        # Add sections with embeddings
        for idx, section in enumerate(sections[:3]):  # Limit to first 3 sections
            section_id = f"{title}#{idx}"
            content = section["content"]

            # Generate embedding
            embedding = embedder.generate([content])[0].tolist()

            conn.execute(
                "MATCH (a:Article {title: $title}) "
                "CREATE (a)-[:HAS_SECTION {section_index: $idx}]->"
                "(s:Section {section_id: $sid, content: $content, embedding: $emb})",
                {
                    "title": title,
                    "idx": idx,
                    "sid": section_id,
                    "content": content,
                    "emb": embedding,
                },
            )

        logger.info(f"Processed {url} -> {title}")
        return True

    except Exception as e:
        logger.error(f"Failed to process {url}: {e}")
        return False


def create_manifest(
    db_path: Path,
    manifest_path: Path,
    articles_count: int,
    entities_count: int,
    relationships_count: int,
) -> None:
    """Create pack manifest file.

    Args:
        db_path: Path to pack database
        manifest_path: Path to save manifest
        articles_count: Number of articles in pack
        entities_count: Number of entities in pack
        relationships_count: Number of relationships in pack
    """
    size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0

    manifest = {
        "name": "dotnet-expert",
        "version": "1.0.0",
        "description": "Expert DotNet programming knowledge covering ownership, traits, async programming, unsafe code, and common patterns from official DotNet documentation",
        "graph_stats": {
            "articles": int(articles_count),
            "entities": int(entities_count),
            "relationships": int(relationships_count),
            "size_mb": round(size_mb, 2),
        },
        "eval_scores": {
            "accuracy": 0.0,
            "hallucination_rate": 0.0,
            "citation_quality": 0.0,
        },
        "source_urls": [
            "https://doc.rust-lang.org/book/",
            "https://doc.rust-lang.org/rust-by-example/",
            "https://doc.rust-lang.org/reference/",
            "https://doc.rust-lang.org/nomicon/",
            "https://doc.rust-lang.org/std/",
        ],
        "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "license": "MIT",
    }

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    logger.info(f"Manifest saved to {manifest_path}")


def build_pack(test_mode: bool = False) -> None:
    """Build the DotNet expert knowledge pack.

    Args:
        test_mode: If True, build a small 10-URL pack for testing
    """
    # Load URLs
    limit = 10 if test_mode else None
    urls = load_urls(URLS_FILE, limit=limit)

    if test_mode:
        logger.info("TEST MODE: Building 10-URL pack")

    # Initialize database - auto-delete in test mode
    if DB_PATH.exists():
        if test_mode:
            logger.info(f"Auto-deleting existing database (test mode): {DB_PATH}")
            import shutil

            shutil.rmtree(DB_PATH) if DB_PATH.is_dir() else DB_PATH.unlink()
        else:
            logger.warning(f"Database already exists: {DB_PATH}")
            response = input("Delete and rebuild? (y/N): ")
            if response.lower() != "y":
                logger.info("Aborted")
                return
            import shutil

            shutil.rmtree(DB_PATH) if DB_PATH.is_dir() else DB_PATH.unlink()

    logger.info(f"Creating database: {DB_PATH}")
    create_schema(str(DB_PATH), drop_existing=True)
    db = kuzu.Database(str(DB_PATH))
    conn = kuzu.Connection(db)

    # Initialize components
    web_source = WebContentSource()
    embedder = EmbeddingGenerator()
    extractor = get_extractor()

    # Process URLs
    successful = 0
    failed = 0

    for i, url in enumerate(urls, 1):
        logger.info(f"Processing {i}/{len(urls)}: {url}")
        if process_url(url, conn, web_source, embedder, extractor):
            successful += 1
        else:
            failed += 1

    # Get final stats
    result = conn.execute("MATCH (a:Article) RETURN count(a) AS count")
    articles_count = result.get_as_df().iloc[0]["count"]

    result = conn.execute("MATCH (e:Entity) RETURN count(e) AS count")
    entities_count = result.get_as_df().iloc[0]["count"]

    result = conn.execute("MATCH ()-[r:ENTITY_RELATION]->() RETURN count(r) AS count")
    relationships_count = result.get_as_df().iloc[0]["count"]

    logger.info(f"Build complete: {successful} successful, {failed} failed")
    logger.info(
        f"Final stats: {articles_count} articles, {entities_count} entities, {relationships_count} relationships"
    )

    # Create manifest
    create_manifest(DB_PATH, MANIFEST_PATH, articles_count, entities_count, relationships_count)

    logger.info("DotNet Expert Pack build complete!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build DotNet Expert Knowledge Pack")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Build a small 10-URL pack for testing",
    )
    args = parser.parse_args()

    # Create logs directory if needed
    Path("logs").mkdir(exist_ok=True)

    try:
        build_pack(test_mode=args.test_mode)
    except KeyboardInterrupt:
        logger.info("Build interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Build failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
