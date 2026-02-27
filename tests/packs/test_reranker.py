"""Tests for graph-based reranking functionality.

This module tests the GraphReranker which combines vector similarity scores
with graph centrality metrics to improve retrieval quality.

TDD Approach: These tests are written BEFORE implementation and will fail initially.
"""

from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

from wikigr.agent.reranker import GraphReranker


@pytest.fixture
def mock_kuzu_conn():
    """Create a mock Kuzu connection for testing."""
    conn = MagicMock()
    return conn


@pytest.fixture
def reranker(mock_kuzu_conn):
    """Create a GraphReranker instance with mock connection."""
    return GraphReranker(mock_kuzu_conn)


class TestGraphRerankerCalculateCentrality:
    """Test GraphReranker.calculate_centrality() with various graph structures."""

    def test_calculate_centrality_single_node(self, reranker, mock_kuzu_conn):
        """Test centrality calculation for single isolated node."""
        # Mock Kuzu query result
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1],
                "degree": [0.0],  # Isolated node has zero centrality
            }
        )
        mock_kuzu_conn.execute.return_value = mock_result

        centrality = reranker.calculate_centrality([1])

        assert centrality == {1: 0.0}
        mock_kuzu_conn.execute.assert_called_once()

    def test_calculate_centrality_star_graph(self, reranker, mock_kuzu_conn):
        """Test centrality calculation for star topology (central hub node)."""
        # Central node should have highest centrality
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4],
                "degree": [1.0, 0.333, 0.333, 0.333],  # Node 1 is hub
            }
        )
        mock_kuzu_conn.execute.return_value = mock_result

        centrality = reranker.calculate_centrality([1, 2, 3, 4])

        assert centrality[1] > centrality[2]
        assert centrality[1] > centrality[3]
        assert centrality[2] == pytest.approx(centrality[3], rel=0.01)

    def test_calculate_centrality_chain_graph(self, reranker, mock_kuzu_conn):
        """Test centrality calculation for linear chain topology."""
        # Middle nodes should have higher centrality than endpoints
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4, 5],
                "degree": [0.2, 0.5, 0.8, 0.5, 0.2],  # Peak in middle
            }
        )
        mock_kuzu_conn.execute.return_value = mock_result

        centrality = reranker.calculate_centrality([1, 2, 3, 4, 5])

        assert centrality[3] > centrality[2]
        assert centrality[2] > centrality[1]
        assert centrality[1] == pytest.approx(centrality[5], rel=0.01)

    def test_calculate_centrality_empty_list(self, reranker, mock_kuzu_conn):
        """Test centrality calculation with empty article list."""
        centrality = reranker.calculate_centrality([])

        assert centrality == {}
        mock_kuzu_conn.execute.assert_not_called()

    def test_calculate_centrality_disconnected_components(self, reranker, mock_kuzu_conn):
        """Test centrality calculation for graph with multiple disconnected components."""
        # Two separate clusters
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4, 5, 6],
                "degree": [0.5, 0.5, 0.0, 0.7, 0.7, 0.0],  # Two components
            }
        )
        mock_kuzu_conn.execute.return_value = mock_result

        centrality = reranker.calculate_centrality([1, 2, 3, 4, 5, 6])

        # Centrality should vary by component connectivity
        assert len(centrality) == 6
        assert centrality[4] == pytest.approx(centrality[5], rel=0.01)

    def test_calculate_centrality_normalization(self, reranker, mock_kuzu_conn):
        """Test that centrality scores are normalized to [0, 1] range."""
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2, 3], "degree": [0.1, 0.5, 1.0]}
        )
        mock_kuzu_conn.execute.return_value = mock_result

        centrality = reranker.calculate_centrality([1, 2, 3])

        assert all(0.0 <= score <= 1.0 for score in centrality.values())
        assert max(centrality.values()) == pytest.approx(1.0, rel=0.01)


