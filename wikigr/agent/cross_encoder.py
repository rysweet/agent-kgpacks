"""Cross-encoder reranking for improved retrieval precision.

Jointly scores query-document pairs via a cross-encoder model, providing much
higher relevance precision than bi-encoder vector search alone.

Design:
    - CPU-only inference (no GPU required)
    - Graceful degradation: __init__ failure sets _model = None; rerank() returns
      results unchanged rather than raising
    - Shallow copies of result dicts with ce_score added (does not mutate caller's list)
    - Sorted by ce_score descending
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-12-v2"

# Allowlist of permitted HuggingFace cross-encoder model identifiers.
# Prevents path-traversal or malicious repo injection if model_name
# is ever surfaced as a configurable parameter.
ALLOWED_MODELS: frozenset[str] = frozenset(
    {
        "cross-encoder/ms-marco-MiniLM-L-12-v2",
    }
)


class CrossEncoderReranker:
    """Reranks retrieval results using a cross-encoder model.

    Cross-encoders jointly process query and document text, producing more
    accurate relevance scores than bi-encoders at the cost of ~50ms latency.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        """Load the cross-encoder model.

        Args:
            model_name: HuggingFace model identifier. Defaults to
                'cross-encoder/ms-marco-MiniLM-L-12-v2' (33MB, CPU-only).

        If the model fails to load (e.g. network error on first download),
        a warning is logged and self._model is set to None. Subsequent calls
        to rerank() will return results unchanged.
        """
        if model_name not in ALLOWED_MODELS:
            raise ValueError(
                f"model_name '{model_name}' is not in allowed models {sorted(ALLOWED_MODELS)}. "
                "Add it to ALLOWED_MODELS in cross_encoder.py after security review."
            )
        self._model = None
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(model_name)
            logger.info("CrossEncoderReranker loaded model: %s", model_name)
        except Exception as e:
            logger.warning(
                "CrossEncoderReranker failed to load model '%s': %s. "
                "Reranking will be skipped.",
                model_name,
                e,
            )

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Rerank results using cross-encoder scores.

        Args:
            query: The search query string.
            results: List of result dicts. Each dict must contain a 'content'
                or 'title' key used as the document text for scoring.
            top_k: Maximum number of results to return.

        Returns:
            List of up to top_k result dicts sorted by ce_score descending.
            Each dict is a shallow copy of the input with 'ce_score' (float) added.
            If _model is None (load failure), returns results unchanged (no top_k trim,
            no ce_score added) to preserve caller expectations.
        """
        if not results:
            return []

        if self._model is None:
            return list(results)

        query = query[:2000]  # cap tokenizer input
        top_k = max(1, min(top_k, len(results)))  # clamp: 0 → 1, excess → len(results)

        pairs = [(query, r.get("content") or r.get("title", "")) for r in results]
        scores = self._model.predict(pairs, show_progress_bar=False)

        reranked = [{**r, "ce_score": float(s)} for r, s in zip(results, scores)]
        reranked.sort(key=lambda r: r["ce_score"], reverse=True)
        return reranked[:top_k]
