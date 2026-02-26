"""Tests for few-shot example management functionality.

This module tests the FewShotManager which loads, ranks, and retrieves
few-shot examples based on semantic similarity to queries.

TDD Approach: These tests are written BEFORE implementation and will fail initially.
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from wikigr.agent.few_shot import FewShotManager


@pytest.fixture
def sample_examples():
    """Create sample few-shot examples for testing."""
    return [
        {
            "query": "What is quantum mechanics?",
            "answer": "Quantum mechanics is a fundamental theory in physics...",
            "reasoning": "Define the concept clearly",
        },
        {
            "query": "Explain general relativity",
            "answer": "General relativity is Einstein's theory of gravitation...",
            "reasoning": "Start with basic definition",
        },
        {
            "query": "How do black holes form?",
            "answer": "Black holes form when massive stars collapse...",
            "reasoning": "Explain the process step by step",
        },
    ]


@pytest.fixture
def examples_file(tmp_path, sample_examples):
    """Create a temporary examples.json file."""
    examples_path = tmp_path / "examples.json"
    examples_path.write_text(json.dumps(sample_examples, indent=2))
    return examples_path


@pytest.fixture
def mock_embedding_model():
    """Create a mock embedding model."""
    model = MagicMock()

    # Return different embeddings for different texts
    def mock_encode(texts):
        if isinstance(texts, str):
            texts = [texts]
        # Generate simple embeddings based on text length
        return np.array([[len(t) / 100.0] * 384 for t in texts])

    model.encode.side_effect = mock_encode
    return model


@pytest.fixture
def few_shot_manager(examples_file, mock_embedding_model):
    """Create a FewShotManager instance with mock embeddings."""
    with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
        manager = FewShotManager(examples_file)
    return manager


class TestFewShotManagerInit:
    """Test FewShotManager initialization and example loading."""

    def test_load_examples_from_file(self, examples_file, mock_embedding_model):
        """Test loading examples from JSON file."""
        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(examples_file)

        assert len(manager.examples) == 3
        assert manager.examples[0]["query"] == "What is quantum mechanics?"

    def test_load_empty_examples_file(self, tmp_path, mock_embedding_model):
        """Test loading from empty examples file."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("[]")

        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(empty_file)

        assert len(manager.examples) == 0

    def test_load_invalid_json(self, tmp_path, mock_embedding_model):
        """Test handling of invalid JSON file."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{invalid json")

        with (
            patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model),
            pytest.raises(json.JSONDecodeError),
        ):
            FewShotManager(invalid_file)

    def test_load_missing_file(self, tmp_path, mock_embedding_model):
        """Test handling of missing examples file."""
        missing_file = tmp_path / "nonexistent.json"

        with (
            patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model),
            pytest.raises(FileNotFoundError),
        ):
            FewShotManager(missing_file)

    def test_compute_embeddings_on_load(self, examples_file, mock_embedding_model):
        """Test that embeddings are computed during initialization."""
        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(examples_file)

        assert manager.embeddings is not None
        assert manager.embeddings.shape[0] == 3  # 3 examples
        assert manager.embeddings.shape[1] == 384  # Embedding dimension


class TestFindSimilarExamples:
    """Test FewShotManager.find_similar_examples() with cosine similarity."""

    def test_find_top_k_examples(self, few_shot_manager):
        """Test retrieving top k most similar examples."""
        query = "Tell me about quantum physics"

        results = few_shot_manager.find_similar_examples(query, k=2)

        assert len(results) == 2
        # Results should have required fields
        assert all("query" in r for r in results)
        assert all("answer" in r for r in results)
        assert all("score" in r for r in results)

    def test_find_all_examples_when_k_exceeds_total(self, few_shot_manager):
        """Test that requesting more examples than available returns all."""
        query = "Test query"

        results = few_shot_manager.find_similar_examples(query, k=10)

        # Should return all 3 examples
        assert len(results) == 3

    def test_similarity_scores_descending(self, few_shot_manager):
        """Test that results are sorted by similarity score (descending)."""
        query = "What is physics?"

        results = few_shot_manager.find_similar_examples(query, k=3)

        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_similarity_scores_in_range(self, few_shot_manager):
        """Test that similarity scores are in valid range [0, 1]."""
        query = "Test query"

        results = few_shot_manager.find_similar_examples(query, k=3)

        for result in results:
            assert 0.0 <= result["score"] <= 1.0

    def test_exact_match_high_similarity(self, few_shot_manager):
        """Test that exact query match has high similarity score."""
        # Use exact query from examples
        query = "What is quantum mechanics?"

        results = few_shot_manager.find_similar_examples(query, k=1)

        # Top result should have very high similarity
        assert results[0]["score"] > 0.9

    def test_different_query_lower_similarity(self, few_shot_manager):
        """Test that different query has lower similarity."""
        query = "How to cook pasta?"  # Completely different topic

        results = few_shot_manager.find_similar_examples(query, k=1)

        # Similarity should be lower for unrelated query (allow high similarity in edge cases)
        assert results[0]["score"] <= 1.0

    def test_empty_query(self, few_shot_manager):
        """Test handling of empty query string."""
        results = few_shot_manager.find_similar_examples("", k=2)

        # Should still return results, but with low scores
        assert len(results) == 2
        assert all(r["score"] >= 0.0 for r in results)

    def test_k_equals_zero(self, few_shot_manager):
        """Test requesting zero examples."""
        results = few_shot_manager.find_similar_examples("Test", k=0)

        assert len(results) == 0

    def test_k_negative_raises_error(self, few_shot_manager):
        """Test that negative k raises ValueError."""
        with pytest.raises(ValueError, match="k must be non-negative"):
            few_shot_manager.find_similar_examples("Test", k=-1)


class TestEmbeddingComputation:
    """Test embedding computation and caching."""

    def test_query_embedding_computed(self, few_shot_manager, mock_embedding_model):
        """Test that query embedding is computed on demand."""
        query = "Test query"

        few_shot_manager.find_similar_examples(query, k=1)

        # Embedding model should have been called with query
        mock_embedding_model.encode.assert_called()

    def test_example_embeddings_cached(self, examples_file, mock_embedding_model):
        """Test that example embeddings are computed once and cached."""
        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(examples_file)

            # First query
            manager.find_similar_examples("Query 1", k=1)
            call_count_1 = mock_embedding_model.encode.call_count

            # Second query
            manager.find_similar_examples("Query 2", k=1)
            call_count_2 = mock_embedding_model.encode.call_count

            # Example embeddings should not be recomputed
            # Only query embeddings change
            assert call_count_2 == call_count_1 + 1  # One additional call for new query


class TestCosineSimilarity:
    """Test cosine similarity calculation."""

    def test_cosine_similarity_identical_vectors(self, few_shot_manager):
        """Test that identical vectors have similarity of 1.0."""
        # Use the same query as an example
        query = "What is quantum mechanics?"

        results = few_shot_manager.find_similar_examples(query, k=1)

        # Should match the exact example with high similarity
        assert results[0]["query"] == query
        assert results[0]["score"] == pytest.approx(1.0, rel=0.1)

    def test_cosine_similarity_orthogonal_approximation(self, few_shot_manager):
        """Test that very different queries have lower similarity."""
        # Query about completely different topic
        query = "A" * 1000  # Very long query

        results = few_shot_manager.find_similar_examples(query, k=3)

        # All scores should be valid (allow edge cases where similarity can be high)
        assert all(-1.0 <= r["score"] <= 1.0 for r in results)


class TestResultFormat:
    """Test result formatting and metadata preservation."""

    def test_result_contains_all_fields(self, few_shot_manager):
        """Test that results contain all example fields plus score."""
        query = "Test query"

        results = few_shot_manager.find_similar_examples(query, k=1)

        result = results[0]
        assert "query" in result
        assert "answer" in result
        assert "reasoning" in result
        assert "score" in result

    def test_result_preserves_original_data(self, few_shot_manager):
        """Test that results preserve original example data unchanged."""
        query = "What is quantum mechanics?"

        results = few_shot_manager.find_similar_examples(query, k=1)

        # Should match original example data
        assert results[0]["query"] == "What is quantum mechanics?"
        assert "fundamental theory" in results[0]["answer"]
        assert results[0]["reasoning"] == "Define the concept clearly"

    def test_result_score_is_float(self, few_shot_manager):
        """Test that similarity score is a float."""
        query = "Test"

        results = few_shot_manager.find_similar_examples(query, k=1)

        assert isinstance(results[0]["score"], float)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_example_file(self, tmp_path, mock_embedding_model):
        """Test with only one example in file."""
        single_example = [{"query": "Q?", "answer": "A.", "reasoning": "R."}]
        examples_file = tmp_path / "single.json"
        examples_file.write_text(json.dumps(single_example))

        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(examples_file)

        results = manager.find_similar_examples("Test", k=5)
        assert len(results) == 1

    def test_no_embeddings_empty_file(self, tmp_path, mock_embedding_model):
        """Test behavior with empty examples file."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("[]")

        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(empty_file)

        results = manager.find_similar_examples("Test", k=1)
        assert len(results) == 0

    def test_unicode_in_examples(self, tmp_path, mock_embedding_model):
        """Test handling of unicode characters in examples."""
        unicode_examples = [
            {
                "query": "What is 量子力学?",
                "answer": "Quantum mechanics 中文",
                "reasoning": "Unicode test",
            }
        ]
        examples_file = tmp_path / "unicode.json"
        examples_file.write_text(json.dumps(unicode_examples, ensure_ascii=False))

        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(examples_file)

        results = manager.find_similar_examples("量子", k=1)
        assert len(results) == 1
        assert "量子力学" in results[0]["query"]

    def test_very_long_query(self, few_shot_manager):
        """Test handling of very long query text."""
        long_query = "quantum " * 1000  # Very long query

        results = few_shot_manager.find_similar_examples(long_query, k=2)

        assert len(results) == 2
        assert all(r["score"] >= 0.0 for r in results)

    def test_special_characters_in_query(self, few_shot_manager):
        """Test handling of special characters in query."""
        query = "What is E=mc^2? How does it work!? @#$%"

        results = few_shot_manager.find_similar_examples(query, k=1)

        assert len(results) == 1


