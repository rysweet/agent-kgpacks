#!/usr/bin/env python3
"""
Basic usage example for EmbeddingGenerator.

Demonstrates:
- Initialization with auto GPU detection
- Generating embeddings for sample texts
- Calculating cosine similarity
- Batch processing
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from embeddings import EmbeddingGenerator


def main():
    """Run basic embedding generation examples."""
    print("=== EmbeddingGenerator Basic Usage ===\n")

    # 1. Initialize generator
    print("1. Initializing generator (auto-detecting GPU)...")
    gen = EmbeddingGenerator()
    print(f"   {gen}\n")

    # 2. Generate embeddings for sample texts
    print("2. Generating embeddings for sample texts...")
    texts = [
        "Machine learning is a subset of artificial intelligence",
        "Deep learning uses neural networks with many layers",
        "Python is a popular programming language",
        "The quick brown fox jumps over the lazy dog"
    ]

    embeddings = gen.generate(texts, show_progress=False)
    print(f"   Generated {embeddings.shape[0]} embeddings")
    print(f"   Shape: {embeddings.shape}")
    print(f"   Dtype: {embeddings.dtype}\n")

    # 3. Calculate cosine similarities
    print("3. Computing cosine similarities...")

    def cosine_similarity(a, b):
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    # Compare ML and DL (should be high)
    sim_ml_dl = cosine_similarity(embeddings[0], embeddings[1])
    print(f"   'Machine learning' vs 'Deep learning': {sim_ml_dl:.4f}")

    # Compare ML and Python (should be moderate)
    sim_ml_python = cosine_similarity(embeddings[0], embeddings[2])
    print(f"   'Machine learning' vs 'Python': {sim_ml_python:.4f}")

    # Compare ML and fox (should be low)
    sim_ml_fox = cosine_similarity(embeddings[0], embeddings[3])
    print(f"   'Machine learning' vs 'The quick brown fox': {sim_ml_fox:.4f}\n")

    # 4. Batch processing demonstration
    print("4. Batch processing demonstration...")
    large_texts = [f"This is sample text number {i}" for i in range(100)]
    large_embeddings = gen.generate(large_texts, batch_size=32, show_progress=True)
    print(f"   Generated {large_embeddings.shape[0]} embeddings\n")

    # 5. Statistics
    print("5. Embedding statistics...")
    norms = np.linalg.norm(embeddings, axis=1)
    print(f"   Mean L2 norm: {norms.mean():.4f}")
    print(f"   Min L2 norm: {norms.min():.4f}")
    print(f"   Max L2 norm: {norms.max():.4f}")
    print(f"   Embedding variance: {embeddings.var():.6f}\n")

    print("✓ Example completed successfully!")


if __name__ == "__main__":
    main()
