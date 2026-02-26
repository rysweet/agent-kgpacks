"""Graph-based reranking for vector search results.

This module provides GraphReranker which combines vector similarity scores
with graph centrality metrics to improve retrieval quality in knowledge graphs.

API Contract:
    GraphReranker(kuzu_conn) -> instance
    calculate_centrality(article_ids: list[int]) -> dict[int, float]
    rerank(
        vector_results: list[dict],
        vector_weight: float = 0.6,
        graph_weight: float = 0.4
    ) -> list[dict]

Design Philosophy:
    - Simple weighted combination: vector_score * w1 + centrality * w2
    - Uses PageRank-style centrality from Kuzu
    - Preserves all metadata from input results
    - Handles missing graph nodes gracefully (zero centrality)
"""

import logging
from typing import Any

import kuzu

logger = logging.getLogger(__name__)


class GraphReranker:
    """Combines vector similarity with graph centrality for better ranking."""

    def __init__(self, kuzu_conn: kuzu.Connection):
        """Initialize reranker with Kuzu connection.

        Args:
            kuzu_conn: Active Kuzu connection for centrality queries
        """
        self.conn = kuzu_conn

    def calculate_centrality(self, article_ids: list[int]) -> dict[int, float]:
        """Calculate normalized centrality scores for articles.

        Uses degree centrality (in-degree + out-degree) normalized to [0, 1].
        Articles not in the graph receive centrality of 0.0.

        Args:
            article_ids: List of article IDs to calculate centrality for

        Returns:
            Dictionary mapping article_id -> centrality score in [0, 1]

        Example:
            >>> centrality = reranker.calculate_centrality([1, 2, 3])
            >>> assert all(0.0 <= score <= 1.0 for score in centrality.values())
        """
        if not article_ids:
            return {}

        # Build Cypher query for degree centrality with normalization
        # Count both incoming and outgoing LINKS_TO edges, then normalize
        cypher = """
        UNWIND $article_ids AS aid
        MATCH (a:Article {id: aid})
        OPTIONAL MATCH (a)-[r:LINKS_TO]->()
        WITH a, count(r) AS out_degree
        OPTIONAL MATCH (a)<-[r2:LINKS_TO]-()
        WITH a, out_degree, count(r2) AS in_degree, (out_degree + count(r2)) AS degree
        WITH collect({id: a.id, degree: degree}) AS articles, max(degree) AS max_degree
        UNWIND articles AS article
        RETURN article.id AS article_id,
               CASE WHEN max_degree > 0 THEN toFloat(article.degree) / toFloat(max_degree) ELSE 0.0 END AS centrality
        """

        try:
            result = self.conn.execute(cypher, {"article_ids": article_ids})
            df = result.get_as_df()

            if df.empty:
                # No articles found in graph
                return {aid: 0.0 for aid in article_ids}

            centrality = {}

            # Extract already-normalized centrality values from result
            for _, row in df.iterrows():
                article_id = int(row["article_id"])
                centrality_score = float(row["centrality"])
                centrality[article_id] = centrality_score

            # Fill in missing articles with 0.0
            for aid in article_ids:
                if aid not in centrality:
                    centrality[aid] = 0.0

            return centrality

        except Exception as e:
            logger.error(f"Centrality calculation failed: {e}")
            # Fallback: all articles get zero centrality
            return {aid: 0.0 for aid in article_ids}

    def rerank(
        self,
        vector_results: list[dict[str, Any]],
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
    ) -> list[dict[str, Any]]:
        """Rerank vector search results using graph centrality.

        Combines vector similarity scores with graph centrality metrics:
            final_score = (vector_score * vector_weight) + (centrality * graph_weight)

        Args:
            vector_results: List of dicts with at least {article_id, score, ...}
            vector_weight: Weight for vector similarity (default 0.6)
            graph_weight: Weight for graph centrality (default 0.4)

        Returns:
            Reranked results sorted by combined score (descending)
            All original fields preserved, score field updated

        Raises:
            ValueError: If weights are invalid (negative or don't sum to 1.0)

        Example:
            >>> results = [
            ...     {"article_id": 1, "score": 0.9, "title": "Article 1"},
            ...     {"article_id": 2, "score": 0.7, "title": "Article 2"},
            ... ]
            >>> reranked = reranker.rerank(results)
            >>> assert reranked[0]["score"] >= reranked[1]["score"]
        """
        # Validate weights
        if vector_weight < 0 or graph_weight < 0:
            raise ValueError("Weights must be non-negative")
        if abs(vector_weight + graph_weight - 1.0) > 0.001:
            raise ValueError(
                f"vector_weight and graph_weight must sum to 1.0, got {vector_weight + graph_weight}"
            )

        if not vector_results:
            return []

        # Extract article IDs
        article_ids = [r["article_id"] for r in vector_results]

        # Calculate centrality scores
        centrality = self.calculate_centrality(article_ids)

        # Compute combined scores
        reranked = []
        for result in vector_results:
            article_id = result["article_id"]
            vector_score = result["score"]
            centrality_score = centrality.get(article_id, 0.0)

            # Weighted combination
            combined_score = (vector_score * vector_weight) + (centrality_score * graph_weight)

            # Create new result with updated score
            new_result = result.copy()
            new_result["score"] = combined_score
            reranked.append(new_result)

        # Sort by combined score (descending)
        reranked.sort(key=lambda r: r["score"], reverse=True)

        return reranked
