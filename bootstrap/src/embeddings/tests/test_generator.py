"""
Unit tests for EmbeddingGenerator.

Tests verify the module fulfills its contract:
- Generates embeddings of correct shape (N, 384)
- Handles batch processing correctly
- Auto-detects GPU availability
- Provides consistent output
- Handles errors appropriately
"""

import numpy as np
import pytest

from bootstrap.src.embeddings import EmbeddingGenerator


class TestEmbeddingGenerator:
    """Test suite for EmbeddingGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create generator instance for tests."""
        # Force CPU for deterministic testing
        return EmbeddingGenerator(use_gpu=False)

    @pytest.fixture
    def sample_texts(self):
        """Sample texts for testing."""
        return [
            "Machine learning is a field of artificial intelligence",
            "Deep learning uses neural networks",
            "Python is a programming language",
        ]

    def test_initialization_cpu(self):
        """Test generator initializes with CPU device."""
        gen = EmbeddingGenerator(use_gpu=False)
        assert gen.device == "cpu"
        assert gen.model_name == "paraphrase-MiniLM-L3-v2"

    def test_initialization_auto_detect(self):
        """Test generator auto-detects device."""
        gen = EmbeddingGenerator(use_gpu=None)
        assert gen.device in ["cpu", "cuda"]

    def test_generate_shape(self, generator, sample_texts):
        """Test embeddings have correct shape (N, 384)."""
        embeddings = generator.generate(sample_texts)
        assert embeddings.shape == (3, 384)

    def test_generate_type(self, generator, sample_texts):
        """Test embeddings are numpy arrays."""
        embeddings = generator.generate(sample_texts)
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.dtype == np.float32

    def test_generate_non_zero(self, generator, sample_texts):
        """Test embeddings are not all zeros."""
        embeddings = generator.generate(sample_texts)
        assert not np.allclose(embeddings, 0)

    def test_generate_nonzero_norms(self, generator, sample_texts):
        """Test embeddings have non-zero L2 norms."""
        embeddings = generator.generate(sample_texts)
        norms = np.linalg.norm(embeddings, axis=1)
        assert all(norm > 0.1 for norm in norms)

    def test_generate_single_text(self, generator):
        """Test generating embedding for single text."""
        embeddings = generator.generate(["Single text"])
        assert embeddings.shape == (1, 384)

    def test_generate_large_batch(self, generator):
        """Test generating embeddings for 100 texts."""
        texts = [f"Sample text number {i}" for i in range(100)]
        embeddings = generator.generate(texts, batch_size=32)
        assert embeddings.shape == (100, 384)

    def test_generate_consistency(self, generator):
        """Test same text produces same embedding."""
        text = ["Consistent embedding test"]
        emb1 = generator.generate(text)
        emb2 = generator.generate(text)
        # Should be exactly the same (deterministic)
        assert np.allclose(emb1, emb2)

    def test_generate_similarity(self, generator):
        """Test similar texts have high cosine similarity."""
        texts = ["Machine learning", "Deep learning"]
        embeddings = generator.generate(texts)

        # Calculate cosine similarity
        e1, e2 = embeddings[0], embeddings[1]
        similarity = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))

        # Similar texts should have similarity > 0.5
        assert similarity > 0.5

    def test_generate_dissimilarity(self, generator):
        """Test dissimilar texts have low cosine similarity."""
        texts = ["Machine learning algorithms", "The quick brown fox"]
        embeddings = generator.generate(texts)

        # Calculate cosine similarity
        e1, e2 = embeddings[0], embeddings[1]
        similarity = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))

        # Dissimilar texts should have lower similarity
        assert similarity < 0.7

    def test_generate_empty_list_raises(self, generator):
        """Test empty text list raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            generator.generate([])

    def test_batch_size_parameter(self, generator):
        """Test different batch sizes produce same results."""
        texts = [f"Text {i}" for i in range(10)]
        emb_batch_2 = generator.generate(texts, batch_size=2)
        emb_batch_5 = generator.generate(texts, batch_size=5)

        # Different batch sizes should produce identical results
        assert np.allclose(emb_batch_2, emb_batch_5)

    def test_show_progress_parameter(self, generator, sample_texts):
        """Test show_progress parameter doesn't affect output."""
        emb_no_progress = generator.generate(sample_texts, show_progress=False)
        emb_progress = generator.generate(sample_texts, show_progress=True)

        # Progress bar shouldn't affect embeddings
        assert np.allclose(emb_no_progress, emb_progress)

    def test_repr(self, generator):
        """Test string representation."""
        repr_str = repr(generator)
        assert "EmbeddingGenerator" in repr_str
        assert "paraphrase-MiniLM-L3-v2" in repr_str
        assert "cpu" in repr_str

    def test_variance(self, generator):
        """Test embeddings have reasonable variance (not all same)."""
        texts = [f"Different text {i}" for i in range(10)]
        embeddings = generator.generate(texts)

        # Embeddings should differ significantly
        variance = embeddings.var()
        assert variance > 0.001  # Should have meaningful variance


if __name__ == "__main__":
    # Run tests with pytest if available, otherwise run basic tests
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        print("pytest not available, running basic tests...")
        gen = EmbeddingGenerator(use_gpu=False)
        texts = ["Test 1", "Test 2", "Test 3"]
        embeddings = gen.generate(texts)
        assert embeddings.shape == (3, 384)
        print("✓ Basic tests passed!")
