#!/usr/bin/env python3.10
"""
Parallel LLM knowledge extraction for maximum throughput on 16-core machine.

Architecture:
  - Fetch pool (10 threads): Wikipedia API
  - LLM pool (20 threads): Concurrent Claude API calls for entity extraction
  - Writer (main thread): Serialize Kuzu DB writes

Expected: 30-40 articles/min (10x speedup), ~50 hours for 30K.
"""

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import kuzu  # noqa: E402

from bootstrap.src.embeddings.generator import EmbeddingGenerator  # noqa: E402
from bootstrap.src.expansion.link_discovery import LinkDiscovery  # noqa: E402
from bootstrap.src.expansion.work_queue import WorkQueueManager  # noqa: E402
from bootstrap.src.extraction.llm_extractor import LLMExtractor  # noqa: E402
from bootstrap.src.wikipedia.api_client import WikipediaAPIClient  # noqa: E402
from bootstrap.src.wikipedia.parser import parse_sections  # noqa: E402

DB_PATH = "data/wikigr_30k.db"
TARGET = 30000
FETCH_WORKERS = 10
LLM_WORKERS = 20  # Claude API supports high concurrency
BATCH_SIZE = 20  # Smaller batches to prevent OOM (20 articles × ~100KB = 2MB per batch)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)-12s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/expansion_30k_llm_parallel.log"),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class ArticleData:
    title: str
    article: object
    sections: list
    links: list
    embeddings: object
    extraction: object  # LLM extraction result
    category: str
    word_count: int


