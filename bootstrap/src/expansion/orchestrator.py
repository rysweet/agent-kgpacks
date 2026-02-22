"""
Expansion orchestrator for WikiGR

Coordinates the entire expansion process:
- Initialize seeds
- Claim work from queue
- Process articles
- Discover links
- Expand to target count

Supports parallel expansion with multiple worker threads, each using
its own Kuzu connection for thread safety.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import kuzu

from .link_discovery import LinkDiscovery
from .processor import ArticleProcessor
from .work_queue import WorkQueueManager

logger = logging.getLogger(__name__)


class RyuGraphOrchestrator:
    """Coordinates Wikipedia knowledge graph expansion"""

    def __init__(
        self,
        db_path: str,
        max_depth: int = 2,
        batch_size: int = 10,
        claim_timeout: int = 300,
        num_workers: int = 1,
    ):
        """
        Initialize expansion orchestrator

        Args:
            db_path: Path to Kuzu database
            max_depth: Maximum expansion depth from seeds
            batch_size: Articles to process per batch
            claim_timeout: Timeout for claim reclamation (seconds)
            num_workers: Number of parallel worker threads (1 = sequential)
        """
        self.db_path = db_path
        self.max_depth = max_depth
        self.batch_size = batch_size
        self.claim_timeout = claim_timeout
        self.num_workers = max(1, min(num_workers, 10))

        # Initialize database connection
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)

        # Initialize components (used for seeds, stats, and single-worker mode)
        self.work_queue = WorkQueueManager(self.conn)
        self.processor = ArticleProcessor(self.conn)
        self.link_discovery = LinkDiscovery(self.conn)

        # Shared embedding generator (loaded once, reused across workers)
        # Thread-safe for inference — sentence-transformers model.encode() is safe
        self._shared_embedding_generator = self.processor.embedding_generator

        logger.info(f"RyuGraphOrchestrator initialized: {db_path}")
        logger.info(f"  Max depth: {max_depth}")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Workers: {self.num_workers}")

    def close(self):
        """Release database resources."""
        self.work_queue = None  # type: ignore[assignment]
        self.processor = None  # type: ignore[assignment]
        self.link_discovery = None  # type: ignore[assignment]
        self.conn = None  # type: ignore[assignment]
        self.db = None  # type: ignore[assignment]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def initialize_seeds(self, seed_titles: list[str], category: str = "General") -> str:
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
            result = self.conn.execute(
                """
                MATCH (a:Article {title: $title})
                RETURN COUNT(a) AS count
            """,
                {"title": title},
            )

            if result.get_as_df().iloc[0]["count"] > 0:
                logger.warning(f"  Seed already exists: {title}, skipping")
                continue

            # Insert as discovered at depth 0
            self.conn.execute(
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

            logger.info(f"  Initialized seed: {title}")

        logger.info(f"Seeds initialized: {len(seed_titles)} articles")

        return session_id

    def _process_one(
        self,
        article_info: dict,
        worker_conn: kuzu.Connection,
    ) -> tuple[str, bool, str | None]:
        """Process a single article with a dedicated worker connection.

        Each call creates its own component instances bound to *worker_conn*
        so there is no shared mutable state between threads.

        Args:
            article_info: Dict with 'title', 'expansion_depth', and optionally 'category'.
            worker_conn: A Kuzu connection owned exclusively by this worker thread.

        Returns:
            (title, success, error_message)
        """
        title = article_info["title"]
        depth = article_info["expansion_depth"]

        worker_queue = WorkQueueManager(worker_conn)
        worker_processor = ArticleProcessor(
            worker_conn, embedding_generator=self._shared_embedding_generator
        )
        worker_link_disc = LinkDiscovery(worker_conn)

        logger.info(f"  Processing: {title} (depth={depth})")

        # Update heartbeat
        worker_queue.update_heartbeat(title)

        # Process article
        success, links, error = worker_processor.process_article(
            title=title,
            category=article_info.get("category", "General"),
            expansion_depth=depth,
        )

        if success:
            logger.info(f"    Loaded ({len(links)} links)")

            # Discover new links (if not at max depth)
            if depth < self.max_depth:
                discovered = worker_link_disc.discover_links(
                    source_title=title,
                    links=links,
                    current_depth=depth,
                    max_depth=self.max_depth,
                )

                if discovered > 0:
                    logger.info(f"    Discovered {discovered} new articles")
            else:
                logger.info("    Max depth reached, not discovering links")

            # Advance directly to processed (processor already sets loaded during insertion)
            worker_queue.advance_state(title, "processed")
        else:
            # Handle failure
            worker_queue.mark_failed(title, error or "Unknown error")
            logger.warning(f"    Failed: {error}")

        return (title, success, error)

    def expand_to_target(self, target_count: int, max_iterations: int | None = None) -> dict:
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
        stats = self.work_queue.get_queue_stats()

        # Create per-worker connections for parallel mode.
        # In single-worker mode we reuse self.conn (no extra connections).
        worker_conns: list[kuzu.Connection] = []
        if self.num_workers > 1:
            worker_conns = [kuzu.Connection(self.db) for _ in range(self.num_workers)]

        try:
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
                current_count = result.get_as_df().iloc[0]["count"]

                logger.info(f"\nIteration {iteration}: {current_count}/{target_count} loaded")

                if current_count >= target_count:
                    logger.info(f"Target reached: {current_count} articles")
                    break

                # Reclaim stale claims periodically
                if iteration % 5 == 0:
                    reclaimed = self.work_queue.reclaim_stale(self.claim_timeout)
                    if reclaimed > 0:
                        logger.info(f"  Reclaimed {reclaimed} stale claims")

                # Claim batch of work
                batch = self.work_queue.claim_work(self.batch_size)

                if not batch:
                    logger.warning("  No more work available in queue")

                    # Check if we have undiscovered links
                    fresh_stats = self.work_queue.get_queue_stats()
                    discovered_count = fresh_stats.get("discovered", 0)
                    if discovered_count == 0:
                        logger.warning("  No discovered articles remaining - expansion stalled")
                        break

                    # Wait briefly for reclaim or retry
                    time.sleep(2)
                    continue

                logger.info(f"  Claimed {len(batch)} articles")

                # Process batch: parallel or sequential
                if self.num_workers > 1 and len(batch) > 1:
                    self._process_batch_parallel(batch, worker_conns)
                else:
                    self._process_batch_sequential(batch)

                # Progress summary
                stats = self.work_queue.get_queue_stats()
                logger.info(f"  Queue: {stats}")

        finally:
            # Worker connections are released when they go out of scope;
            # clearing the list makes intent explicit.
            worker_conns.clear()

        # Final statistics
        duration = time.time() - start_time
        final_stats = self.work_queue.get_queue_stats()
        final_stats["iterations"] = iteration
        final_stats["duration_seconds"] = duration

        logger.info(f"\nExpansion complete in {duration:.1f}s ({iteration} iterations)")
        logger.info(f"Final stats: {final_stats}")

        return final_stats

    def _process_batch_sequential(self, batch: list[dict]) -> None:
        """Process a batch of articles sequentially using self.conn."""
        for article_info in batch:
            self._process_one(article_info, self.conn)

    def _process_batch_parallel(
        self, batch: list[dict], worker_conns: list[kuzu.Connection]
    ) -> None:
        """Process a batch of articles in parallel using ThreadPoolExecutor.

        Each article is submitted to the pool and processed with a dedicated
        Kuzu connection selected round-robin from *worker_conns*.
        """
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            # Process in chunks of num_workers to ensure each connection
            # is used by at most one thread at a time
            all_futures: dict = {}
            for chunk_start in range(0, len(batch), len(worker_conns)):
                chunk = batch[chunk_start : chunk_start + len(worker_conns)]
                # Wait for previous chunk to complete before starting next
                # (ensures connection reuse safety)
                for future in as_completed(all_futures):
                    title = all_futures[future]
                    try:
                        future.result()
                    except Exception:
                        logger.error(f"Worker exception for {title}", exc_info=True)
                all_futures.clear()

                for i, article_info in enumerate(chunk):
                    conn = worker_conns[i]
                    future = executor.submit(self._process_one, article_info, conn)
                    all_futures[future] = article_info["title"]

            # Process remaining futures from last chunk
            for future in as_completed(all_futures):
                title = all_futures[future]
                try:
                    future.result()
                except Exception:
                    logger.error(f"Worker exception for {title}", exc_info=True)

    def get_status(self) -> dict:
        """Get current expansion status"""
        return self.work_queue.get_queue_stats()
