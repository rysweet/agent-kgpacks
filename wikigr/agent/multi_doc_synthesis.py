"""
MultiDocSynthesizer - Expand seed articles and synthesize multi-document context.

Expands queries to related articles via entity overlap, LINKS_TO edges, and categories.
Synthesizes context from multiple articles with proper Markdown citations [1], [2], [3].
"""

import logging
from typing import Any

import kuzu

logger = logging.getLogger(__name__)


class MultiDocSynthesizer:
    """Synthesize context from multiple related articles with citations."""

    def __init__(self, conn: kuzu.Connection):
        """
        Initialize MultiDocSynthesizer with Kuzu connection.

        Args:
            conn: Kuzu database connection
        """
        self.conn = conn

    def expand_to_related_articles(
        self,
        seed_articles: list[str],
        max_related: int = 5,
    ) -> list[str]:
        """
        Expand seed articles to include related articles.

        Uses three signals for relatedness:
        1. Entity overlap (shared entities between articles)
        2. LINKS_TO edges (direct wiki links)
        3. Category similarity (same category)

        Args:
            seed_articles: Initial article titles to expand from
            max_related: Maximum number of related articles per seed

        Returns:
            List of article titles including seeds and related articles (deduplicated)
        """
        if not seed_articles:
            return []

        expanded = list(seed_articles)  # Start with seeds
        seen = set(seed_articles)

        try:
            # Query for related articles using all three signals
            query = """
            UNWIND $seeds AS seed_title
            MATCH (seed:Article {title: seed_title})

            // Signal 1: Entity overlap (shared entities)
            OPTIONAL MATCH (seed)-[:HAS_ENTITY]->(e:Entity)<-[:HAS_ENTITY]-(related1:Article)
            WITH seed, related1, count(e) AS entity_overlap

            // Signal 2: LINKS_TO edges (direct links)
            OPTIONAL MATCH (seed)-[:LINKS_TO]->(related2:Article)

            // Signal 3: Category similarity
            OPTIONAL MATCH (seed), (related3:Article)
            WHERE seed.category = related3.category AND seed.title <> related3.title

            // Combine all signals
            WITH seed,
                 collect(DISTINCT related1.title) AS entity_related,
                 collect(DISTINCT related2.title) AS link_related,
                 collect(DISTINCT related3.title) AS category_related

            UNWIND (entity_related + link_related + category_related) AS related_title

            // Score by number of signals that found this article
            WITH seed.title AS seed_title,
                 related_title,
                 (CASE WHEN related_title IN entity_related THEN 5 ELSE 0 END +
                  CASE WHEN related_title IN link_related THEN 1 ELSE 0 END +
                  CASE WHEN related_title IN category_related THEN 2 ELSE 0 END) AS overlap_score

            WHERE related_title IS NOT NULL
            RETURN DISTINCT related_title, overlap_score
            ORDER BY overlap_score DESC
            LIMIT $max_related
            """

            result = self.conn.execute(query, {"seeds": seed_articles, "max_related": max_related})
            df = result.get_as_df()

            if not df.empty:
                records = df.to_dict(orient="records")
                for record in records:
                    title = record.get("related_title")
                    if title and title not in seen:
                        expanded.append(title)
                        seen.add(title)

        except Exception as e:
            logger.warning(f"Related article expansion failed: {e}")
            # Fallback: return just the seeds

        return expanded

    def synthesize_context(
        self,
        article_titles: list[str],
        max_content_length: int = 1000,
    ) -> str:
        """
        Synthesize context from multiple articles with Markdown citations.

        Fetches lead section content from each article and formats it with
        citation markers [1], [2], [3] for proper attribution.

        Args:
            article_titles: List of article titles to synthesize
            max_content_length: Maximum length per article content (truncate longer)

        Returns:
            Markdown-formatted text with citations [1], [2], [3]
            Format:
                ## Article Title [1]
                Content excerpt...

                ## Another Article [2]
                Content excerpt...

                ## References
                [1] Article Title
                [2] Another Article
        """
        if not article_titles:
            return ""

        try:
            # Fetch lead sections for all articles
            query = """
            UNWIND $titles AS title
            MATCH (a:Article {title: title})-[:HAS_SECTION {section_index: 0}]->(s:Section)
            RETURN a.title AS title, s.content AS content
            """

            result = self.conn.execute(query, {"titles": article_titles})
            df = result.get_as_df()

            if df.empty:
                return ""

            # Build Markdown with citations
            sections: list[str] = []
            references: list[str] = []

            for idx, row in enumerate(df.iterrows(), start=1):
                _, data = row
                title = data.get("title", "")
                content = data.get("content", "")

                if not title:
                    continue

                # Truncate long content
                if len(content) > max_content_length:
                    content = content[:max_content_length] + "..."

                # Add section with citation
                sections.append(f"## {title} [{idx}]\n{content}")

                # Add reference entry
                references.append(f"[{idx}] {title}")

            # Combine sections and references
            markdown = "\n\n".join(sections)

            if references:
                markdown += "\n\n## References\n" + "\n".join(references)

            return markdown

        except Exception as e:
            logger.warning(f"Context synthesis failed: {e}")
            return ""
