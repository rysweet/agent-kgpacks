#!/usr/bin/env python3
"""
Build Physics Expert Knowledge Pack from topics.txt.

This script reads the 537 physics topics from topics.txt and builds a
complete knowledge graph with LLM-based extraction.

Expected runtime: 10-15 hours (537 articles with LLM extraction)
Estimated cost: ~$15-30 (Haiku at ~$0.25/1M input tokens)

Usage:
    python scripts/build_physics_pack.py [--test-mode]

Options:
    --test-mode     Build a small 10-article pack for testing (1-2 minutes)
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

from bootstrap.src.database.loader import DatabaseLoader  # noqa: E402
from bootstrap.src.embeddings.generator import EmbeddingGenerator  # noqa: E402
from bootstrap.src.extraction.llm_extractor import get_extractor  # noqa: E402
from bootstrap.src.wikipedia.api_client import WikipediaAPIClient  # noqa: E402
from bootstrap.src.wikipedia.parser import parse_sections  # noqa: E402

PACK_DIR = Path("data/packs/physics-expert")
TOPICS_FILE = PACK_DIR / "topics.txt"
DB_PATH = PACK_DIR / "pack.db"
MANIFEST_PATH = PACK_DIR / "manifest.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/build_physics_pack.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_topics(topics_file: Path, limit: int | None = None) -> list[str]:
    """Load topics from topics.txt file.

    Args:
        topics_file: Path to topics.txt
        limit: Optional limit on number of topics (for testing)

    Returns:
        List of topic titles
    """
    with open(topics_file) as f:
        topics = [line.strip() for line in f if line.strip()]

    if limit:
        topics = topics[:limit]
        logger.info(f"Limited to {limit} topics for testing")

    logger.info(f"Loaded {len(topics)} topics from {topics_file}")
    return topics


def process_article(
    title: str,
    conn: kuzu.Connection,
    wiki_client: WikipediaAPIClient,
    embedder: EmbeddingGenerator,
    extractor,
) -> bool:
    """Process a single article with LLM extraction.

    Args:
        title: Article title
        conn: Kuzu database connection
        wiki_client: Wikipedia API client
        embedder: Embedding generator
        extractor: LLM extractor

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if article already exists
        result = conn.execute(
            "MATCH (a:Article {title: $title}) RETURN a.title AS title",
            {"title": title},
        )
        if not result.get_as_df().empty:
            logger.info(f"Skipping {title} (already exists)")
            return True

        # Fetch article from Wikipedia
        article_data = wiki_client.get_article(title)
        if not article_data or not article_data.get("extract"):
            logger.warning(f"No content for {title}")
            return False

        # Parse sections
        sections = parse_sections(article_data.get("extract", ""), title)
        if not sections:
            logger.warning(f"No sections for {title}")
            return False

        # Extract knowledge with LLM
        lead_section = sections[0] if sections else None
        if not lead_section:
            logger.warning(f"No lead section for {title}")
            return False

        knowledge = extractor.extract_knowledge(lead_section["content"], title)

        # Create article node
        conn.execute(
            "CREATE (a:Article {title: $title, category: $category, word_count: $wc})",
            {
                "title": title,
                "category": "Physics",
                "wc": len(lead_section["content"].split()),
            },
        )

        # Add entities
        for entity in knowledge.get("entities", []):
            entity_name = entity["name"]
            entity_type = entity["type"]
            props_json = json.dumps(entity.get("properties", {}))

            # Create entity if not exists
            conn.execute(
                "MERGE (e:Entity {name: $name}) "
                "ON CREATE SET e.type = $type, e.properties = $props",
                {"name": entity_name, "type": entity_type, "props": props_json},
            )

            # Link article to entity
            conn.execute(
                "MATCH (a:Article {title: $title}), (e:Entity {name: $name}) "
                "MERGE (a)-[:HAS_ENTITY]->(e)",
                {"title": title, "name": entity_name},
            )

        # Add relationships
        for rel in knowledge.get("relationships", []):
            source = rel["source"]
            target = rel["target"]
            relation = rel["relation"]
            context = rel.get("context", "")

            # Ensure both entities exist
            conn.execute("MERGE (e:Entity {name: $name})", {"name": source})
            conn.execute("MERGE (e:Entity {name: $name})", {"name": target})

            # Create relationship
            conn.execute(
                "MATCH (s:Entity {name: $source}), (t:Entity {name: $target}) "
                "MERGE (s)-[:ENTITY_RELATION {relation: $rel, context: $ctx}]->(t)",
                {"source": source, "target": target, "rel": relation, "ctx": context},
            )

        # Add facts
        for fact in knowledge.get("facts", []):
            conn.execute(
                "MATCH (a:Article {title: $title}) "
                "CREATE (a)-[:HAS_FACT]->(f:Fact {content: $content, source_article: $title})",
                {"title": title, "content": fact},
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

        logger.info(f"Processed {title}")
        return True

    except Exception as e:
        logger.error(f"Failed to process {title}: {e}")
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
        "name": "physics-expert",
        "version": "1.0.0",
        "description": "Expert-level physics knowledge covering classical mechanics, quantum mechanics, relativity, thermodynamics, electromagnetism, and modern physics",
        "graph_stats": {
            "articles": articles_count,
            "entities": entities_count,
            "relationships": relationships_count,
            "size_mb": round(size_mb, 2),
        },
        "eval_scores": {
            "accuracy": 0.0,
            "hallucination_rate": 0.0,
            "citation_quality": 0.0,
        },
        "source_urls": ["https://en.wikipedia.org"],
        "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "license": "CC-BY-SA-4.0",
    }

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    logger.info(f"Manifest saved to {manifest_path}")


def build_pack(test_mode: bool = False) -> None:
    """Build the physics expert knowledge pack.

    Args:
        test_mode: If True, build a small 10-article pack for testing
    """
    # Load topics
    limit = 10 if test_mode else None
    topics = load_topics(TOPICS_FILE, limit=limit)

    if test_mode:
        logger.info("TEST MODE: Building 10-article pack")

    # Initialize database
    if DB_PATH.exists():
        logger.warning(f"Database already exists: {DB_PATH}")
        response = input("Delete and rebuild? (y/N): ")
        if response.lower() != "y":
            logger.info("Aborted")
            return
        DB_PATH.unlink()

    logger.info(f"Creating database: {DB_PATH}")
    db = kuzu.Database(str(DB_PATH))
    conn = kuzu.Connection(db)

    # Create schema
    loader = DatabaseLoader(db)
    loader.create_schema()

    # Initialize components
    wiki_client = WikipediaAPIClient()
    embedder = EmbeddingGenerator()
    extractor = get_extractor()

    # Process articles
    successful = 0
    failed = 0

    for i, topic in enumerate(topics, 1):
        logger.info(f"Processing {i}/{len(topics)}: {topic}")
        if process_article(topic, conn, wiki_client, embedder, extractor):
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

    logger.info("Physics Expert Pack build complete!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build Physics Expert Knowledge Pack")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Build a small 10-article pack for testing",
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