class TestGraphRerankerRerank:
    """Test GraphReranker.rerank() with different scoring combinations."""

    def test_rerank_default_weights(self, reranker, mock_kuzu_conn):
        """Test reranking with default weights (vector: 0.6, graph: 0.4)."""
        # Mock vector search results
        vector_results = [
            {"article_id": 1, "score": 0.9, "title": "Article 1"},
            {"article_id": 2, "score": 0.7, "title": "Article 2"},
            {"article_id": 3, "score": 0.5, "title": "Article 3"},
        ]

        # Dense graph density check (2.0+ avg links/article → centrality enabled)
        dense_links = Mock()
        dense_links.get_as_df.return_value = pd.DataFrame({"total_links": [20]})
        dense_articles = Mock()
        dense_articles.get_as_df.return_value = pd.DataFrame({"total_articles": [10]})
        # Mock centrality calculation
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2, 3], "degree": [0.3, 0.8, 0.6]}
        )
        mock_kuzu_conn.execute.side_effect = [dense_links, dense_articles, mock_result]

        reranked = reranker.rerank(vector_results)

        # Degrees [0.3, 0.8, 0.6] normalized by max(0.8) → centrality [0.375, 1.0, 0.75]
        # Expected scores: (vector * 0.6) + (centrality * 0.4)
        # Article 1: (0.9 * 0.6) + (0.375 * 0.4) = 0.54 + 0.15 = 0.69
        # Article 2: (0.7 * 0.6) + (1.0 * 0.4)   = 0.42 + 0.40 = 0.82
        # Article 3: (0.5 * 0.6) + (0.75 * 0.4)  = 0.30 + 0.30 = 0.60

        assert reranked[0]["article_id"] == 2  # Highest combined score
        assert reranked[0]["score"] == pytest.approx(0.82, rel=0.01)
        assert reranked[1]["article_id"] == 1
        assert reranked[2]["article_id"] == 3

    def test_rerank_custom_weights(self, reranker, mock_kuzu_conn):
        """Test reranking with custom weights."""
        vector_results = [
            {"article_id": 1, "score": 0.9, "title": "Article 1"},
            {"article_id": 2, "score": 0.7, "title": "Article 2"},
        ]

        dense_links = Mock()
        dense_links.get_as_df.return_value = pd.DataFrame({"total_links": [20]})
        dense_articles = Mock()
        dense_articles.get_as_df.return_value = pd.DataFrame({"total_articles": [10]})
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.3, 0.8]}
        )
        mock_kuzu_conn.execute.side_effect = [dense_links, dense_articles, mock_result]

        # Heavy graph weight: 0.2 vector, 0.8 graph
        reranked = reranker.rerank(vector_results, vector_weight=0.2, graph_weight=0.8)

        # Degrees [0.3, 0.8] normalized by max(0.8) → centrality [0.375, 1.0]
        # Article 1: (0.9 * 0.2) + (0.375 * 0.8) = 0.18 + 0.30 = 0.48
        # Article 2: (0.7 * 0.2) + (1.0 * 0.8)   = 0.14 + 0.80 = 0.94
        assert reranked[0]["article_id"] == 2
        assert reranked[0]["score"] == pytest.approx(0.94, rel=0.01)

    def test_rerank_vector_only(self, reranker, mock_kuzu_conn):
        """Test reranking with vector-only scoring (graph_weight=0)."""
        vector_results = [
            {"article_id": 1, "score": 0.9, "title": "Article 1"},
            {"article_id": 2, "score": 0.7, "title": "Article 2"},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.3, 0.8]}
        )
        mock_kuzu_conn.execute.return_value = mock_result

        reranked = reranker.rerank(vector_results, vector_weight=1.0, graph_weight=0.0)

        # Should maintain original vector order
        assert reranked[0]["article_id"] == 1
        assert reranked[0]["score"] == pytest.approx(0.9, rel=0.01)

    def test_rerank_graph_only(self, reranker, mock_kuzu_conn):
        """Test reranking with graph-only scoring (vector_weight=0)."""
        vector_results = [
            {"article_id": 1, "score": 0.9, "title": "Article 1"},
            {"article_id": 2, "score": 0.7, "title": "Article 2"},
        ]

        dense_links = Mock()
        dense_links.get_as_df.return_value = pd.DataFrame({"total_links": [20]})
        dense_articles = Mock()
        dense_articles.get_as_df.return_value = pd.DataFrame({"total_articles": [10]})
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.3, 0.8]}
        )
        mock_kuzu_conn.execute.side_effect = [dense_links, dense_articles, mock_result]

        reranked = reranker.rerank(vector_results, vector_weight=0.0, graph_weight=1.0)

        # Degrees [0.3, 0.8] normalized by max(0.8) → centrality [0.375, 1.0]
        # Article 1: (0.0 * 0.0) + (0.375 * 1.0) = 0.375
        # Article 2: (0.0 * 0.0) + (1.0 * 1.0)   = 1.0
        assert reranked[0]["article_id"] == 2
        assert reranked[0]["score"] == pytest.approx(1.0, rel=0.01)

    def test_rerank_empty_results(self, reranker, mock_kuzu_conn):
        """Test reranking with empty vector results."""
        reranked = reranker.rerank([])

        assert reranked == []
        mock_kuzu_conn.execute.assert_not_called()

    def test_rerank_missing_article_in_graph(self, reranker, mock_kuzu_conn):
        """Test reranking when some articles are not in graph (zero centrality)."""
        vector_results = [
            {"article_id": 1, "score": 0.9, "title": "Article 1"},
            {"article_id": 2, "score": 0.7, "title": "Article 2"},
            {"article_id": 3, "score": 0.5, "title": "Article 3"},
        ]

        # Only articles 1 and 2 in graph
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.6, 0.8]}
        )
        mock_kuzu_conn.execute.return_value = mock_result

        reranked = reranker.rerank(vector_results)

        # Article 3 should have zero centrality component
        # Article 3: (0.5 * 0.6) + (0.0 * 0.4) = 0.30
        assert len(reranked) == 3
        article_3 = next(r for r in reranked if r["article_id"] == 3)
        assert article_3["score"] == pytest.approx(0.30, rel=0.01)

    def test_rerank_all_zero_centrality(self, reranker, mock_kuzu_conn):
        """Test reranking when all articles have zero centrality."""
        vector_results = [
            {"article_id": 1, "score": 0.9, "title": "Article 1"},
            {"article_id": 2, "score": 0.7, "title": "Article 2"},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.0, 0.0]}
        )
        mock_kuzu_conn.execute.return_value = mock_result

        reranked = reranker.rerank(vector_results)

        # Should fall back to vector scores only
        assert reranked[0]["article_id"] == 1
        assert reranked[0]["score"] == pytest.approx(0.54, rel=0.01)  # 0.9 * 0.6

    def test_rerank_preserves_metadata(self, reranker, mock_kuzu_conn):
        """Test that reranking preserves all metadata fields."""
        vector_results = [
            {
                "article_id": 1,
                "score": 0.9,
                "title": "Article 1",
                "content": "Content 1",
                "url": "http://1",
            },
            {
                "article_id": 2,
                "score": 0.7,
                "title": "Article 2",
                "content": "Content 2",
                "url": "http://2",
            },
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.5, 0.5]}
        )
        mock_kuzu_conn.execute.return_value = mock_result

        reranked = reranker.rerank(vector_results)

        # All original fields should be preserved
        for result in reranked:
            assert "title" in result
            assert "content" in result
            assert "url" in result

    def test_rerank_weights_sum_to_one(self, reranker, mock_kuzu_conn):
        """Test that weights are validated to sum to 1.0."""
        vector_results = [{"article_id": 1, "score": 0.9, "title": "Article 1"}]

        with pytest.raises(ValueError, match="vector_weight and graph_weight must sum to 1.0"):
            reranker.rerank(vector_results, vector_weight=0.5, graph_weight=0.6)

    def test_rerank_negative_weights(self, reranker, mock_kuzu_conn):
        """Test that negative weights are rejected."""
        vector_results = [{"article_id": 1, "score": 0.9, "title": "Article 1"}]

        with pytest.raises(ValueError, match="Weights must be non-negative"):
            reranker.rerank(vector_results, vector_weight=-0.2, graph_weight=1.2)


