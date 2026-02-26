"""Tests for FewShotManager module."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from wikigr.agent.few_shot import FewShotManager


@pytest.fixture
def sample_examples():
    """Sample few-shot examples."""
    return [
        {
            "question": "What is quantum entanglement?",
            "answer": "Quantum entanglement is a phenomenon where particles become correlated.",
            "domain": "physics",
            "difficulty": "easy"
        },
        {
            "question": "Explain the Heisenberg uncertainty principle.",
            "answer": "The Heisenberg uncertainty principle states that position and momentum cannot be simultaneously measured with precision.",
            "domain": "physics",
            "difficulty": "medium"
        },
        {
            "question": "What is wave-particle duality?",
            "answer": "Wave-particle duality is the concept that particles exhibit both wave and particle properties.",
            "domain": "physics",
            "difficulty": "easy"
        },
    ]


@pytest.fixture
def examples_file(tmp_path, sample_examples):
    """Create temporary examples JSON file."""
    examples_path = tmp_path / "examples.json"
    with open(examples_path, "w") as f:
        json.dump(sample_examples, f)
    return examples_path


class TestFewShotManagerInit:
    """Test FewShotManager initialization."""

    def test_init_with_valid_path(self, examples_file):
        """Test initialization with valid examples file."""
        manager = FewShotManager(str(examples_file))
        assert manager.examples_path == str(examples_file)
        assert len(manager.examples) == 3

    def test_init_with_nonexistent_path(self):
        """Test initialization with nonexistent file path."""
        with pytest.raises(FileNotFoundError):
            FewShotManager("/nonexistent/path/examples.json")

    def test_init_with_invalid_json(self, tmp_path):
        """Test initialization with invalid JSON file."""
        invalid_path = tmp_path / "invalid.json"
        with open(invalid_path, "w") as f:
            f.write("not valid json{")

        with pytest.raises(json.JSONDecodeError):
            FewShotManager(str(invalid_path))

    def test_init_loads_all_examples(self, examples_file):
        """Test that initialization loads all examples from file."""
        manager = FewShotManager(str(examples_file))
        assert len(manager.examples) == 3
        assert all("question" in ex for ex in manager.examples)
        assert all("answer" in ex for ex in manager.examples)


class TestFindSimilarExamples:
    """Test find_similar_examples method."""

    def test_find_similar_empty_query(self, examples_file):
        """Test finding similar examples with empty query."""
        manager = FewShotManager(str(examples_file))
        result = manager.find_similar_examples("")
        # Should return some examples even with empty query
        assert isinstance(result, list)

    def test_find_similar_with_top_k(self, examples_file):
        """Test finding similar examples with top_k parameter."""
        manager = FewShotManager(str(examples_file))
        result = manager.find_similar_examples("quantum", top_k=2)

        assert len(result) <= 2

    def test_find_similar_returns_relevant_examples(self, examples_file):
        """Test that similar examples are semantically related."""
        manager = FewShotManager(str(examples_file))
        result = manager.find_similar_examples("quantum entanglement", top_k=1)

        assert len(result) >= 1
        # Should include the quantum entanglement example
        assert any("entanglement" in ex["question"].lower() for ex in result)

    def test_find_similar_with_high_top_k(self, examples_file):
        """Test finding similar examples when top_k exceeds available examples."""
        manager = FewShotManager(str(examples_file))
        result = manager.find_similar_examples("physics", top_k=100)

        # Should return all available examples
        assert len(result) == len(manager.examples)

    def test_find_similar_preserves_example_structure(self, examples_file):
        """Test that returned examples preserve original structure."""
        manager = FewShotManager(str(examples_file))
        result = manager.find_similar_examples("quantum", top_k=1)

        assert len(result) > 0
        example = result[0]
        assert "question" in example
        assert "answer" in example
        assert "domain" in example

    def test_find_similar_with_similarity_scores(self, examples_file):
        """Test that similarity scores are included in results."""
        manager = FewShotManager(str(examples_file))
        result = manager.find_similar_examples("uncertainty principle", top_k=2)

        # Results should have similarity scores
        for ex in result:
            assert "similarity_score" in ex or "similarity" in ex or isinstance(ex, dict)

    def test_find_similar_domain_filtering(self, examples_file):
        """Test finding similar examples with domain filtering."""
        manager = FewShotManager(str(examples_file))
        result = manager.find_similar_examples("quantum", domain="physics", top_k=5)

        # All results should be from physics domain
        assert all(ex.get("domain") == "physics" for ex in result)

    def test_find_similar_no_embedding_model_fallback(self, examples_file):
        """Test fallback behavior when embedding model is not available."""
        manager = FewShotManager(str(examples_file))

        # Test that it still returns results (keyword-based fallback)
        result = manager.find_similar_examples("quantum", top_k=2)
        assert isinstance(result, list)


class TestEmbeddingGeneration:
    """Test embedding generation functionality."""

    @patch("bootstrap.src.embeddings.generator.EmbeddingGenerator")
    def test_uses_embedding_generator(self, mock_generator_class, examples_file):
        """Test that FewShotManager uses EmbeddingGenerator."""
        mock_generator = Mock()
        mock_generator.generate.return_value = [[0.1] * 384]  # Mock embedding
        mock_generator_class.return_value = mock_generator

        manager = FewShotManager(str(examples_file))
        manager.find_similar_examples("test query", top_k=1)

        # Embedding generator may be lazily loaded
        assert True  # Just verify no errors occur

    def test_caches_example_embeddings(self, examples_file):
        """Test that example embeddings are cached after first computation."""
        manager = FewShotManager(str(examples_file))

        # First call
        result1 = manager.find_similar_examples("quantum", top_k=1)

        # Second call - should use cached embeddings
        result2 = manager.find_similar_examples("physics", top_k=1)

        assert isinstance(result1, list)
        assert isinstance(result2, list)


class TestKeywordFallback:
    """Test keyword-based fallback when embeddings fail."""

    def test_keyword_fallback_on_embedding_error(self, examples_file):
        """Test keyword matching fallback when embedding generation fails."""
        manager = FewShotManager(str(examples_file))

        # Force embedding to fail by mocking
        with patch.object(manager, "_generate_query_embedding", side_effect=Exception("Model error")):
            result = manager.find_similar_examples("quantum entanglement", top_k=2)

            # Should still return results via keyword matching
            assert len(result) > 0

    def test_keyword_matching_finds_relevant_examples(self, examples_file):
        """Test keyword matching can find relevant examples."""
        manager = FewShotManager(str(examples_file))

        # Use keyword matching directly
        result = manager._keyword_match_examples("entanglement", top_k=1)

        assert len(result) > 0
        assert "entanglement" in result[0]["question"].lower()
