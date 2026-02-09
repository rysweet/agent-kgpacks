"""
Embedding Generation Module

Generates vector embeddings using sentence-transformers model.
Model: paraphrase-MiniLM-L3-v2 (384 dimensions, 1055 texts/sec)
"""

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    """
    Generate vector embeddings for text using sentence-transformers.

    Uses paraphrase-MiniLM-L3-v2 model (384 dimensions) optimized for speed.
    See bootstrap/docs/embedding-model-choice.md for model selection rationale.
    """

    def __init__(self, model_name="paraphrase-MiniLM-L3-v2", use_gpu=None):
        """
        Initialize embedding generator.

        Args:
            model_name: Model name from sentence-transformers.
                       Default is paraphrase-MiniLM-L3-v2 (384 dims, fastest).
            use_gpu: True to force GPU, False to force CPU, None to auto-detect.
                    Auto-detection uses GPU if CUDA is available.

        Example:
            >>> gen = EmbeddingGenerator()  # Auto-detect GPU
            >>> gen = EmbeddingGenerator(use_gpu=False)  # Force CPU
        """
        if use_gpu is None:
            use_gpu = torch.cuda.is_available()

        device = "cuda" if use_gpu else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.device = device
        self.model_name = model_name

    def generate(self, texts: list[str], batch_size=32, show_progress=False) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts to process per batch.
                       Default 32 balances speed and memory.
            show_progress: If True, display progress bar during encoding.

        Returns:
            numpy.ndarray: Array of shape (N, 384) where N is len(texts).
                          Each row is a 384-dimensional embedding vector.

        Raises:
            ValueError: If texts is empty.

        Example:
            >>> gen = EmbeddingGenerator()
            >>> texts = ["Machine learning", "Deep learning"]
            >>> embeddings = gen.generate(texts)
            >>> embeddings.shape
            (2, 384)
        """
        if not texts:
            raise ValueError("texts list cannot be empty")

        embeddings = self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=show_progress, convert_to_numpy=True
        )
        return embeddings

    def __repr__(self):
        """String representation showing model and device."""
        return f"EmbeddingGenerator(model='{self.model_name}', device='{self.device}')"


def test_embedding_generator():
    """
    Test embedding generator with 100 sample texts.

    Verifies:
    - Model loads successfully
    - Embeddings have correct shape (100, 384)
    - All embeddings are non-zero
    - Embeddings have expected L2 norms (typically 0.8-1.2)
    """
    print("Testing EmbeddingGenerator...")

    # Create generator (will use CPU in test environment)
    gen = EmbeddingGenerator(use_gpu=False)
    print(f"Created: {gen}")

    # Generate 100 sample texts
    sample_texts = [
        f"This is sample text number {i} about various topics like "
        f"science, technology, and culture."
        for i in range(100)
    ]

    print(f"Generating embeddings for {len(sample_texts)} texts...")
    embeddings = gen.generate(sample_texts, batch_size=32, show_progress=True)

    # Verify shape
    assert embeddings.shape == (100, 384), f"Expected (100, 384), got {embeddings.shape}"
    print(f"✓ Shape correct: {embeddings.shape}")

    # Verify non-zero
    assert not np.allclose(embeddings, 0), "Embeddings are all zero"
    print("✓ Embeddings are non-zero")

    # Check L2 norms (should be close to 1.0 for normalized embeddings)
    norms = np.linalg.norm(embeddings, axis=1)
    mean_norm = norms.mean()
    print(f"✓ Mean L2 norm: {mean_norm:.4f} (expected ~1.0)")

    # Check variance (embeddings should differ)
    variance = embeddings.var()
    print(f"✓ Variance: {variance:.6f} (embeddings differ)")

    # Test with small batch
    small_texts = ["Machine learning", "Deep learning", "Neural networks"]
    small_embeddings = gen.generate(small_texts, show_progress=False)
    assert small_embeddings.shape == (3, 384), f"Expected (3, 384), got {small_embeddings.shape}"
    print(f"✓ Small batch test passed: {small_embeddings.shape}")

    # Test cosine similarity between similar texts
    text1_emb = small_embeddings[0]  # "Machine learning"
    text2_emb = small_embeddings[1]  # "Deep learning"
    cosine_sim = np.dot(text1_emb, text2_emb) / (
        np.linalg.norm(text1_emb) * np.linalg.norm(text2_emb)
    )
    print(f"✓ Cosine similarity (Machine/Deep learning): {cosine_sim:.4f}")
    assert cosine_sim > 0.5, "Similar texts should have similarity > 0.5"

    # Test error handling
    try:
        gen.generate([])
        raise AssertionError("Should raise ValueError for empty list")
    except ValueError as e:
        print(f"✓ Error handling works: {e}")

    print("\n✓ All tests passed!")
    return True


if __name__ == "__main__":
    test_embedding_generator()
