#!/usr/bin/env python3.10
"""
30K expansion with LLM-based knowledge extraction.

Uses Claude (Anthropic API) to extract entities, relationships, and facts
from each Wikipedia article, building a true knowledge graph.

Expected runtime: 15-20 hours (LLM API calls add latency but enable parallel processing)
Estimated cost: ~$50-100 (Haiku at ~$0.25/1M input tokens, ~8M tokens total)
"""

import json
import logging
import os
import sys
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import kuzu  # noqa: E402

from bootstrap.src.embeddings.generator import EmbeddingGenerator  # noqa: E402
from bootstrap.src.expansion.link_discovery import LinkDiscovery  # noqa: E402
from bootstrap.src.expansion.work_queue import WorkQueueManager  # noqa: E402
from bootstrap.src.extraction.llm_extractor import get_extractor  # noqa: E402
from bootstrap.src.wikipedia.api_client import WikipediaAPIClient  # noqa: E402
from bootstrap.src.wikipedia.parser import parse_sections  # noqa: E402

DB_PATH = "data/wikigr_30k.db"
SEEDS_PATH = "bootstrap/data/seeds_1k.json"
TARGET = 30000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/expansion_30k_llm.log"),
    ],
)
logger = logging.getLogger(__name__)


def process_article_with_llm(title: str, conn, wiki_client, embedder, extractor, discovery) -> bool:
    """Process single article with LLM extraction."""
    import re

    try:
        # Fetch
        article = wiki_client.fetch_article(title)

        # Handle redirects
        redirect_match = re.match(r"#REDIRECT\s*\[\[(.+?)\]\]", article.wikitext, re.IGNORECASE)
        if redirect_match:
            redirect_target = redirect_match.group(1).split("|")[0].strip()
            try:
                article = wiki_client.fetch_article(redirect_target)
            except Exception as e:
                logger.warning("Cannot follow redirect '%s' -> '%s': %s", title, redirect_target, e)
                return True  # Skip unfollowable redirects

        # Parse
        sections = parse_sections(article.wikitext)
        if not sections:
            return True  # Skip stubs

        # Generate embeddings
        texts = [s.get("content", "") or s.get("title", "") for s in sections]
        embeddings = embedder.generate(texts, show_progress=False)

        # Extract knowledge with LLM
        extraction = extractor.extract_from_article(title, sections, max_sections=3)

        # Insert Article
        category = (
            article.categories[0]
            if hasattr(article, "categories") and article.categories
            else "General"
        )
        word_count = sum(len((s.get("content", "") or "").split()) for s in sections)

        r = conn.execute("MATCH (a:Article {title: $t}) RETURN a", {"t": title})
        exists = r.has_next()

        if not exists:
            conn.execute(
                """CREATE (a:Article {
                    title: $t, category: $c, word_count: $w,
                    expansion_state: 'processed', expansion_depth: 0,
                    claimed_at: NULL, processed_at: current_timestamp(), retry_count: 0
                })""",
                {"t": title, "c": category, "w": word_count},
            )

        # Delete old sections
        conn.execute(
            "MATCH (a:Article {title: $t})-[r:HAS_SECTION]->(s:Section) DELETE r, s",
            {"t": title},
        )

        # Insert sections
        for i, (section, emb) in enumerate(zip(sections, embeddings)):
            sid = f"{title}#{i}"
            sec_wc = len((section.get("content", "") or "").split())
            conn.execute(
                """CREATE (s:Section {
                    section_id: $sid, title: $st, content: $c,
                    word_count: $w, level: $l, embedding: $e
                })""",
                {
                    "sid": sid,
                    "st": section.get("title", ""),
                    "c": section.get("content", ""),
                    "w": sec_wc,
                    "l": section.get("level", 2),
                    "e": emb.tolist(),
                },
            )
            conn.execute(
                """MATCH (a:Article {title: $t}), (s:Section {section_id: $sid})
                   CREATE (a)-[:HAS_SECTION {section_index: $i}]->(s)""",
                {"t": title, "sid": sid, "i": i},
            )

        # Insert entities
        for entity in extraction.entities:
            # Use MERGE to handle duplicates across articles
            conn.execute(
                """MERGE (e:Entity {name: $name})
                   ON CREATE SET e.type = $type, e.properties = $props,
                                 e.source_article = $src
                   ON MATCH SET e.properties = $props""",
                {
                    "name": entity.name,
                    "type": entity.type,
                    "props": json.dumps(entity.properties),
                    "src": title,
                },
            )
            conn.execute(
                """MATCH (a:Article {title: $t}), (e:Entity {name: $name})
                   MERGE (a)-[:HAS_ENTITY]->(e)""",
                {"t": title, "name": entity.name},
            )

        # Insert relationships
        for rel in extraction.relationships:
            # Ensure both entities exist first
            conn.execute(
                """MERGE (e:Entity {name: $name})
                   ON CREATE SET e.type = 'concept', e.source_article = $src""",
                {"name": rel.source, "src": title},
            )
            conn.execute(
                """MERGE (e:Entity {name: $name})
                   ON CREATE SET e.type = 'concept', e.source_article = $src""",
                {"name": rel.target, "src": title},
            )
            conn.execute(
                """MATCH (src:Entity {name: $s}), (tgt:Entity {name: $t})
                   CREATE (src)-[:ENTITY_RELATION {relation: $r, context: $c}]->(tgt)""",
                {"s": rel.source, "t": rel.target, "r": rel.relation, "c": rel.context},
            )

        # Insert facts
        for i, fact in enumerate(extraction.key_facts):
            fact_id = f"{title}#fact{i}"
            conn.execute(
                """CREATE (f:Fact {
                    fact_id: $fid, content: $c, source_article: $src
                })""",
                {"fid": fact_id, "c": fact, "src": title},
            )
            conn.execute(
                """MATCH (a:Article {title: $t}), (f:Fact {fact_id: $fid})
                   CREATE (a)-[:HAS_FACT]->(f)""",
                {"t": title, "fid": fact_id},
            )

        # Discover links
        links = article.links if hasattr(article, "links") else []
        if links:
            discovery.discover_links(title, links, 0, max_depth=3)

        logger.info(
            f"✓ {title}: {len(sections)}sec, {len(extraction.entities)}ent, {len(extraction.relationships)}rel"
        )
        return True

    except Exception as e:
        logger.error(f"✗ {title}: {e}")
        return False


