"""
Expansion orchestrator for WikiGR

Coordinates the entire expansion process:
- Initialize seeds
- Claim work from queue
- Process articles
- Discover links
- Expand to target count
"""

import kuzu
from typing import List, Optional
import logging
from datetime import datetime
import time

from .work_queue import WorkQueueManager
from .processor import ArticleProcessor
from .link_discovery import LinkDiscovery


logger = logging.getLogger(__name__)


class RyuGraphOrchestrator:
    """Coordinates Wikipedia knowledge graph expansion"""

    def __init__(
        self,
        db_path: str,
        max_depth: int = 2,
        batch_size: int = 10,
        claim_timeout: int = 300
    ):
        """
        Initialize expansion orchestrator

        Args:
            db_path: Path to Kuzu database
            max_depth: Maximum expansion depth from seeds
            batch_size: Articles to process per batch
            claim_timeout: Timeout for claim reclamation (seconds)
        """
        self.db_path = db_path
        self.max_depth = max_depth
        self.batch_size = batch_size
        self.claim_timeout = claim_timeout

        # Initialize database connection
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)

        # Initialize components
        self.work_queue = WorkQueueManager(self.conn)
        self.processor = ArticleProcessor(self.conn)
        self.link_discovery = LinkDiscovery(self.conn)

        logger.info(f"RyuGraphOrchestrator initialized: {db_path}")
        logger.info(f"  Max depth: {max_depth}")
        logger.info(f"  Batch size: {batch_size}")

    def initialize_seeds(self, seed_titles: List[str], category: str = "General") -> str:
        """
        Initialize expansion with seed articles

        Args:
            seed_titles: List of seed article titles
            category: Category for seed articles

        Returns:
            session_id: Unique expansion session ID
        """
        import uuid

        session_id = str(uuid.uuid4())[:8]

        logger.info(f"Initializing {len(seed_titles)} seeds (session: {session_id})")

        for title in seed_titles:
            # Check if article already exists
            result = self.conn.execute("""
                MATCH (a:Article {title: $title})
                RETURN COUNT(a) AS count
            """, {"title": title})

            if result.get_as_df().iloc[0]['count'] > 0:
                logger.warning(f"  Seed already exists: {title}, skipping")
                continue

            # Insert as discovered at depth 0
            self.conn.execute("""
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
            """, {
                "title": title,
                "category": category
            })

            logger.info(f"  ✓ Initialized seed: {title}")

        logger.info(f"Seeds initialized: {len(seed_titles)} articles")

        return session_id

    def expand_to_target(
        self,
        target_count: int,
        max_iterations: Optional[int] = None
    ) -> dict:
        """
        Expand database to target number of loaded articles

        Args:
            target_count: Target number of loaded articles
            max_iterations: Max iterations (None = unlimited)

        Returns:
            Statistics: {
                'loaded': int,
                'failed': int,
                'discovered': int,
                'iterations': int,
                'duration_seconds': float
            }
        """
        logger.info(f"Starting expansion to {target_count} articles")

        start_time = time.time()
        iteration = 0

        while True:
            iteration += 1

            if max_iterations and iteration > max_iterations:
                logger.warning(f"Max iterations ({max_iterations}) reached")
                break

            # Check current progress (count articles with actual content)
            result = self.conn.execute("""
                MATCH (a:Article)
                WHERE a.word_count > 0
                RETURN COUNT(a) AS count
            """)
            current_count = result.get_as_df().iloc[0]['count']

            logger.info(f"\nIteration {iteration}: {current_count}/{target_count} loaded")

            if current_count >= target_count:
                logger.info(f"✓ Target reached: {current_count} articles")
                break

            # Reclaim stale claims periodically
            if iteration % 5 == 0:
                reclaimed = self.work_queue.reclaim_stale(self.claim_timeout)
                if reclaimed > 0:
                    logger.info(f"  Reclaimed {reclaimed} stale claims")

            # Claim batch of work
            batch = self.work_queue.claim_work(self.batch_size, self.claim_timeout)

            if not batch:
                logger.warning("  No more work available in queue")

                # Check if we have undiscovered links
                discovered_count = stats.get('discovered', 0)
                if discovered_count == 0:
                    logger.warning("  No discovered articles remaining - expansion stalled")
                    break

                # Wait briefly for reclaim or retry
                time.sleep(2)
                continue

            logger.info(f"  Claimed {len(batch)} articles")

            # Process batch
            for article_info in batch:
                title = article_info['title']
                depth = article_info['expansion_depth']

                logger.info(f"  Processing: {title} (depth={depth})")

                # Update heartbeat
                self.work_queue.update_heartbeat(title)

                # Process article
                success, links, error = self.processor.process_article(
                    title=title,
                    category=article_info.get('category', 'General'),
                    expansion_depth=depth
                )

                if success:
                    # Advance to loaded
                    self.work_queue.advance_state(title, 'loaded')
                    logger.info(f"    ✓ Loaded ({len(links)} links)")

                    # Discover new links (if not at max depth)
                    if depth < self.max_depth:
                        discovered = self.link_discovery.discover_links(
                            source_title=title,
                            links=links,
                            current_depth=depth,
                            max_depth=self.max_depth
                        )

                        if discovered > 0:
                            logger.info(f"    ✓ Discovered {discovered} new articles")

                        # Mark as processed
                        self.work_queue.advance_state(title, 'processed')
                    else:
                        logger.info(f"    Max depth reached, not discovering links")
                        self.work_queue.advance_state(title, 'processed')

                else:
                    # Handle failure
                    self.work_queue.mark_failed(title, error)
                    logger.warning(f"    ✗ Failed: {error}")

            # Progress summary
            stats = self.work_queue.get_queue_stats()
            logger.info(f"  Queue: {stats}")

        # Final statistics
        duration = time.time() - start_time
        final_stats = self.work_queue.get_queue_stats()
        final_stats['iterations'] = iteration
        final_stats['duration_seconds'] = duration

        logger.info(f"\nExpansion complete in {duration:.1f}s ({iteration} iterations)")
        logger.info(f"Final stats: {final_stats}")

        return final_stats

    def get_status(self) -> dict:
        """Get current expansion status"""
        return self.work_queue.get_queue_stats()