class TestGraphRerankerIntegration:
    """Integration tests for complete reranking workflow."""

    def test_rerank_improves_quality_with_graph_context(self, reranker, mock_kuzu_conn):
        """Test that graph reranking improves result quality over vector-only."""
        # Scenario: Low vector score but high centrality article should rank higher
        vector_results = [
            {"article_id": 1, "score": 0.95, "title": "Tangential Article"},
            {"article_id": 2, "score": 0.60, "title": "Central Hub Article"},
            {"article_id": 3, "score": 0.85, "title": "Medium Article"},
        ]

        # Article 2 is central hub despite lower vector score
        dense_links = Mock()
        dense_links.get_as_df.return_value = pd.DataFrame({"total_links": [20]})
        dense_articles = Mock()
        dense_articles.get_as_df.return_value = pd.DataFrame({"total_articles": [10]})
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2, 3], "degree": [0.2, 0.95, 0.5]}
        )
        mock_kuzu_conn.execute.side_effect = [dense_links, dense_articles, mock_result]

        reranked = reranker.rerank(vector_results)

        # Article 1: (0.95 * 0.6) + (0.2 * 0.4) = 0.57 + 0.08 = 0.65
        # Article 2: (0.60 * 0.6) + (0.95 * 0.4) = 0.36 + 0.38 = 0.74
        # Article 3: (0.85 * 0.6) + (0.5 * 0.4) = 0.51 + 0.20 = 0.71

        assert reranked[0]["article_id"] == 2  # Central article promoted
        assert reranked[1]["article_id"] == 3
        assert reranked[2]["article_id"] == 1  # Tangential demoted

    def test_rerank_handles_ties_consistently(self, reranker, mock_kuzu_conn):
        """Test that reranking handles score ties consistently."""
        vector_results = [
            {"article_id": 1, "score": 0.8, "title": "Article 1"},
            {"article_id": 2, "score": 0.8, "title": "Article 2"},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.5, 0.5]}
        )
        mock_kuzu_conn.execute.return_value = mock_result

        reranked = reranker.rerank(vector_results)

        # Tied scores should maintain stable order
        assert len(reranked) == 2
        assert reranked[0]["score"] == pytest.approx(reranked[1]["score"], rel=0.01)