def main():
    os.makedirs("logs", exist_ok=True)

    db = kuzu.Database(DB_PATH)
    conn = kuzu.Connection(db)
    queue = WorkQueueManager(conn)
    discovery = LinkDiscovery(conn)

    # Initialize components
    wiki_client = WikipediaAPIClient(rate_limit_delay=0.1)
    embedder = EmbeddingGenerator()
    extractor = get_extractor()

    # Load seeds
    with open(SEEDS_PATH) as f:
        seed_data = json.load(f)
    _seed_titles = [s["title"] for s in seed_data["seeds"]]  # noqa: F841

    # Check current state
    r = conn.execute("MATCH (a:Article) RETURN a.expansion_state AS state, COUNT(*) AS c")
    stats_df = r.get_as_df()
    logger.info(f"Current DB state:\n{stats_df.to_string()}")

    loaded = 0
    failed = 0
    iteration = 0

    logger.info(f"Starting LLM-enhanced expansion to {TARGET} articles...")

    while loaded < TARGET:
        iteration += 1

        batch = queue.claim_work(10)
        if not batch:
            stats = queue.get_queue_stats()
            if stats.get("discovered", 0) == 0:
                logger.info("No more articles. Complete.")
                break
            reclaimed = queue.reclaim_stale(120)
            if reclaimed > 0:
                logger.info(f"Reclaimed {reclaimed}")
            continue

        for item in batch:
            title = (
                item
                if isinstance(item, str)
                else (item.get("title") if isinstance(item, dict) else str(item))
            )

            if process_article_with_llm(title, conn, wiki_client, embedder, extractor, discovery):
                queue.advance_state(title, "processed")
                loaded += 1
            else:
                queue.mark_failed(title, "Processing error")
                failed += 1

        if iteration % 10 == 0:
            logger.info(f"Progress: {loaded}/{TARGET} ({failed} failed)")

    logger.info(f"Complete: {loaded} loaded, {failed} failed")


if __name__ == "__main__":
    main()
