"""
Search service for WikiGR visualization.

Wraps existing semantic search functionality from bootstrap.
"""

import logging
import time

import kuzu

from backend.models.search import (
    AutocompleteResponse,
    AutocompleteResult,
    SearchResponse,
    SearchResult,
)

logger = logging.getLogger(__name__)


class SearchService:
    """Service for search operations."""

    @staticmethod
    def semantic_search(
        conn: kuzu.Connection,
        query: str,
        category: str | None = None,
        limit: int = 10,
        threshold: float = 0.0,
    ) -> SearchResponse:
        """
        Perform semantic search for similar articles.

        Args:
            conn: Kuzu connection
            query: Search query (article title)
            category: Optional category filter
            limit: Maximum results to return (1-100)
            threshold: Minimum similarity threshold (0.0-1.0)

        Returns:
            SearchResponse with results

        Raises:
            ValueError: If query article not found
        """
        start_time = time.time()

        # Validate query article exists
        result = conn.execute("MATCH (a:Article {title: $title}) RETURN a", {"title": query})
        if not result.has_next():
            raise ValueError(f"Article not found: {query}")

        # Use semantic search logic from bootstrap
        results = SearchService._semantic_search_impl(conn, query, category=category, top_k=limit)

        # Filter by threshold
        filtered_results = [r for r in results if r.similarity >= threshold]

        # Sort by similarity (descending)
        filtered_results.sort(key=lambda x: x.similarity, reverse=True)

        execution_time_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            query=query,
            results=filtered_results[:limit],
            total=len(filtered_results[:limit]),
            execution_time_ms=execution_time_ms,
        )

    @staticmethod
    def _semantic_search_impl(
        conn: kuzu.Connection,
        query_title: str,
        category: str | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """
        Internal semantic search implementation.

        Reuses logic from bootstrap.src.query.search.semantic_search
        but returns SearchResult models instead of dicts.
        """
        # Step 1: Get query article's section embeddings
        query_result = conn.execute(
            """
            MATCH (a:Article {title: $query_title})-[:HAS_SECTION]->(s:Section)
            RETURN s.embedding AS embedding, s.section_id AS section_id
            """,
            {"query_title": query_title},
        )

        query_df = query_result.get_as_df()

        if len(query_df) == 0:
            return []

        # Step 2: For each query embedding, find similar sections
        all_matches = []

        for _idx, row in query_df.iterrows():
            query_embedding = row["embedding"]

            # Query vector index
            result = conn.execute(
                """
                CALL QUERY_VECTOR_INDEX(
                    'Section',
                    'embedding_idx',
                    $query_embedding,
                    $top_k
                ) RETURN *
                """,
                {
                    "query_embedding": query_embedding,
                    "top_k": top_k * 5,  # Over-fetch for aggregation
                },
            )

            matches = result.get_as_df()

            for _, match_row in matches.iterrows():
                node = match_row["node"]
                distance = match_row["distance"]

                # Extract section info
                if isinstance(node, dict):
                    if "_properties" in node:
                        section_id = node["_properties"]["section_id"]
                    else:
                        section_id = node["section_id"]
                else:
                    section_id = node.section_id

                # Get article title from section_id
                article_title = section_id.split("#")[0]

                # Skip self-matches
                if article_title == query_title:
                    continue

                all_matches.append(
                    {
                        "article_title": article_title,
                        "distance": distance,
                        "similarity": 1.0 - distance,
                    }
                )

        # Step 3: Aggregate by article (best match per article)
        article_best_matches = {}

        for match in all_matches:
            article = match["article_title"]

            if article not in article_best_matches:
                article_best_matches[article] = match
            else:
                if match["distance"] < article_best_matches[article]["distance"]:
                    article_best_matches[article] = match

        # Step 4: Filter by category if specified
        results = []

        for article_title, match in article_best_matches.items():
            # Get article details
            article_result = conn.execute(
                """
                MATCH (a:Article {title: $title})
                RETURN a.category AS category, a.word_count AS word_count
                """,
                {"title": article_title},
            )

            article_df = article_result.get_as_df()
            if len(article_df) == 0:
                continue

            article_category = article_df.iloc[0]["category"]
            word_count = int(article_df.iloc[0]["word_count"])

            # Apply category filter
            if category and article_category != category:
                continue

            # Get summary (first section content)
            summary_result = conn.execute(
                """
                MATCH (a:Article {title: $title})-[:HAS_SECTION]->(s:Section)
                RETURN s.content AS content
                ORDER BY s.section_id ASC
                LIMIT 1
                """,
                {"title": article_title},
            )
            summary_df = summary_result.get_as_df()
            summary = ""
            if len(summary_df) > 0:
                content = summary_df.iloc[0]["content"]
                if content:
                    summary = content[:200] + "..." if len(content) > 200 else content

            result = SearchResult(
                article=article_title,
                similarity=match["similarity"],
                category=article_category,
                word_count=word_count,
                summary=summary,
            )
            results.append(result)

        # Step 5: Sort by similarity (descending)
        results.sort(key=lambda x: x.similarity, reverse=True)

        return results[:top_k]

    @staticmethod
    def autocomplete(
        conn: kuzu.Connection,
        q: str,
        limit: int = 10,
    ) -> AutocompleteResponse:
        """
        Get autocomplete suggestions for article titles.

        Args:
            conn: Kuzu connection
            q: Query string (minimum 2 characters)
            limit: Maximum suggestions to return (1-20)

        Returns:
            AutocompleteResponse with suggestions

        Raises:
            ValueError: If query is too short
        """
        if len(q) < 2:
            raise ValueError("Query must be at least 2 characters")

        # Search for articles with title starting with query
        query = """
            MATCH (a:Article)
            WHERE a.title STARTS WITH $prefix
            RETURN a.title AS title, a.category AS category
            ORDER BY a.title ASC
            LIMIT $limit
        """

        result = conn.execute(query, {"prefix": q, "limit": limit})
        df = result.get_as_df()

        suggestions = []
        for _, row in df.iterrows():
            suggestion = AutocompleteResult(
                title=row["title"],
                category=row["category"],
                match_type="prefix",
            )
            suggestions.append(suggestion)

        # If not enough results, search for contains
        if len(suggestions) < limit:
            remaining = limit - len(suggestions)
            contains_query = """
                MATCH (a:Article)
                WHERE a.title CONTAINS $substring AND NOT a.title STARTS WITH $prefix
                RETURN a.title AS title, a.category AS category
                ORDER BY a.title ASC
                LIMIT $limit
            """

            result = conn.execute(contains_query, {"substring": q, "prefix": q, "limit": remaining})
            df = result.get_as_df()

            for _, row in df.iterrows():
                suggestion = AutocompleteResult(
                    title=row["title"],
                    category=row["category"],
                    match_type="contains",
                )
                suggestions.append(suggestion)

        return AutocompleteResponse(
            query=q,
            suggestions=suggestions,
            total=len(suggestions),
        )
