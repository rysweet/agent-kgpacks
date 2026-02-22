"""
Article service for WikiGR visualization.

Handles article details, categories, and statistics.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import kuzu

from backend.models.article import (
    ArticleDetail,
    CategoryInfo,
    CategoryListResponse,
    Section,
    StatsResponse,
)

logger = logging.getLogger(__name__)

# Stats cache: (result, timestamp). TTL = 60 seconds.
_stats_cache: tuple | None = None
_STATS_TTL = 60


class ArticleService:
    """Service for article operations."""

    @staticmethod
    def get_article_details(
        conn: kuzu.Connection,
        title: str,
    ) -> ArticleDetail:
        """
        Get detailed information about an article.

        Args:
            conn: Kuzu connection
            title: Article title

        Returns:
            ArticleDetail with full article information

        Raises:
            ValueError: If article not found
        """
        # Get article metadata
        result = conn.execute(
            """
            MATCH (a:Article {title: $title})
            RETURN a.category AS category, a.word_count AS word_count
            """,
            {"title": title},
        )

        df = result.get_as_df()
        if len(df) == 0:
            raise ValueError("Article not found")

        category = df.iloc[0]["category"]
        word_count = int(df.iloc[0]["word_count"])

        # Get sections
        sections_result = conn.execute(
            """
            MATCH (a:Article {title: $title})-[:HAS_SECTION]->(s:Section)
            RETURN s.title AS title, s.content AS content,
                   s.word_count AS word_count, s.level AS level
            ORDER BY s.section_id ASC
            """,
            {"title": title},
        )

        sections_df = sections_result.get_as_df()
        sections = []

        for _, row in sections_df.iterrows():
            section = Section(
                title=row["title"],
                content=row["content"] or "",
                word_count=int(row["word_count"]),
                level=int(row["level"]),
            )
            sections.append(section)

        # Get outgoing links
        links_result = conn.execute(
            """
            MATCH (a:Article {title: $title})-[:LINKS_TO]->(target:Article)
            RETURN target.title AS title
            ORDER BY title ASC
            LIMIT 500
            """,
            {"title": title},
        )

        links_df = links_result.get_as_df()
        links = links_df["title"].tolist() if len(links_df) > 0 else []

        # Get backlinks
        backlinks_result = conn.execute(
            """
            MATCH (source:Article)-[:LINKS_TO]->(a:Article {title: $title})
            RETURN source.title AS title
            ORDER BY title ASC
            LIMIT 500
            """,
            {"title": title},
        )

        backlinks_df = backlinks_result.get_as_df()
        backlinks = backlinks_df["title"].tolist() if len(backlinks_df) > 0 else []

        # Get categories (for now, just return the main category)
        categories = [category] if category else []

        # Generate Wikipedia URL (properly encoded)
        from urllib.parse import quote

        wikipedia_url = (
            f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='/:@')}"
        )

        # Use current timestamp as last_updated
        last_updated = datetime.now(timezone.utc)

        return ArticleDetail(
            title=title,
            category=category,
            word_count=word_count,
            sections=sections,
            links=links,
            backlinks=backlinks,
            categories=categories,
            wikipedia_url=wikipedia_url,
            last_updated=last_updated,
        )

    @staticmethod
    def get_categories(conn: kuzu.Connection) -> CategoryListResponse:
        """
        Get list of all categories with article counts.

        Args:
            conn: Kuzu connection

        Returns:
            CategoryListResponse with category information
        """
        # Get category counts
        result = conn.execute(
            """
            MATCH (a:Article)
            WHERE a.category IS NOT NULL
            RETURN a.category AS category, count(*) AS count
            ORDER BY count DESC, category ASC
            """
        )

        df = result.get_as_df()
        categories = []

        for _, row in df.iterrows():
            category = CategoryInfo(
                name=row["category"],
                article_count=int(row["count"]),
            )
            categories.append(category)

        return CategoryListResponse(
            categories=categories,
            total=len(categories),
        )

    @staticmethod
    def get_stats(conn: kuzu.Connection, db_path: str) -> StatsResponse:
        """
        Get database statistics and metrics.

        Results are cached for 60 seconds to avoid repeated full-table scans.

        Args:
            conn: Kuzu connection
            db_path: Path to database file

        Returns:
            StatsResponse with comprehensive statistics
        """
        global _stats_cache
        if _stats_cache is not None:
            cached_result, cached_at = _stats_cache
            if time.time() - cached_at < _STATS_TTL:
                return cached_result
        # Article statistics
        articles_result = conn.execute(
            """
            MATCH (a:Article)
            RETURN count(*) AS total
            """
        )
        total_articles = int(articles_result.get_as_df().iloc[0]["total"])

        # Articles by category
        category_result = conn.execute(
            """
            MATCH (a:Article)
            WHERE a.category IS NOT NULL
            RETURN a.category AS category, count(*) AS count
            ORDER BY count DESC
            """
        )
        category_df = category_result.get_as_df()
        by_category = {row["category"]: int(row["count"]) for _, row in category_df.iterrows()}

        # Articles by expansion depth (real query)
        depth_result = conn.execute(
            """
            MATCH (a:Article)
            WHERE a.expansion_depth IS NOT NULL
            RETURN a.expansion_depth AS depth, count(*) AS count
            ORDER BY depth ASC
            """
        )
        depth_df = depth_result.get_as_df()
        by_depth = {str(int(row["depth"])): int(row["count"]) for _, row in depth_df.iterrows()}

        articles = {
            "total": total_articles,
            "by_category": by_category,
            "by_depth": by_depth,
        }

        # Section statistics
        sections_result = conn.execute(
            """
            MATCH (s:Section)
            RETURN count(*) AS total
            """
        )
        total_sections = int(sections_result.get_as_df().iloc[0]["total"])
        avg_per_article = total_sections / total_articles if total_articles > 0 else 0

        sections = {
            "total": total_sections,
            "avg_per_article": round(avg_per_article, 1),
        }

        # Link statistics
        links_result = conn.execute(
            """
            MATCH ()-[r:LINKS_TO]->()
            RETURN count(r) AS total
            """
        )
        total_links = int(links_result.get_as_df().iloc[0]["total"])
        avg_links_per_article = total_links / total_articles if total_articles > 0 else 0

        links = {
            "total": total_links,
            "avg_per_article": round(avg_links_per_article, 1),
        }

        # Database information (capped traversal for safety)
        db_file = Path(db_path)
        db_size_mb = 0
        if db_file.exists():
            try:
                if db_file.is_dir():
                    # Cap file count to prevent unbounded traversal
                    total = 0
                    for i, f in enumerate(db_file.rglob("*")):
                        if i > 10000:
                            break
                        if f.is_file():
                            total += f.stat().st_size
                    db_size_mb = total / (1024 * 1024)
                else:
                    db_size_mb = db_file.stat().st_size / (1024 * 1024)
            except OSError:
                db_size_mb = 0

        database = {
            "size_mb": round(db_size_mb, 2),
            "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        result = StatsResponse(
            articles=articles,
            sections=sections,
            links=links,
            database=database,
        )

        # Cache the result
        _stats_cache = (result, time.time())

        return result