def main():
    """Test orchestrator"""
    import shutil
    from pathlib import Path

    print("=" * 70)
    print("Expansion Orchestrator Test")
    print("=" * 70)

    # Create fresh database
    db_path = "data/test_orchestrator.db"
    if Path(db_path).exists():
        if Path(db_path).is_dir():
            shutil.rmtree(db_path)
        else:
            Path(db_path).unlink()

    # Create schema
    from bootstrap.schema.ryugraph_schema import create_schema
    create_schema(db_path)

    # Initialize orchestrator
    orch = RyuGraphOrchestrator(
        db_path=db_path,
        max_depth=2,
        batch_size=5
    )

    # Test 1: Initialize seeds
    print("\n1. Initializing seeds...")
    seeds = [
        "Python (programming language)",
        "Artificial intelligence",
        "Machine learning"
    ]

    session_id = orch.initialize_seeds(seeds, category="Computer Science")
    print(f"   ✓ Initialized {len(seeds)} seeds (session: {session_id})")

    # Test 2: Expand to 10 articles
    print("\n2. Expanding to 10 articles...")
    stats = orch.expand_to_target(target_count=10, max_iterations=20)

    print(f"\n" + "=" * 70)
    print("EXPANSION RESULTS")
    print("=" * 70)
    print(f"Iterations: {stats['iterations']}")
    print(f"Duration: {stats['duration_seconds']:.1f}s")
    print(f"Loaded: {stats.get('loaded', 0) + stats.get('processed', 0)}")
    print(f"Failed: {stats.get('failed', 0)}")
    print(f"Discovered: {stats.get('discovered', 0)}")

    # Cleanup
    if Path(db_path).exists():
        if Path(db_path).is_dir():
            shutil.rmtree(db_path)
        else:
            Path(db_path).unlink()

    print("\n✓ Test complete!")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'bootstrap')

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    main()
