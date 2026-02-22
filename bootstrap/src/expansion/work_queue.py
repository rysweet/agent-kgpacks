"""
Work Queue Manager for Article Expansion

Manages distributed article processing with claim/heartbeat/reclaim logic.
Implements the expansion state machine for coordinating work across workers.
"""

import logging
from datetime import datetime, timedelta, timezone

import kuzu

logger = logging.getLogger(__name__)


class WorkQueueManager:
    """
    Manages work queue for distributed article processing.

    Implements claim-based work distribution with heartbeat monitoring
    and automatic reclamation of stale claims.

    State transitions:
        discovered -> claimed -> processed (success path)
        discovered -> claimed -> failed (after max retries)
        claimed -> discovered (timeout reclaim or retry)
    """

    def __init__(self, conn: kuzu.Connection, max_retries: int = 3):
        """
        Initialize work queue manager.

        Args:
            conn: Kuzu database connection
            max_retries: Maximum retry attempts before marking as failed

        Example:
            >>> db = kuzu.Database("data/wikigr.db")
            >>> conn = kuzu.Connection(db)
            >>> manager = WorkQueueManager(conn)
        """
        self.conn = conn
        self.max_retries = max_retries
        logger.info("WorkQueueManager initialized")

    def claim_work(self, batch_size: int = 10) -> list[dict]:
        """
        Claim a batch of articles for processing.

        Finds unclaimed articles with state='discovered' and claims them
        by updating to state='claimed' with current timestamp.

        Args:
            batch_size: Number of articles to claim

        Returns:
            List of claimed articles: [{'title': str, 'expansion_depth': int,
                                       'claimed_at': datetime}]
            Empty list if no work available.

        Example:
            >>> articles = manager.claim_work(batch_size=5)
            >>> for article in articles:
            ...     print(f"Claimed: {article['title']} at depth {article['expansion_depth']}")
        """
        now = datetime.now(tz=timezone.utc)

        # Find and claim articles in discovered state
        # Order by depth ASC to process seeds (depth=0) first
        result = self.conn.execute(
            """
            MATCH (a:Article)
            WHERE a.expansion_state = 'discovered'
            RETURN a.title AS title, a.expansion_depth AS expansion_depth
            ORDER BY a.expansion_depth ASC
            LIMIT $batch_size
        """,
            {"batch_size": batch_size},
        )

        # Get articles as list
        articles = result.get_as_df().to_dict("records")

        if not articles:
            logger.debug("No work available to claim")
            return []

        # Claim each article atomically with MATCH+WHERE+SET+RETURN.
        # If another worker claimed the article between the SELECT above
        # and this UPDATE, the WHERE guard prevents the SET and the RETURN
        # yields an empty result -- no separate re-verify query needed.
        claimed = []
        for article in articles:
            title = article["title"]
            try:
                result = self.conn.execute(
                    """
                    MATCH (a:Article {title: $title})
                    WHERE a.expansion_state = 'discovered'
                    SET a.expansion_state = 'claimed',
                        a.claimed_at = $now
                    RETURN a.title AS title
                """,
                    {"title": title, "now": now},
                )

                if result.get_as_df().empty:
                    logger.debug(f"Claim lost race for article: {title}")
                    continue

                claimed.append(
                    {
                        "title": title,
                        "expansion_depth": article["expansion_depth"],
                        "claimed_at": now,
                    }
                )
                logger.debug(f"Claimed article: {title} (depth={article['expansion_depth']})")
            except Exception as e:
                logger.warning(f"Failed to claim article {title}: {e}", exc_info=True)

        logger.info(f"Claimed {len(claimed)} articles for processing")
        return claimed

    def update_heartbeat(self, article_title: str):
        """
        Update heartbeat timestamp for claimed article.

        Resets claimed_at to current time to prevent reclamation
        while article is being actively processed.

        Args:
            article_title: Article being processed

        Example:
            >>> manager.update_heartbeat("Python (programming language)")
        """
        now = datetime.now(tz=timezone.utc)

        try:
            self.conn.execute(
                """
                MATCH (a:Article {title: $title})
                WHERE a.expansion_state = 'claimed'
                SET a.claimed_at = $now
            """,
                {"title": article_title, "now": now},
            )

            logger.debug(f"Updated heartbeat for: {article_title}")
        except Exception as e:
            logger.warning(f"Failed to update heartbeat for {article_title}: {e}", exc_info=True)

    def reclaim_stale(self, timeout_seconds: int = 300) -> int:
        """
        Reclaim articles with stale claims (no heartbeat).

        Finds articles in 'claimed' state where claimed_at timestamp
        is older than timeout_seconds and resets them to 'discovered'.

        Args:
            timeout_seconds: Timeout for stale claims

        Returns:
            Number of articles reclaimed

        Example:
            >>> reclaimed = manager.reclaim_stale(timeout_seconds=300)
            >>> print(f"Reclaimed {reclaimed} stale articles")
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=timeout_seconds)

        try:
            # Find stale claims
            result = self.conn.execute(
                """
                MATCH (a:Article)
                WHERE a.expansion_state = 'claimed'
                  AND a.claimed_at < $cutoff
                RETURN a.title AS title
            """,
                {"cutoff": cutoff},
            )

            stale_articles = result.get_as_df().to_dict("records")

            if not stale_articles:
                logger.debug("No stale claims to reclaim")
                return 0

            # Reclaim each stale article
            reclaimed = 0
            for article in stale_articles:
                title = article["title"]
                try:
                    self.conn.execute(
                        """
                        MATCH (a:Article {title: $title})
                        WHERE a.expansion_state = 'claimed'
                        SET a.expansion_state = 'discovered',
                            a.claimed_at = NULL
                    """,
                        {"title": title},
                    )
                    reclaimed += 1
                    logger.debug(f"Reclaimed stale claim: {title}")
                except Exception as e:
                    logger.warning(f"Failed to reclaim {title}: {e}", exc_info=True)

            logger.info(f"Reclaimed {reclaimed} stale claims")
            return reclaimed

        except Exception as e:
            logger.error(f"Error reclaiming stale claims: {e}", exc_info=True)
            return 0

    VALID_STATES = {"discovered", "claimed", "loaded", "processed", "failed"}

    def advance_state(self, article_title: str, new_state: str):
        """
        Advance article to new state.

        Updates expansion_state and sets processed_at timestamp.
        Valid states: 'discovered', 'claimed', 'loaded', 'processed', 'failed'

        Args:
            article_title: Article title
            new_state: New state (discovered, claimed, loaded, processed, failed)

        Raises:
            ValueError: If new_state is not a valid state

        Example:
            >>> manager.advance_state("Python (programming language)", "loaded")
        """
        if new_state not in self.VALID_STATES:
            raise ValueError(f"Invalid state: {new_state}. Must be one of {self.VALID_STATES}")

        # Legal state transitions
        valid_predecessors = {
            "claimed": {"discovered"},
            "loaded": {"claimed"},
            "processed": {"loaded", "claimed"},
            "failed": {"claimed", "discovered"},
            "discovered": {"claimed", "failed"},  # retry/reclaim
        }
        predecessors = valid_predecessors.get(new_state, set())

        now = datetime.now(tz=timezone.utc)

        try:
            # Guard: only transition from legal predecessor states (parameterized)
            if predecessors:
                self.conn.execute(
                    """
                    MATCH (a:Article {title: $title})
                    WHERE a.expansion_state IN $predecessors
                    SET a.expansion_state = $new_state,
                        a.processed_at = $now
                """,
                    {
                        "title": article_title,
                        "new_state": new_state,
                        "now": now,
                        "predecessors": list(predecessors),
                    },
                )
            else:
                self.conn.execute(
                    """
                    MATCH (a:Article {title: $title})
                    SET a.expansion_state = $new_state,
                        a.processed_at = $now
                """,
                    {"title": article_title, "new_state": new_state, "now": now},
                )

            logger.info(f"Advanced {article_title} to state: {new_state}")
        except Exception as e:
            logger.error(f"Failed to advance state for {article_title}: {e}")
            raise

    def mark_failed(self, article_title: str, error: str):
        """
        Mark article as failed after max retries.

        Increments retry_count. If retry_count >= max_retries, sets state to 'failed'.
        Otherwise, resets to 'discovered' for retry.

        Args:
            article_title: Article title
            error: Error message (for logging only)

        Example:
            >>> manager.mark_failed("Invalid Article", "404 Not Found")
        """
        try:
            # Get current retry count and increment in one query
            result = self.conn.execute(
                """
                MATCH (a:Article {title: $title})
                RETURN a.retry_count AS retry_count
            """,
                {"title": article_title},
            )

            df = result.get_as_df()
            if df.empty:
                logger.warning(f"Article not found: {article_title}")
                return

            new_retry_count = int(df.iloc[0]["retry_count"]) + 1

            # Increment retry count and set state in a single query
            if new_retry_count >= self.max_retries:
                self.conn.execute(
                    """
                    MATCH (a:Article {title: $title})
                    SET a.retry_count = $new_retry_count,
                        a.expansion_state = 'failed',
                        a.processed_at = $now
                """,
                    {
                        "title": article_title,
                        "new_retry_count": new_retry_count,
                        "now": datetime.now(tz=timezone.utc),
                    },
                )
                logger.error(
                    f"Article failed after {new_retry_count} retries: {article_title} - {error}"
                )
            else:
                self.conn.execute(
                    """
                    MATCH (a:Article {title: $title})
                    SET a.retry_count = $new_retry_count,
                        a.expansion_state = 'discovered',
                        a.claimed_at = NULL
                """,
                    {"title": article_title, "new_retry_count": new_retry_count},
                )
                logger.warning(
                    f"Article retry {new_retry_count}/{self.max_retries}: {article_title} - {error}"
                )

        except Exception as e:
            logger.error(f"Failed to mark article as failed {article_title}: {e}")
            raise

    def get_queue_stats(self) -> dict:
        """
        Get work queue statistics.

        Returns:
            Dictionary with counts by state: {
                'discovered': int,
                'claimed': int,
                'loaded': int,
                'failed': int,
                'total': int
            }

        Example:
            >>> stats = manager.get_queue_stats()
            >>> print(f"Discovered: {stats['discovered']}, Loaded: {stats['loaded']}")
        """
        try:
            result = self.conn.execute("""
                MATCH (a:Article)
                WHERE a.expansion_state IS NOT NULL
                RETURN a.expansion_state AS state, COUNT(a) AS count
            """)

            df = result.get_as_df()

            stats = {
                "discovered": 0,
                "claimed": 0,
                "loaded": 0,
                "processed": 0,
                "failed": 0,
                "total": 0,
            }

            for _, row in df.iterrows():
                state = row["state"]
                count = row["count"]
                if state in stats:
                    stats[state] = count
                stats["total"] += count

            return stats

        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}", exc_info=True)
            raise  # Don't swallow - let caller handle
