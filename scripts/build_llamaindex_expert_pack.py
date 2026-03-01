#!/usr/bin/env python3
"""
Build LlamaIndex Expert Knowledge Pack from URLs.

This script reads LlamaIndex framework documentation URLs from urls.txt
and builds a complete knowledge graph with LLM-based extraction using the
web content pipeline.

Expected runtime: 2-4 hours (30-45 URLs with LLM extraction)
Estimated cost: ~$5-10 (Haiku at ~$0.25/1M input tokens)

Usage:
    python scripts/build_llamaindex_expert_pack.py [--test-mode]

Options:
    --test-mode     Build a small 5-URL pack for testing (5-10 minutes)
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

PACK_DIR = Path("data/packs/llamaindex-expert")
URLS_FILE = PACK_DIR / "urls.txt"
DB_PATH = PACK_DIR / "pack.db"
MANIFEST_PATH = PACK_DIR / "manifest.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/build_llamaindex_expert_pack.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_urls(urls_file: Path, limit: int | None = None) -> list[str]:
    """Load URLs from urls.txt file, skipping comments and blank lines."""
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
    """Process a single URL: fetch, extract knowledge, store in graph."""
    try:
        article = web_source.fetch_article(url)
        if not article or not article.content:
            logger.warning(f"No content for {url}")
            return False

        title = article.title

        result = conn.execute(
            "MATCH (a:Article {title: $title}) RETURN a.title AS title",
            {"title": title},
        )
        if not result.get_as_df().empty:
            logger.info(f"Skipping {title!r} (already exists)")
            return True

        sections = web_source.parse_sections(article.content)
        if not sections:
            sections = [{"title": "Overview", "content": article.content, "level": 1}]

        extraction = extractor.extract_from_article(
            title=title,
            sections=sections,
            max_sections=5,
            domain="llamaindex",
        )

        word_count = sum(len(s["content"].split()) for s in sections)
        conn.execute(
            "CREATE (a:Article {title: $title, category: $category, word_count: $wc})",
            {
                "title": title,
                "category": "LlamaIndex",
                "wc": word_count,
            },
        )

        for entity in extraction.entities:
            conn.execute(
                "MERGE (e:Entity {entity_id: $entity_id}) "
                "ON CREATE SET e.name = $name, e.type = $type",
                {"entity_id": entity.name, "name": entity.name, "type": entity.type},
            )
            conn.execute(
                "MATCH (a:Article {title: $title}), (e:Entity {entity_id: $entity_id}) "
                "MERGE (a)-[:HAS_ENTITY]->(e)",
                {"title": title, "entity_id": entity.name},
            )

        for rel in extraction.relationships:
            for entity_id in (rel.source, rel.target):
                conn.execute(
                    "MERGE (e:Entity {entity_id: $entity_id}) "
                    "ON CREATE SET e.name = $entity_id, e.type = 'concept'",
                    {"entity_id": entity_id},
                )
            conn.execute(
                "MATCH (s:Entity {entity_id: $source}), (t:Entity {entity_id: $target}) "
                "MERGE (s)-[:ENTITY_RELATION {relation: $rel, context: $ctx}]->(t)",
                {
                    "source": rel.source,
                    "target": rel.target,
                    "rel": rel.relation,
                    "ctx": rel.context,
                },
            )

        for idx, fact in enumerate(extraction.key_facts):
            fact_id = f"{title}:fact:{idx}"
            conn.execute(
                "MATCH (a:Article {title: $title}) "
                "CREATE (a)-[:HAS_FACT]->(f:Fact {fact_id: $fact_id, content: $content})",
                {"title": title, "fact_id": fact_id, "content": fact},
            )

        for idx, section in enumerate(sections[:3]):
            section_id = f"{title}#{idx}"
            content = section["content"]
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

        logger.info(f"Processed {url!r} -> {title!r}")
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
    """Create pack manifest JSON file."""
    size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0

    manifest = {
        "name": "llamaindex-expert",
        "version": "1.0.0",
        "description": (
            "Expert knowledge of LlamaIndex framework covering RAG pipelines, indexing, embeddings, AgentWorkflow, and agentic document workflows."
        ),
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
            "https://developers.llamaindex.ai/python/framework/getting_started/",
            "https://github.com/run-llama/llama_index",
        ],
        "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "license": "MIT",
    }

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    logger.info(f"Manifest saved to {manifest_path}")


def build_pack(test_mode: bool = False) -> None:
    """Build the LlamaIndex Expert Knowledge Pack."""
    limit = 5 if test_mode else None
    urls = load_urls(URLS_FILE, limit=limit)

    if test_mode:
        logger.info("TEST MODE: Building 5-URL pack")

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

    web_source = WebContentSource()
    embedder = EmbeddingGenerator()
    extractor = get_extractor()

    successful = 0
    failed = 0

    for i, url in enumerate(urls, 1):
        logger.info(f"Processing {i}/{len(urls)}: {url}")
        if process_url(url, conn, web_source, embedder, extractor):
            successful += 1
        else:
            failed += 1

    articles_count = (
        conn.execute("MATCH (a:Article) RETURN count(a) AS count").get_as_df().iloc[0]["count"]
    )
    entities_count = (
        conn.execute("MATCH (e:Entity) RETURN count(e) AS count").get_as_df().iloc[0]["count"]
    )
    relationships_count = (
        conn.execute("MATCH ()-[r:ENTITY_RELATION]->() RETURN count(r) AS count")
        .get_as_df()
        .iloc[0]["count"]
    )

    logger.info(f"Build complete: {successful} successful, {failed} failed")
    logger.info(
        f"Final stats: {articles_count} articles, {entities_count} entities, "
        f"{relationships_count} relationships"
    )

    create_manifest(DB_PATH, MANIFEST_PATH, articles_count, entities_count, relationships_count)
    logger.info("LlamaIndex Expert Knowledge Pack build complete!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build LlamaIndex Expert Knowledge Pack")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Build a small 5-URL pack for testing",
    )
    args = parser.parse_args()

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
