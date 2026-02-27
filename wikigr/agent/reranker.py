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
        self._sparse_graph: bool | None = None  # Cached density check (None = not yet checked)

    def _check_graph_density(self) -> float:
        """Check average LINKS_TO edges per Article node.

        Returns:
            Average links per article (float). Returns 0.0 on error.
        """
        try:
            result = self.conn.execute("MATCH ()-[:LINKS_TO]->() RETURN count(*) AS total_links")
            links_df = result.get_as_df()
            total_links = int(links_df.iloc[0]["total_links"]) if not links_df.empty else 0

            result = self.conn.execute("MATCH (a:Article) RETURN count(a) AS total_articles")
            articles_df = result.get_as_df()
            total_articles = (
                int(articles_df.iloc[0]["total_articles"]) if not articles_df.empty else 0
            )

            if total_articles == 0:
                return 0.0
            return total_links / total_articles
        except Exception as e:
            logger.warning(f"Graph density check failed: {e}")
            return 0.0

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

        # Build Cypher query for raw degree centrality per article.
        # Normalization is done in Python to avoid Kuzu nested-aggregation errors
        # when collect() and max() both operate on aggregated values.
        cypher = """
        UNWIND $article_ids AS aid
        MATCH (a:Article) WHERE a.title = aid
        OPTIONAL MATCH (a)-[r:LINKS_TO]->()
        WITH a, count(r) AS out_degree
        OPTIONAL MATCH (a)<-[r2:LINKS_TO]-()
        WITH a, out_degree, count(r2) AS in_degree
        RETURN a.title AS article_id, out_degree + in_degree AS degree
        """

        try:
            result = self.conn.execute(cypher, {"article_ids": article_ids})
            df = result.get_as_df()

            if df.empty:
                # No articles found in graph
                return dict.fromkeys(article_ids, 0.0)

            # Normalize in Python to avoid Kuzu nested-aggregation errors
            max_degree = float(df["degree"].max()) if not df.empty else 0.0
            centrality = {}
            for _, row in df.iterrows():
                article_id = row["article_id"]
                raw_degree = float(row["degree"])
                centrality[article_id] = raw_degree / max_degree if max_degree > 0 else 0.0

            # Fill in missing articles with 0.0
            for aid in article_ids:
                if aid not in centrality:
                    centrality[aid] = 0.0

            return centrality

        except Exception as e:
            logger.error(f"Centrality calculation failed: {e}")
            # Fallback: all articles get zero centrality
            return dict.fromkeys(article_ids, 0.0)

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

        # Extract article identifiers (supports both article_id and title keys)
        id_key = "article_id" if "article_id" in vector_results[0] else "title"
        article_ids = [r[id_key] for r in vector_results]

        # Check graph density once per session; disable centrality for sparse graphs
        if self._sparse_graph is None:
            avg_links = self._check_graph_density()
            self._sparse_graph = avg_links < 2.0
            if self._sparse_graph:
                logger.warning(
                    f"Sparse graph detected (avg {avg_links:.1f} links/article), "
                    "disabling centrality component"
                )

        # Calculate centrality scores (skip for sparse graphs to avoid degradation)
        if self._sparse_graph:
            centrality = dict.fromkeys(article_ids, 0.0)
        else:
            centrality = self.calculate_centrality(article_ids)

        # Compute combined scores
        reranked = []
        for result in vector_results:
            article_id = result[id_key]
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
