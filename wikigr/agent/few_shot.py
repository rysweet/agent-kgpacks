"""Few-shot example management for query improvement.

This module provides FewShotManager which loads, ranks, and retrieves
few-shot examples based on semantic similarity to queries.

API Contract:
    FewShotManager(examples_path: Path) -> instance
    find_similar_examples(query: str, k: int = 3) -> list[dict]

Design Philosophy:
    - Sentence-transformers for semantic embeddings
    - Cosine similarity for ranking
    - Precomputed embeddings cached in memory
    - Simple top-k retrieval
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class FewShotManager:
    """Manages and retrieves few-shot examples using semantic similarity."""

    def __init__(self, examples_path: Path | str):
        """Initialize manager and load examples from JSON file.

        Args:
            examples_path: Path to JSON file with examples
                Format: [{"query": "...", "answer": "...", "reasoning": "..."}, ...]

        Raises:
            FileNotFoundError: If examples file doesn't exist
            json.JSONDecodeError: If examples file is invalid JSON
        """
        self.examples_path = Path(examples_path)

        # Load examples from file
        if not self.examples_path.exists():
            raise FileNotFoundError(f"Examples file not found: {self.examples_path}")

        with open(self.examples_path) as f:
            # Support both JSON array and JSONL (one object per line) formats
            content = f.read().strip()
            if content.startswith("["):
                self.examples = json.loads(content)
            else:
                self.examples = [json.loads(line) for line in content.splitlines() if line.strip()]

        # Security: Validate example count to prevent OOM
        if len(self.examples) > 1000:
            raise ValueError(f"Too many examples: {len(self.examples)} (max 1000)")

        # Initialize embedding model (sentence-transformers)
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # Precompute embeddings for all examples
        if self.examples:
            queries = [ex.get("query", ex.get("question", "")) for ex in self.examples]
            self.embeddings = np.array(self.model.encode(queries))
        else:
            self.embeddings = np.array([])

        logger.info(f"Loaded {len(self.examples)} few-shot examples from {self.examples_path}")

    def find_similar_examples(self, query: str, k: int = 3) -> list[dict[str, Any]]:
        """Find k most similar examples to query using cosine similarity.

        Args:
            query: Input query to match against examples
            k: Number of examples to return (default 3)

        Returns:
            List of dicts with example fields plus "score" (cosine similarity in [-1, 1])
            Sorted by similarity score (descending)

        Raises:
            ValueError: If k is negative

        Example:
            >>> manager = FewShotManager("examples.json")
            >>> results = manager.find_similar_examples("What is quantum mechanics?", k=2)
            >>> assert len(results) <= 2
            >>> assert all("score" in r for r in results)
            >>> assert results[0]["score"] >= results[1]["score"]
        """
        if k < 0:
            raise ValueError("k must be non-negative")

        if k == 0 or not self.examples:
            return []

        # Compute query embedding
        query_embedding = np.array(self.model.encode([query]))[0]

        # Calculate cosine similarity with all examples
        similarities = self._cosine_similarity(query_embedding, self.embeddings)

        # Get top-k indices (use stable sort to preserve order for equal scores)
        top_k = min(k, len(self.examples))
        # Sort by negative similarity to get descending order, stable sort preserves original order for ties
        top_indices = np.argsort(-similarities, kind="stable")[:top_k]

        # Build results with scores
        results = []
        for idx in top_indices:
            example = self.examples[idx].copy()
            example["score"] = float(similarities[idx])
            results.append(example)

        return results

    def _cosine_similarity(self, query_vec: np.ndarray, example_vecs: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity between query and example vectors.

        Args:
            query_vec: Query embedding vector (1D)
            example_vecs: Example embedding matrix (2D)

        Returns:
            Array of similarity scores (cosine similarity in [-1, 1])
        """
        # Handle zero vectors gracefully
        query_norm_val = np.linalg.norm(query_vec)
        if query_norm_val == 0:
            return np.zeros(len(example_vecs))

        # Normalize query vector
        query_norm = query_vec / query_norm_val

        # Normalize example vectors
        example_norm_vals = np.linalg.norm(example_vecs, axis=1, keepdims=True)
        example_norm_vals = np.where(example_norm_vals == 0, 1, example_norm_vals)
        example_norms = example_vecs / example_norm_vals

        # Compute dot product (cosine similarity)
        similarities = np.dot(example_norms, query_norm)

        # Clip to handle numerical precision issues
        return np.clip(similarities, -1.0, 1.0)