class ParallelLLMPipeline:
    def __init__(self, db_path: str):
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self.queue_mgr = WorkQueueManager(self.conn)
        self.discovery = LinkDiscovery(self.conn)
        self.embedder = (
            EmbeddingGenerator()
        )  # Shared (sentence-transformers is thread-safe for encode)

        self.loaded = 0
        self.failed = 0

    def fetch_and_extract(
        self, title: str, wiki_client: WikipediaAPIClient, llm: LLMExtractor
    ) -> ArticleData | None:
        """Fetch Wikipedia + run LLM extraction (runs in thread pool)."""
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
                    logger.warning(
                        "Cannot follow redirect '%s' -> '%s': %s", title, redirect_target, e
                    )
                    return None  # Skip

            # Parse
            sections = parse_sections(article.wikitext)
            if not sections:
                return None  # Stub

            # Generate embeddings (CPU-bound, but fast with TOKENIZERS_PARALLELISM=false)
            texts = [s.get("content", "") or s.get("title", "") for s in sections]
            embeddings = self.embedder.generate(texts, show_progress=False)

            # LLM extraction (I/O-bound, can parallelize heavily)
            extraction = llm.extract_from_article(title, sections, max_sections=3)

            category = (
                article.categories[0]
                if hasattr(article, "categories") and article.categories
                else "General"
            )
            word_count = sum(len((s.get("content", "") or "").split()) for s in sections)
            links = article.links if hasattr(article, "links") else []

            return ArticleData(
                title=title,
                article=article,
                sections=sections,
                links=links,
                embeddings=embeddings,
                extraction=extraction,
                category=category,
                word_count=word_count,
            )

        except Exception as e:
            logger.warning(f"Failed {title}: {e}")
            return None

    def write_to_db(self, data: ArticleData):
        """Write article + extraction to DB (serialized on main thread)."""
        title = data.title

        # Article node
        r = self.conn.execute("MATCH (a:Article {title: $t}) RETURN a", {"t": title})
        if not r.has_next():
            self.conn.execute(
                """CREATE (a:Article {
                    title: $t, category: $c, word_count: $w,
                    expansion_state: 'processed', expansion_depth: 0,
                    claimed_at: NULL, processed_at: current_timestamp(), retry_count: 0
                })""",
                {"t": title, "c": data.category, "w": data.word_count},
            )

        # Delete old sections
        self.conn.execute(
            "MATCH (a:Article {title: $t})-[r:HAS_SECTION]->(s:Section) DELETE r, s",
            {"t": title},
        )

        # Insert sections
        for i, (section, emb) in enumerate(zip(data.sections, data.embeddings)):
            sid = f"{title}#{i}"
            sec_wc = len((section.get("content", "") or "").split())
            self.conn.execute(
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
            self.conn.execute(
                """MATCH (a:Article {title: $t}), (s:Section {section_id: $sid})
                   CREATE (a)-[:HAS_SECTION {section_index: $i}]->(s)""",
                {"t": title, "sid": sid, "i": i},
            )

        # Entities
        for entity in data.extraction.entities:
            self.conn.execute(
                """MERGE (e:Entity {name: $name})
                   ON CREATE SET e.type = $type, e.properties = $props, e.source_article = $src""",
                {
                    "name": entity.name,
                    "type": entity.type,
                    "props": json.dumps(entity.properties),
                    "src": title,
                },
            )
            self.conn.execute(
                """MATCH (a:Article {title: $t}), (e:Entity {name: $name})
                   MERGE (a)-[:HAS_ENTITY]->(e)""",
                {"t": title, "name": entity.name},
            )

        # Relationships
        for rel in data.extraction.relationships:
            self.conn.execute(
                """MERGE (src:Entity {name: $s})
                   ON CREATE SET src.type = 'concept', src.source_article = $art""",
                {"s": rel.source, "art": title},
            )
            self.conn.execute(
                """MERGE (tgt:Entity {name: $t})
                   ON CREATE SET tgt.type = 'concept', tgt.source_article = $art""",
                {"t": rel.target, "art": title},
            )
            self.conn.execute(
                """MATCH (src:Entity {name: $s}), (tgt:Entity {name: $t})
                   CREATE (src)-[:ENTITY_RELATION {relation: $r, context: $c}]->(tgt)""",
                {"s": rel.source, "t": rel.target, "r": rel.relation, "c": rel.context},
            )

        # Facts
        for i, fact in enumerate(data.extraction.key_facts):
            fact_id = f"{title}#fact{i}"
            self.conn.execute(
                """CREATE (f:Fact {fact_id: $fid, content: $c, source_article: $src})""",
                {"fid": fact_id, "c": fact, "src": title},
            )
            self.conn.execute(
                """MATCH (a:Article {title: $t}), (f:Fact {fact_id: $fid})
                   CREATE (a)-[:HAS_FACT]->(f)""",
                {"t": title, "fid": fact_id},
            )

        # Discover links
        if data.links:
            self.discovery.discover_links(title, data.links, 0, max_depth=3)

    def run(self):
        start = time.time()
        iteration = 0

        # Create worker-specific clients
        wiki_clients = [WikipediaAPIClient(rate_limit_delay=0.1) for _ in range(FETCH_WORKERS)]
        llm_clients = [LLMExtractor() for _ in range(LLM_WORKERS)]

        while self.loaded < TARGET:
            iteration += 1

            batch = self.queue_mgr.claim_work(BATCH_SIZE)
            if not batch:
                stats = self.queue_mgr.get_queue_stats()
                logger.info(f"No batch claimed. Stats: {stats}")
                if stats.get("discovered", 0) == 0:
                    logger.info("No discovered articles remaining. Expansion complete.")
                    break
                # Try reclaiming stale
                reclaimed = self.queue_mgr.reclaim_stale(120)
                logger.info(f"Reclaimed {reclaimed} stale claims")
                time.sleep(5)
                continue

            titles = []
            for item in batch:
                if isinstance(item, str):
                    titles.append(item)
                elif isinstance(item, dict):
                    titles.append(item.get("title", str(item)))
                else:
                    titles.append(str(item))

            # Process batch in parallel
            results = []
            with ThreadPoolExecutor(max_workers=FETCH_WORKERS + LLM_WORKERS) as pool:
                future_to_title = {}
                for i, title in enumerate(titles):
                    wiki_client = wiki_clients[i % FETCH_WORKERS]
                    llm_client = llm_clients[i % LLM_WORKERS]
                    future = pool.submit(self.fetch_and_extract, title, wiki_client, llm_client)
                    future_to_title[future] = title

                for future in as_completed(future_to_title):
                    title = future_to_title[future]
                    try:
                        result = future.result(timeout=120)
                        if result:
                            results.append(result)
                        else:
                            self.queue_mgr.advance_state(title, "processed")  # Skip stub
                            self.loaded += 1
                    except Exception as e:
                        logger.error(f"Error {title}: {e}")
                        self.queue_mgr.mark_failed(title, str(e))
                        self.failed += 1

            # Write results to DB (serialized)
            for data in results:
                try:
                    self.write_to_db(data)
                    self.queue_mgr.advance_state(data.title, "processed")
                    self.loaded += 1
                except Exception as e:
                    logger.error(f"DB write failed {data.title}: {e}")
                    self.queue_mgr.mark_failed(data.title, str(e))
                    self.failed += 1

            # Clear results to free memory
            results.clear()

            if iteration % 5 == 0:
                elapsed = time.time() - start
                rate = self.loaded / (elapsed / 60) if elapsed > 0 else 0
                logger.info(
                    f"Progress: {self.loaded}/{TARGET}, {self.failed} failed, {rate:.1f}/min"
                )

        elapsed = time.time() - start
        logger.info(
            f"Complete: {self.loaded} in {elapsed / 3600:.1f}h ({self.loaded / (elapsed / 60):.1f}/min)"
        )


def main():
    os.makedirs("logs", exist_ok=True)
    pipeline = ParallelLLMPipeline(DB_PATH)
    pipeline.run()


if __name__ == "__main__":
    main()