class TestSparseGraphDetection:
    """Tests for graph density check and sparse graph centrality suppression."""

    def test_sparse_graph_disables_centrality(self, reranker, mock_kuzu_conn):
        """When avg links/article < 2.0, centrality scores should be zeroed out."""
        # Sparse: 5 links / 10 articles = 0.5 avg
        links_result = Mock()
        links_result.get_as_df.return_value = pd.DataFrame({"total_links": [5]})
        articles_result = Mock()
        articles_result.get_as_df.return_value = pd.DataFrame({"total_articles": [10]})
        mock_kuzu_conn.execute.side_effect = [links_result, articles_result]

        vector_results = [
            {"article_id": 1, "score": 0.8, "title": "Article 1"},
            {"article_id": 2, "score": 0.6, "title": "Article 2"},
        ]

        reranked = reranker.rerank(vector_results)

        # Centrality is 0 (sparse), so score = vector_score * vector_weight (0.6)
        assert reranked[0]["article_id"] == 1
        assert reranked[0]["score"] == pytest.approx(0.48, rel=0.01)  # 0.8 * 0.6
        assert reranked[1]["score"] == pytest.approx(0.36, rel=0.01)  # 0.6 * 0.6

    def test_dense_graph_uses_centrality(self, reranker, mock_kuzu_conn):
        """When avg links/article >= 2.0, centrality should be applied normally."""
        # Dense: 50 links / 10 articles = 5.0 avg
        links_result = Mock()
        links_result.get_as_df.return_value = pd.DataFrame({"total_links": [50]})
        articles_result = Mock()
        articles_result.get_as_df.return_value = pd.DataFrame({"total_articles": [10]})
        # Centrality query result
        centrality_result = Mock()
        centrality_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [1, 2], "degree": [0.2, 0.9]}
        )
        mock_kuzu_conn.execute.side_effect = [links_result, articles_result, centrality_result]

        vector_results = [
            {"article_id": 1, "score": 0.8, "title": "Article 1"},
            {"article_id": 2, "score": 0.6, "title": "Article 2"},
        ]

        reranked = reranker.rerank(vector_results)

        # Degrees [0.2, 0.9] normalized by max(0.9) → centrality [0.222, 1.0]
        # Dense graph: centrality applied
        # Article 1: (0.8 * 0.6) + (0.222 * 0.4) = 0.48 + 0.089 = 0.569
        # Article 2: (0.6 * 0.6) + (1.0 * 0.4)   = 0.36 + 0.400 = 0.760
        assert reranked[0]["article_id"] == 2
        assert reranked[0]["score"] == pytest.approx(0.76, rel=0.01)

    def test_density_cached_per_session(self, reranker, mock_kuzu_conn):
        """Graph density only queried once per session (cached)."""
        links_result = Mock()
        links_result.get_as_df.return_value = pd.DataFrame({"total_links": [3]})
        articles_result = Mock()
        articles_result.get_as_df.return_value = pd.DataFrame({"total_articles": [10]})
        mock_kuzu_conn.execute.side_effect = [links_result, articles_result]
        vector_results = [{"article_id": 1, "score": 0.8, "title": "A"}]
        reranker.rerank(vector_results)  # triggers density check
        reranker.rerank(vector_results)  # uses cache
        assert mock_kuzu_conn.execute.call_count == 2

    def test_zero_articles_no_division_error(self, reranker, mock_kuzu_conn):
        """Zero articles returns 0.0 (no division by zero)."""
        links_result = Mock()
        links_result.get_as_df.return_value = pd.DataFrame({"total_links": [0]})
        articles_result = Mock()
        articles_result.get_as_df.return_value = pd.DataFrame({"total_articles": [0]})
        mock_kuzu_conn.execute.side_effect = [links_result, articles_result]
        assert reranker._check_graph_density() == 0.0

    def test_density_exception_returns_zero(self, reranker, mock_kuzu_conn):
        """DB error during density check returns 0.0."""
        mock_kuzu_conn.execute.side_effect = Exception("DB error")
        assert reranker._check_graph_density() == 0.0
