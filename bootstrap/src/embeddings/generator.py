"""
Embedding Generation Module

Generates vector embeddings using sentence-transformers model.
Model: BAAI/bge-base-en-v1.5 (768 dimensions, retrieval-optimized)

Upgraded from paraphrase-MiniLM-L3-v2 (384d, paraphrase-optimized) based on
MTEB benchmark analysis showing BGE models are significantly better for
information retrieval tasks.
"""

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

# BGE models require a query prefix for retrieval tasks
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbeddingGenerator:
    """
    Generate vector embeddings for text using sentence-transformers.

    Uses BAAI/bge-base-en-v1.5 (768 dimensions) optimized for retrieval.
    For queries (search), use generate_query() which adds the BGE prefix.
    For documents (indexing), use generate() without prefix.
    """

    DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"

    def __init__(self, model_name=None, use_gpu=None):
        """
        Initialize embedding generator.

        Args:
            model_name: Model name from sentence-transformers.
                       Default is BAAI/bge-base-en-v1.5 (768 dims, retrieval-optimized).
            use_gpu: True to force GPU, False to force CPU, None to auto-detect.
                    Auto-detection uses GPU if CUDA is available.
        """
        if model_name is None:
            model_name = self.DEFAULT_MODEL

        if use_gpu is None:
            use_gpu = torch.cuda.is_available()

        device = "cuda" if use_gpu else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.device = device
        self.model_name = model_name
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

    def generate(self, texts: list[str], batch_size=32, show_progress=False) -> np.ndarray:
        """
        Generate embeddings for documents (indexing).

        No query prefix is added — use this for storing document embeddings.
        For search queries, use generate_query() instead.

        Args:
            texts: List of text strings to embed.
            batch_size: Number of texts to process per batch.
            show_progress: If True, display progress bar during encoding.

        Returns:
            numpy.ndarray: Array of shape (N, D) where D is the model's dimension.
        """
        if not texts:
            raise ValueError("texts list cannot be empty")

        embeddings = self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=show_progress, convert_to_numpy=True
        )
        return embeddings

    def generate_query(self, queries: list[str], batch_size=32) -> np.ndarray:
        """
        Generate embeddings for search queries.

        Adds the BGE query prefix for retrieval-optimized models.
        This improves retrieval accuracy by signaling the model that
        the input is a search query, not a document.

        Args:
            queries: List of query strings to embed.
            batch_size: Number of queries to process per batch.

        Returns:
            numpy.ndarray: Array of shape (N, D) where D is the model's dimension.
        """
        if not queries:
            raise ValueError("queries list cannot be empty")

        # Add BGE prefix for retrieval models
        if "bge" in self.model_name.lower():
            prefixed = [BGE_QUERY_PREFIX + q for q in queries]
        else:
            prefixed = queries

        embeddings = self.model.encode(
            prefixed, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True
        )
        return embeddings

    def __repr__(self):
        """String representation showing model and device."""
        return f"EmbeddingGenerator(model='{self.model_name}', dim={self.embedding_dim}, device='{self.device}')"
