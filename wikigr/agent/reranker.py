"""
GraphReranker - Rerank search results using graph centrality.

Combines vector similarity scores (60%) with graph centrality scores (40%)
using PageRank-style centrality calculations to improve result relevance.
"""

import logging
from typing import Any

import kuzu

logger = logging.getLogger(__name__)


class GraphReranker:
    """Rerank search results by combining vector and graph signals."""

    def __init__(
        self,
        conn: kuzu.Connection,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
    ):
        """
        Initialize GraphReranker with Kuzu connection and weights.

        Args:
            conn: Kuzu database connection
            vector_weight: Weight for vector similarity score (0-1)
            graph_weight: Weight for graph centrality score (0-1)

        Raises:
            ValueError: If weights don't sum to 1.0 or are out of range
        """
        if not (0.0 <= vector_weight <= 1.0 and 0.0 <= graph_weight <= 1.0):
            raise ValueError("Weights must be between 0 and 1")
        if not abs(vector_weight + graph_weight - 1.0) < 1e-9:
            raise ValueError(f"Weights must sum to 1.0, got {vector_weight + graph_weight}")

        self.conn = conn
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

    def calculate_centrality(self, article_titles: list[str]) -> dict[str, float]:
        """
        Calculate PageRank-style centrality for articles.

        Centrality is computed as a combination of inbound and outbound link counts,
        normalized to [0, 1] range. Higher centrality indicates more important/connected
        articles in the knowledge graph.

        Args:
            article_titles: List of article titles to compute centrality for

        Returns:
            Dictionary mapping article title to centrality score (0-1)
        """
        if not article_titles:
            return {}

        centrality_scores: dict[str, float] = {}

        try:
            # Query inbound and outbound link counts for each article
            query = """
            UNWIND $titles AS title
            MATCH (a:Article {title: title})
            OPTIONAL MATCH (a)<-[:LINKS_TO]-(inbound:Article)
            OPTIONAL MATCH (a)-[:LINKS_TO]->(outbound:Article)
            WITH a.title AS article_title,
                 count(DISTINCT inbound) AS inbound_count,
                 count(DISTINCT outbound) AS outbound_count
            RETURN article_title, inbound_count AS inbound, outbound_count AS outbound
            """

            result = self.conn.execute(query, {"titles": article_titles})
            df = result.get_as_df()

            if df.empty:
                logger.warning(f"No graph data found for articles: {article_titles}")
                return {title: 0.5 for title in article_titles}

            # Calculate centrality: weighted combination of inbound (80%) and outbound (20%)
            # Inbound links are stronger signal of importance (like PageRank)
            records = df.to_dict(orient="records")
            raw_scores: list[float] = []

            for record in records:
                inbound = record.get("inbound", 0) or 0
                outbound = record.get("outbound", 0) or 0
                # PageRank-style: inbound links matter more
                centrality = 0.8 * inbound + 0.2 * outbound
                raw_scores.append(centrality)

            # Normalize to [0, 1] range
            max_score = max(raw_scores) if raw_scores else 1.0
            if max_score == 0:
                max_score = 1.0

            for i, record in enumerate(records):
                title = record["article_title"]
                normalized_score = raw_scores[i] / max_score
                centrality_scores[title] = normalized_score

        except Exception as e:
            logger.warning(f"Centrality calculation failed: {e}")
            # Fallback: return default scores
            return {title: 0.5 for title in article_titles}

        # Fill in any missing titles with default score
        for title in article_titles:
            if title not in centrality_scores:
                centrality_scores[title] = 0.5

        return centrality_scores

    def rerank(
        self,
        search_results: list[dict[str, Any]],
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Rerank search results using combined vector + graph scoring.

        Args:
            search_results: List of search results with 'title' and 'score'/'similarity' fields
            max_results: Optional limit on number of results to return

        Returns:
            Reranked results with added 'reranked_score' field, sorted by combined score
        """
        if not search_results:
            return []

        # Extract article titles
        titles = [result.get("title", "") for result in search_results]
        titles = [t for t in titles if t]

        # Calculate graph centrality scores
        centrality_scores = self.calculate_centrality(titles)

        # Combine vector and graph scores
        reranked: list[dict[str, Any]] = []
        for result in search_results:
            title = result.get("title", "")
            if not title:
                continue

            # Get vector score (try both 'score' and 'similarity' fields)
            vector_score = result.get("score", result.get("similarity", 0.5))
            graph_score = centrality_scores.get(title, 0.5)

            # Combined score: vector_weight * vector + graph_weight * graph
            combined_score = self.vector_weight * vector_score + self.graph_weight * graph_score

            # Create reranked result with all original fields plus new score
            reranked_result = result.copy()
            reranked_result["reranked_score"] = combined_score
            reranked.append(reranked_result)

        # Sort by combined score (descending)
        reranked.sort(key=lambda x: x["reranked_score"], reverse=True)

        # Apply max_results limit if specified
        if max_results is not None:
            reranked = reranked[:max_results]

        return reranked
