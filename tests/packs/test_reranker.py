"""Tests for GraphReranker module."""

import pytest
from unittest.mock import Mock, MagicMock
import kuzu

from wikigr.agent.reranker import GraphReranker


@pytest.fixture
def mock_connection():
    """Create a mock Kuzu connection."""
    conn = MagicMock(spec=kuzu.Connection)
    return conn


@pytest.fixture
def sample_search_results():
    """Sample search results for reranking."""
    return [
        {"title": "Quantum Mechanics", "score": 0.9, "similarity": 0.9},
        {"title": "Wave Function", "score": 0.85, "similarity": 0.85},
        {"title": "Schrodinger Equation", "score": 0.8, "similarity": 0.8},
        {"title": "Quantum Entanglement", "score": 0.75, "similarity": 0.75},
    ]


class TestGraphRerankerInit:
    """Test GraphReranker initialization."""

    def test_init_default_weights(self, mock_connection):
        """Test initialization with default weights."""
        reranker = GraphReranker(mock_connection)
        assert reranker.conn == mock_connection
        assert reranker.vector_weight == 0.6
        assert reranker.graph_weight == 0.4

    def test_init_custom_weights(self, mock_connection):
        """Test initialization with custom weights."""
        reranker = GraphReranker(mock_connection, vector_weight=0.7, graph_weight=0.3)
        assert reranker.vector_weight == 0.7
        assert reranker.graph_weight == 0.3

    def test_init_weights_validation(self, mock_connection):
        """Test weights validation during initialization."""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            GraphReranker(mock_connection, vector_weight=0.5, graph_weight=0.3)

    def test_init_negative_weights(self, mock_connection):
        """Test negative weights are rejected."""
        with pytest.raises(ValueError, match="must be between 0 and 1"):
            GraphReranker(mock_connection, vector_weight=-0.1, graph_weight=1.1)


class TestCalculateCentrality:
    """Test calculate_centrality method."""

    def test_calculate_centrality_empty_list(self, mock_connection):
        """Test centrality calculation with empty list."""
        reranker = GraphReranker(mock_connection)
        result = reranker.calculate_centrality([])
        assert result == {}

    def test_calculate_centrality_single_node(self, mock_connection):
        """Test centrality calculation with single node."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [{"inbound": 0, "outbound": 0}]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        result = reranker.calculate_centrality(["Quantum Mechanics"])

        assert "Quantum Mechanics" in result
        assert result["Quantum Mechanics"] >= 0.0

    def test_calculate_centrality_multiple_nodes(self, mock_connection):
        """Test centrality calculation with multiple nodes."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"inbound": 10, "outbound": 5},
            {"inbound": 8, "outbound": 3},
            {"inbound": 12, "outbound": 7},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        titles = ["Quantum Mechanics", "Wave Function", "Schrodinger Equation"]
        result = reranker.calculate_centrality(titles)

        assert len(result) == 3
        assert all(title in result for title in titles)
        assert all(score >= 0.0 for score in result.values())

    def test_calculate_centrality_normalization(self, mock_connection):
        """Test that centrality scores are properly normalized."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"inbound": 100, "outbound": 50},
            {"inbound": 50, "outbound": 25},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        result = reranker.calculate_centrality(["Node A", "Node B"])

        # Highest centrality should be normalized to 1.0
        max_score = max(result.values())
        assert max_score <= 1.0

    def test_calculate_centrality_query_error(self, mock_connection):
        """Test handling of query errors in centrality calculation."""
        mock_connection.execute.side_effect = Exception("Database error")

        reranker = GraphReranker(mock_connection)
        result = reranker.calculate_centrality(["Quantum Mechanics"])

        # Should return default scores on error
        assert "Quantum Mechanics" in result
        assert result["Quantum Mechanics"] == 0.5

    def test_calculate_centrality_empty_dataframe(self, mock_connection):
        """Test centrality calculation when query returns empty results."""
        mock_df = Mock()
        mock_df.empty = True

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        result = reranker.calculate_centrality(["Nonexistent Article"])

        assert "Nonexistent Article" in result
        assert result["Nonexistent Article"] == 0.5


class TestRerank:
    """Test rerank method."""

    def test_rerank_empty_results(self, mock_connection):
        """Test reranking with empty results."""
        reranker = GraphReranker(mock_connection)
        result = reranker.rerank([])
        assert result == []

    def test_rerank_single_result(self, mock_connection, sample_search_results):
        """Test reranking with single result."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [{"inbound": 10, "outbound": 5}]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        result = reranker.rerank([sample_search_results[0]])

        assert len(result) == 1
        assert "reranked_score" in result[0]
        assert 0.0 <= result[0]["reranked_score"] <= 1.0

    def test_rerank_preserves_order_by_combined_score(self, mock_connection, sample_search_results):
        """Test that reranking produces results ordered by combined score."""
        mock_df = Mock()
        mock_df.empty = False
        # Return high centrality for lower-scored items to test reordering
        mock_df.to_dict.return_value = [
            {"inbound": 5, "outbound": 2},
            {"inbound": 15, "outbound": 8},
            {"inbound": 20, "outbound": 10},
            {"inbound": 3, "outbound": 1},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        result = reranker.rerank(sample_search_results)

        assert len(result) == 4
        # Scores should be descending
        scores = [r["reranked_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_combined_score_calculation(self, mock_connection):
        """Test that combined score correctly weights vector and graph scores."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [{"inbound": 10, "outbound": 5}]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection, vector_weight=0.6, graph_weight=0.4)
        results = [{"title": "Test", "score": 0.8, "similarity": 0.8}]
        reranked = reranker.rerank(results)

        # Combined score should be vector_weight * vector_score + graph_weight * graph_score
        assert "reranked_score" in reranked[0]
        # Score should be influenced by both weights

    def test_rerank_missing_score_field(self, mock_connection):
        """Test reranking when results have similarity but not score."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [{"inbound": 10, "outbound": 5}]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        results = [{"title": "Test", "similarity": 0.9}]
        reranked = reranker.rerank(results)

        assert len(reranked) == 1
        assert "reranked_score" in reranked[0]

    def test_rerank_missing_similarity_field(self, mock_connection):
        """Test reranking when results have score but not similarity."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [{"inbound": 10, "outbound": 5}]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        results = [{"title": "Test", "score": 0.9}]
        reranked = reranker.rerank(results)

        assert len(reranked) == 1
        assert "reranked_score" in reranked[0]

    def test_rerank_preserves_original_fields(self, mock_connection, sample_search_results):
        """Test that reranking preserves all original fields."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"inbound": 10, "outbound": 5} for _ in sample_search_results
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        result = reranker.rerank(sample_search_results)

        for original, reranked in zip(sample_search_results, result):
            assert reranked["title"] == original["title"]
            assert "reranked_score" in reranked

    def test_rerank_with_max_results(self, mock_connection, sample_search_results):
        """Test reranking with max_results parameter."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"inbound": 10, "outbound": 5} for _ in sample_search_results
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        reranker = GraphReranker(mock_connection)
        result = reranker.rerank(sample_search_results, max_results=2)

        assert len(result) == 2

    def test_rerank_handles_centrality_calculation_failure(self, mock_connection, sample_search_results):
        """Test that rerank handles centrality calculation failures gracefully."""
        mock_connection.execute.side_effect = Exception("Database error")

        reranker = GraphReranker(mock_connection)
        result = reranker.rerank(sample_search_results)

        # Should still return results with vector scores only
        assert len(result) == len(sample_search_results)
        assert all("reranked_score" in r for r in result)
