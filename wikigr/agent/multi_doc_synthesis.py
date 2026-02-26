"""Multi-document synthesis with graph-based expansion.

This module provides MultiDocSynthesizer which expands search results by
traversing the knowledge graph (BFS) and synthesizes content with citations.

API Contract:
    MultiDocSynthesizer(kuzu_conn) -> instance
    expand_to_related_articles(
        seed_articles: list[int],
        max_hops: int = 1,
        max_articles: int = 50
    ) -> dict[int, dict]
    synthesize_with_citations(
        articles: dict[int, dict],
        query: str
    ) -> str

Design Philosophy:
    - BFS traversal for controlled graph expansion
    - Markdown citations for clear source attribution
    - Content truncation at 500 chars for context windows
    - Simple sequential numbering: [1], [2], [3]...
"""

import logging
from typing import Any

import kuzu

logger = logging.getLogger(__name__)


class MultiDocSynthesizer:
    """Expands and synthesizes content from multiple graph articles."""

    def __init__(self, kuzu_conn: kuzu.Connection):
        """Initialize synthesizer with Kuzu connection.

        Args:
            kuzu_conn: Active Kuzu connection for graph traversal
        """
        self.conn = kuzu_conn

    def expand_to_related_articles(
        self,
        seed_articles: list[int],
        max_hops: int = 1,
        max_articles: int = 50,
    ) -> dict[int, dict[str, Any]]:
        """Expand seed articles by traversing graph relationships.

        Uses BFS traversal to discover related articles up to max_hops away.
        Returns article metadata (id, title, content).

        Args:
            seed_articles: List of starting article IDs
            max_hops: Maximum graph distance to traverse (0 = seeds only)
            max_articles: Maximum total articles to return

        Raises:
            ValueError: If parameters are out of valid ranges

        Returns:
            Dictionary mapping article_id -> {title, content, ...}
            Includes seed articles and discovered neighbors

        Example:
            >>> expanded = synthesizer.expand_to_related_articles([1], max_hops=1)
            >>> assert 1 in expanded  # Seed article included
            >>> assert len(expanded) >= 1  # May include neighbors
        """
        # Security: Validate inputs to prevent DoS
        if not isinstance(seed_articles, list) or len(seed_articles) > 100:
            raise ValueError("seed_articles must be list with ≤100 items")
        if not isinstance(max_hops, int) or not (0 <= max_hops <= 3):
            raise ValueError("max_hops must be 0-3")
        if not isinstance(max_articles, int) or not (1 <= max_articles <= 100):
            raise ValueError("max_articles must be 1-100")

        if not seed_articles:
            return {}

        # BFS traversal to discover neighbors (single query for all hops)
        discovered = set(seed_articles)

        if max_hops > 0:
            # Variable-length path query to find neighbors up to max_hops away
            cypher = f"""
            UNWIND $seed_ids AS seed_id
            MATCH path = (start:Article {{id: seed_id}})-[:LINKS_TO*1..{max_hops}]->(neighbor:Article)
            WHERE neighbor.id NOT IN $seed_ids
            WITH DISTINCT neighbor.id AS article_id, length(path) AS hop
            RETURN article_id, hop
            ORDER BY hop, article_id
            LIMIT $limit
            """

            params = {
                "seed_ids": seed_articles,
                "limit": max_articles - len(seed_articles),
            }

            try:
                result = self.conn.execute(cypher, params)
                df = result.get_as_df()

                # Add discovered neighbors (respecting max_articles limit)
                for _, row in df.iterrows():
                    neighbor_id = int(row["article_id"])
                    hop_level = int(row["hop"])

                    # Respect max_hops constraint
                    if hop_level <= max_hops and len(discovered) < max_articles:
                        discovered.add(neighbor_id)

            except Exception as e:
                logger.error(f"BFS traversal failed: {e}")

        # Fetch content for all discovered articles (seeds + neighbors)
        # Respect max_articles limit
        discovered_list = list(discovered)[:max_articles]
        return self._fetch_article_content(discovered_list)

    def _fetch_article_content(self, article_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Fetch title and content for article IDs.

        Args:
            article_ids: List of article IDs to fetch

        Returns:
            Dictionary mapping article_id -> {title, content}
            Limited to the number of article_ids provided
        """
        if not article_ids:
            return {}

        cypher = """
        UNWIND $article_ids AS aid
        MATCH (a:Article {id: aid})
        RETURN a.id AS article_id, a.title AS title, a.content AS content
        """

        try:
            result = self.conn.execute(cypher, {"article_ids": article_ids})
            df = result.get_as_df()

            articles = {}
            # Only take up to len(article_ids) results
            max_results = len(article_ids)
            for _, row in df.iterrows():
                if len(articles) >= max_results:
                    break
                article_id = int(row["article_id"])
                articles[article_id] = {
                    "title": row["title"],
                    "content": row.get("content", ""),
                }

            return articles

        except Exception as e:
            logger.error(f"Failed to fetch article content: {e}")
            return {}

    def synthesize_with_citations(self, articles: dict[int, dict[str, Any]], _query: str) -> str:
        """Create markdown text with numbered citations.

        Formats articles with sequential citations [1], [2], [3]... and
        includes a References section with truncated content.

        Args:
            articles: Dictionary of article_id -> {title, content, ...}
            _query: Original query (for context, not used directly)

        Returns:
            Markdown formatted text with inline citations and references

        Example:
            >>> articles = {
            ...     1: {"title": "Physics", "content": "Physics is..."},
            ...     2: {"title": "Chemistry", "content": "Chemistry is..."},
            ... }
            >>> result = synthesizer.synthesize_with_citations(articles, "What is science?")
            >>> assert "[1]" in result
            >>> assert "References:" in result or "Sources:" in result
        """
        if not articles:
            return "No articles found to synthesize."

        # Build citation mapping (sequential numbering)
        article_list = sorted(articles.items())  # Deterministic ordering
        citation_map = {aid: idx + 1 for idx, (aid, _) in enumerate(article_list)}

        # Build synthesis text
        lines = []
        lines.append("# Synthesis\n")
        lines.append("Based on the knowledge graph, here are the relevant findings:\n")

        # Add article summaries with citations
        for article_id, article in article_list:
            citation_num = citation_map[article_id]
            title = article.get("title", f"Article {article_id}")
            content = article.get("content", "")

            # Truncate content to 500 chars
            truncated = content[:500]
            if len(content) > 500:
                truncated += "..."

            lines.append(f"**[{citation_num}] {title}**: {truncated}\n")

        # Add references section
        lines.append("\nReferences:\n")
        for article_id, article in article_list:
            citation_num = citation_map[article_id]
            title = article.get("title", f"Article {article_id}")
            content = article.get("content", "")

            # Truncate content for references
            truncated = content[:500]
            if len(content) > 500:
                truncated += "..."

            lines.append(f"[{citation_num}] **{title}** - {truncated}\n")

        return "\n".join(lines)
