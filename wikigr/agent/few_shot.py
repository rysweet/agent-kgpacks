"""
FewShotManager - Load and retrieve few-shot examples for query answering.

Uses semantic similarity to find relevant examples from a JSON file.
Falls back to keyword matching if embedding generation fails.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FewShotManager:
    """Manage and retrieve few-shot examples using semantic similarity."""

    def __init__(self, examples_path: str):
        """
        Initialize FewShotManager with examples file.

        Args:
            examples_path: Path to JSON file containing few-shot examples

        Raises:
            FileNotFoundError: If examples file doesn't exist
            json.JSONDecodeError: If examples file is not valid JSON
        """
        self.examples_path = examples_path

        # Load examples from file
        path = Path(examples_path)
        if not path.exists():
            raise FileNotFoundError(f"Examples file not found: {examples_path}")

        with open(path, "r") as f:
            self.examples = json.load(f)

        if not isinstance(self.examples, list):
            raise ValueError("Examples file must contain a JSON array")

        # Lazy-loaded embedding generator
        self._embedding_generator = None
        self._example_embeddings: list[list[float]] | None = None

        logger.info(f"Loaded {len(self.examples)} few-shot examples from {examples_path}")

    def _get_embedding_generator(self):
        """Lazily initialize and return the embedding generator."""
        if self._embedding_generator is None:
            from bootstrap.src.embeddings.generator import EmbeddingGenerator

            self._embedding_generator = EmbeddingGenerator()
        return self._embedding_generator

    def _generate_example_embeddings(self) -> list[list[float]]:
        """Generate embeddings for all examples (cached after first call)."""
        if self._example_embeddings is not None:
            return self._example_embeddings

        try:
            generator = self._get_embedding_generator()
            questions = [ex.get("question", "") for ex in self.examples]
            embeddings = generator.generate(questions)
            self._example_embeddings = [emb.tolist() if hasattr(emb, "tolist") else emb for emb in embeddings]
            return self._example_embeddings
        except Exception as e:
            logger.warning(f"Failed to generate example embeddings: {e}")
            return []

    def _generate_query_embedding(self, query: str) -> list[float] | None:
        """Generate embedding for a query string."""
        try:
            generator = self._get_embedding_generator()
            embeddings = generator.generate([query])
            embedding = embeddings[0]
            return embedding.tolist() if hasattr(embedding, "tolist") else embedding
        except Exception as e:
            logger.warning(f"Failed to generate query embedding: {e}")
            return None

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _keyword_match_examples(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Fallback: Find examples using keyword matching."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_examples: list[tuple[dict, float]] = []

        for example in self.examples:
            question = example.get("question", "").lower()
            question_words = set(question.split())

            # Calculate word overlap score
            overlap = len(query_words & question_words)
            score = overlap / max(len(query_words), 1)

            # Boost score if query is substring of question
            if query_lower in question:
                score += 0.5

            scored_examples.append((example, score))

        # Sort by score and return top_k
        scored_examples.sort(key=lambda x: x[1], reverse=True)
        results = []
        for ex, score in scored_examples[:top_k]:
            result = ex.copy()
            result["similarity_score"] = score
            results.append(result)

        return results

    def find_similar_examples(
        self,
        query: str,
        top_k: int = 3,
        domain: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find most similar few-shot examples to a query.

        Uses semantic similarity via embeddings. Falls back to keyword
        matching if embedding generation fails.

        Args:
            query: Query text to find similar examples for
            top_k: Number of examples to return (max)
            domain: Optional domain filter (e.g., "physics")

        Returns:
            List of examples with similarity scores, ordered by relevance
        """
        if not query:
            # Return random sample for empty query
            return self.examples[:top_k]

        # Filter by domain if specified
        candidates = self.examples
        if domain:
            candidates = [ex for ex in self.examples if ex.get("domain") == domain]

        if not candidates:
            return []

        # Try semantic similarity first
        try:
            example_embeddings = self._generate_example_embeddings()
            query_embedding = self._generate_query_embedding(query)

            if query_embedding and example_embeddings:
                # Calculate similarities
                scored: list[tuple[dict, float]] = []

                for i, example in enumerate(candidates):
                    if i < len(example_embeddings):
                        similarity = self._cosine_similarity(query_embedding, example_embeddings[i])
                        scored.append((example, similarity))

                # Sort by similarity
                scored.sort(key=lambda x: x[1], reverse=True)

                # Add similarity scores to results
                results = []
                for ex, sim in scored[:top_k]:
                    result = ex.copy()
                    result["similarity_score"] = sim
                    results.append(result)

                return results

        except Exception as e:
            logger.warning(f"Semantic similarity failed, falling back to keyword matching: {e}")

        # Fallback to keyword matching
        return self._keyword_match_examples(query, top_k=top_k)
