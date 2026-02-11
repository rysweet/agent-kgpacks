#!/usr/bin/env python3
"""
Run 30K article expansion from scratch.

Creates a fresh database, initializes seeds, and expands to 30,000 articles.
Expected runtime: 8-15 hours depending on Wikipedia API responsiveness.

Usage:
    nohup python scripts/run_30k_expansion.py > logs/expansion_30k.log 2>&1 &
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.src.expansion.orchestrator import RyuGraphOrchestrator

DB_PATH = "data/wikigr_30k.db"
SEEDS_PATH = "bootstrap/data/seeds_1k.json"
TARGET_ARTICLES = 30000
MAX_DEPTH = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/expansion_30k.log"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # Remove stale DB files and create fresh
    for f in [DB_PATH, DB_PATH + ".wal"]:
        if os.path.exists(f):
            os.remove(f)

    logger.info("Creating fresh database and schema...")
    import kuzu

    db = kuzu.Database(DB_PATH)
    conn = kuzu.Connection(db)

    # Create schema inline (avoiding create_schema function's DB lifecycle issues)
    conn.execute(
        "CREATE NODE TABLE Article(title STRING, category STRING, word_count INT32, expansion_state STRING, expansion_depth INT32, claimed_at TIMESTAMP, processed_at TIMESTAMP, retry_count INT32, PRIMARY KEY(title))"
    )
    conn.execute(
        "CREATE NODE TABLE Section(section_id STRING, title STRING, content STRING, word_count INT32, level INT32, embedding FLOAT[384], PRIMARY KEY(section_id))"
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
    logger.info("Schema created successfully")

    with open(SEEDS_PATH) as f:
        seed_data = json.load(f)

    seed_titles = [s["title"] for s in seed_data["seeds"]]
    logger.info(f"Loaded {len(seed_titles)} seeds from {SEEDS_PATH}")

    orch = RyuGraphOrchestrator(db_path=DB_PATH)
    orch.initialize_seeds(seed_titles)

    stats = orch.work_queue.get_queue_stats()
    logger.info(f"Initial queue stats: {stats}")

    start_time = time.time()
    logger.info(f"Starting expansion to {TARGET_ARTICLES} articles...")

    try:
        orch.expand_to_target(
            target_count=TARGET_ARTICLES,
        )
    except KeyboardInterrupt:
        logger.info("Expansion interrupted by user")
    except Exception as e:
        logger.error(f"Expansion failed: {e}", exc_info=True)
    finally:
        elapsed = time.time() - start_time
        stats = orch.work_queue.get_queue_stats()
        logger.info(f"Final stats after {elapsed / 60:.1f} minutes: {stats}")
        orch.close()


if __name__ == "__main__":
    main()
