"""
Link discovery for graph expansion.

Discovers new articles from links in existing articles, managing
expansion depth and creating LINKS_TO relationships.
"""

import logging

import kuzu

logger = logging.getLogger(__name__)


class LinkDiscovery:
    """Discovers new articles from links for graph expansion"""

    def __init__(self, conn: kuzu.Connection):
        """
        Initialize link discovery with Kuzu connection

        Args:
            conn: Active Kuzu database connection
        """
        self.conn = conn

    def discover_links(
        self, source_title: str, links: list[str], current_depth: int, max_depth: int = 2
    ) -> int:
        """
        Discover new articles from links

        Processes links from a source article, filtering valid article links
        and either creating new discovered articles or linking to existing ones.
        Respects maximum expansion depth.

        Args:
            source_title: Source article title
            links: List of linked article titles
            current_depth: Current expansion depth
            max_depth: Maximum expansion depth (default: 2)

        Returns:
            Number of new articles discovered

        Logic:
            1. If current_depth >= max_depth: return 0 (don't expand further)
            2. For each link:
               - Filter: Skip special pages, meta pages, lists, disambiguations
               - Check if article exists in DB
               - If exists: Create LINKS_TO relationship only
               - If new: INSERT as discovered (depth = current_depth + 1)
                         CREATE LINKS_TO relationship
            3. Return count of new articles

        Example:
            >>> discovery = LinkDiscovery(conn)
            >>> links = ["Python", "Machine Learning", "Wikipedia:About"]
            >>> new_count = discovery.discover_links("Programming", links, 0, max_depth=2)
            >>> assert new_count >= 0
        """
        if current_depth >= max_depth:
            logger.debug(
                f"Skipping link discovery for '{source_title}': "
                f"depth {current_depth} >= max_depth {max_depth}"
            )
            return 0

        next_depth = current_depth + 1
        new_articles_count = 0

        # Filter valid links
        valid_links = [link for link in links if self._is_valid_link(link)]

        logger.debug(
            f"Processing {len(valid_links)} valid links from '{source_title}' "
            f"(filtered from {len(links)} total)"
        )

        # Batch existence check to avoid N+1 queries
        existing_articles = self._batch_article_exists(valid_links)

        # Batch link check: pre-fetch all existing edges from source (1 query)
        existing_links = self._get_existing_links(source_title)

        for link in valid_links:
            try:
                state = existing_articles.get(link)

                if state is not None:
                    # Article exists - create LINKS_TO only if edge doesn't exist
                    if state in ["loaded", "claimed", "discovered", "processed"]:
                        if link not in existing_links:
                            self._create_link(source_title, link)
                        logger.debug(
                            f"Linked '{source_title}' -> '{link}' (existing, state={state})"
                        )
                else:
                    # New article - insert as discovered
                    try:
                        self._insert_discovered_article(link, next_depth)
                        new_articles_count += 1
                        logger.debug(f"Discovered new article '{link}' at depth {next_depth}")
                    except Exception as insert_err:
                        # PK violation if another article already discovered this link
                        logger.debug(f"Insert race for '{link}': {insert_err}")
                    # Always create the link edge for new articles
                    self._create_link(source_title, link)

            except Exception as e:
                logger.warning(f"Failed to process link '{link}': {e}", exc_info=True)
                continue

        logger.info(
            f"Link discovery complete for '{source_title}': "
            f"{new_articles_count} new articles at depth {next_depth}"
        )

        return new_articles_count

    def _is_valid_link(self, title: str) -> bool:
        """
        Check if link is valid for expansion

        Filters out special pages, meta pages, list pages, disambiguation pages,
        and file/image pages that should not be expanded.

        Filters out:
            - Special pages (Wikipedia:, Help:, Template:)
            - List pages (List of ...)
            - Disambiguation pages (... (disambiguation))
            - File/Image pages (File:, Image:)
            - Category pages (Category:)
            - Empty or very short titles

        Args:
            title: Article title to validate

        Returns:
            True if valid article link, False otherwise

        Example:
            >>> discovery = LinkDiscovery(conn)
            >>> discovery._is_valid_link("Python")
            True
            >>> discovery._is_valid_link("Wikipedia:About")
            False
            >>> discovery._is_valid_link("List of programming languages")
            False
            >>> discovery._is_valid_link("Python (disambiguation)")
            False
        """
        if not title or len(title) < 2:
            return False

        # Namespace prefixes to filter out (lowercased for case-insensitive comparison)
        invalid_prefixes = [
            "wikipedia:",
            "help:",
            "template:",
            "file:",
            "image:",
            "category:",
            "portal:",
            "talk:",
            "user:",
            "mediawiki:",
            "special:",
            "draft:",
            "module:",
            "book:",
            "timedtext:",
        ]

        # Check for invalid prefixes (case-insensitive)
        title_lower = title.lower()
        for prefix in invalid_prefixes:
            if title_lower.startswith(prefix):
                return False

        # Filter list pages
        if title.startswith("List of "):
            return False

        # Filter disambiguation pages
        return "(disambiguation)" not in title

    def article_exists(self, title: str) -> tuple[bool, str | None]:
        """
        Check if article exists in database

        Args:
            title: Article title to check

        Returns:
            (exists, state) where:
                - exists: True if article found
                - state: expansion_state if found, None otherwise

        Example:
            >>> discovery = LinkDiscovery(conn)
            >>> exists, state = discovery.article_exists("Python")
            >>> if exists:
            ...     print(f"Article exists with state: {state}")
        """
        result = self.conn.execute(
            """
            MATCH (a:Article {title: $title})
            RETURN a.expansion_state AS state
        """,
            {"title": title},
        )

        df = result.get_as_df()
        if len(df) > 0:
            return (True, df.iloc[0]["state"])
        else:
            return (False, None)

    def _batch_article_exists(self, titles: list[str]) -> dict[str, str]:
        """Check which articles exist in a single query.

        Returns:
            Dict mapping title -> expansion_state for articles that exist.
            Titles not in the dict do not exist.
        """
        if not titles:
            return {}

        result = self.conn.execute(
            """
            MATCH (a:Article)
            WHERE a.title IN $titles
            RETURN a.title AS title, a.expansion_state AS state
        """,
            {"titles": titles},
        )

        df = result.get_as_df()
        return dict(zip(df["title"], df["state"]))

    def _insert_discovered_article(self, title: str, depth: int):
        """
        Insert new article as discovered

        Args:
            title: Article title
            depth: Expansion depth
        """
        self.conn.execute(
            """
            CREATE (a:Article {
                title: $title,
                category: NULL,
                word_count: 0,
                expansion_state: 'discovered',
                expansion_depth: $depth,
                claimed_at: NULL,
                processed_at: NULL,
                retry_count: 0
            })
        """,
            {"title": title, "depth": depth},
        )

    def _get_existing_links(self, source_title: str) -> set[str]:
        """Get all existing LINKS_TO targets from a source article in one query."""
        result = self.conn.execute(
            """
            MATCH (source:Article {title: $source})-[:LINKS_TO]->(target:Article)
            RETURN target.title AS title
        """,
            {"source": source_title},
        )
        df = result.get_as_df()
        return set(df["title"].tolist()) if not df.empty else set()

    def _create_link(self, source_title: str, target_title: str):
        """
        Create LINKS_TO relationship between articles.

        Callers should pre-check with _get_existing_links for batch efficiency.
        """
        self.conn.execute(
            """
            MATCH (source:Article {title: $source}),
                  (target:Article {title: $target})
            CREATE (source)-[:LINKS_TO {link_type: 'internal'}]->(target)
        """,
            {"source": source_title, "target": target_title},
        )

    def get_discovered_count(self) -> int:
        """
        Get count of discovered but not yet loaded articles

        Returns:
            Number of articles in 'discovered' state

        Example:
            >>> discovery = LinkDiscovery(conn)
            >>> count = discovery.get_discovered_count()
            >>> print(f"Articles waiting to be processed: {count}")
        """
        result = self.conn.execute("""
            MATCH (a:Article)
            WHERE a.expansion_state = 'discovered'
            RETURN COUNT(a) AS count
        """)

        df = result.get_as_df()
        if len(df) > 0:
            return df.iloc[0]["count"]
        return 0