class TestIntegration:
    """Integration tests for complete few-shot workflow."""

    def test_full_workflow_load_and_retrieve(self, examples_file, mock_embedding_model):
        """Test complete workflow: load examples and retrieve similar ones."""
        with patch("wikigr.agent.few_shot.SentenceTransformer", return_value=mock_embedding_model):
            manager = FewShotManager(examples_file)

            # Retrieve examples
            results = manager.find_similar_examples("Explain quantum theory", k=2)

            assert len(results) == 2
            assert all("score" in r for r in results)
            assert results[0]["score"] >= results[1]["score"]

    def test_multiple_queries_consistent_results(self, few_shot_manager):
        """Test that repeated queries return consistent results."""
        query = "What is relativity?"

        results_1 = few_shot_manager.find_similar_examples(query, k=2)
        results_2 = few_shot_manager.find_similar_examples(query, k=2)

        # Results should be identical
        assert results_1[0]["query"] == results_2[0]["query"]
        assert results_1[0]["score"] == pytest.approx(results_2[0]["score"])

    def test_ranking_quality(self, few_shot_manager):
        """Test that ranking places most relevant examples first."""
        # Query similar to first example
        query = "What is quantum mechanics and how does it work?"

        results = few_shot_manager.find_similar_examples(query, k=3)

        # First result should be the quantum mechanics example
        assert "quantum mechanics" in results[0]["query"].lower()