def main():
    """Test link discovery"""
    from pathlib import Path

    print("=" * 60)
    print("Link Discovery Test")
    print("=" * 60)

    # Create test database
    db_path = "data/test_link_discovery.db"
    print(f"\nDatabase: {db_path}")

    # Clean up if exists
    import shutil

    db_path_obj = Path(db_path)
    if db_path_obj.exists():
        if db_path_obj.is_dir():
            shutil.rmtree(db_path)
        else:
            db_path_obj.unlink()

    # Initialize database with schema
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # Create schema
    print("\nCreating schema...")
    conn.execute("""
        CREATE NODE TABLE Article(
            title STRING,
            category STRING,
            word_count INT32,
            expansion_state STRING,
            expansion_depth INT32,
            claimed_at TIMESTAMP,
            processed_at TIMESTAMP,
            retry_count INT32,
            PRIMARY KEY(title)
        )
    """)

    conn.execute("""
        CREATE REL TABLE LINKS_TO(
            FROM Article TO Article,
            link_type STRING
        )
    """)

    # Insert seed article
    print("\nInserting seed article...")
    conn.execute("""
        CREATE (a:Article {
            title: 'Python (programming language)',
            category: 'Computer Science',
            word_count: 5000,
            expansion_state: 'loaded',
            expansion_depth: 0,
            claimed_at: NULL,
            processed_at: timestamp('2026-02-08T00:00:00'),
            retry_count: 0
        })
    """)

    # Test link discovery
    print("\nTesting link discovery...")
    discovery = LinkDiscovery(conn)

    test_links = [
        # Valid links
        "Machine Learning",
        "Artificial Intelligence",
        "Data Science",
        # Invalid links (should be filtered)
        "Wikipedia:About",
        "Help:Contents",
        "List of programming languages",
        "Python (disambiguation)",
        "File:Python_logo.svg",
    ]

    print(f"\nProcessing {len(test_links)} links...")
    new_count = discovery.discover_links(
        source_title="Python (programming language)", links=test_links, current_depth=0, max_depth=2
    )

    print(f"\n✓ Discovered {new_count} new articles")

    # Verify results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    # Check discovered articles
    result = conn.execute("""
        MATCH (a:Article)
        RETURN a.title AS title, a.expansion_state AS state, a.expansion_depth AS depth
        ORDER BY a.expansion_depth, a.title
    """)

    print("\nArticles in database:")
    df = result.get_as_df()
    for _idx, row in df.iterrows():
        print(f"  [{row['state']:10s}] {row['title']} (depth={row['depth']})")

    # Check links
    result = conn.execute("""
        MATCH (source:Article)-[r:LINKS_TO]->(target:Article)
        RETURN source.title AS source, target.title AS target, r.link_type AS type
        ORDER BY source.title, target.title
    """)

    print("\nLinks created:")
    df = result.get_as_df()
    if len(df) == 0:
        print("  (none)")
    else:
        for _idx, row in df.iterrows():
            print(f"  {row['source']} -> {row['target']} [{row['type']}]")

    # Check discovered count
    discovered = discovery.get_discovered_count()
    print(f"\nDiscovered articles pending processing: {discovered}")

    # Test depth limiting
    print("\n" + "=" * 60)
    print("Testing depth limiting...")
    print("=" * 60)

    # Add an article at max depth
    conn.execute("""
        CREATE (a:Article {
            title: 'Deep Article',
            category: NULL,
            word_count: 0,
            expansion_state: 'loaded',
            expansion_depth: 2,
            claimed_at: NULL,
            processed_at: timestamp('2026-02-08T00:00:00'),
            retry_count: 0
        })
    """)

    # Try to discover links from it (should be blocked)
    new_count = discovery.discover_links(
        source_title="Deep Article", links=["Should Not Discover"], current_depth=2, max_depth=2
    )

    print(f"Attempted discovery at max depth: {new_count} articles (should be 0)")
    assert new_count == 0, "Should not discover articles at max depth"

    print("\n✓ All tests passed!")


if __name__ == "__main__":
    main()
