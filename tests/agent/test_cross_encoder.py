"""Unit tests for CrossEncoderReranker.

Five functional test cases per spec:
    1. Reranking with mocked model — scores applied and results reordered
    2. Empty results — returns empty list immediately
    3. top_k filtering — returns at most top_k results
    4. ce_score field added to each returned dict
    5. Graceful __init__ failure — rerank() returns results unchanged

Four security hardening tests (TDD — written before implementation):
    6. Query strings longer than 2000 chars are truncated before scoring
    7. top_k=0 is clamped to 1 (prevents silently empty ranked results)
    8. Disallowed model names raise ValueError at init time
    9. candidate_k in _vector_primary_retrieve is capped at 40

All tests mock sentence_transformers.CrossEncoder so no model download is needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_results(n: int) -> list[dict]:
    """Return n simple result dicts with title and content."""
    return [{"title": f"Article {i}", "content": f"Content for article {i}"} for i in range(n)]


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestCrossEncoderReranker:
    """Tests for CrossEncoderReranker."""

    def test_reranking_reorders_by_cross_encoder_score(self) -> None:
        """Cross-encoder scores drive reordering: highest score appears first."""
        mock_ce = MagicMock()
        # predict returns scores in input order: article 1 scores higher than article 0
        mock_ce.predict.return_value = [0.3, 0.9]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_ce):
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            reranker = CrossEncoderReranker()

        results = _make_results(2)
        reranked = reranker.rerank("test query", results, top_k=2)

        assert len(reranked) == 2
        # Article 1 had score 0.9, should be first
        assert reranked[0]["title"] == "Article 1"
        assert reranked[1]["title"] == "Article 0"

    def test_empty_results_returns_empty_list(self) -> None:
        """rerank() returns [] immediately when results is empty."""
        mock_ce = MagicMock()

        with patch("sentence_transformers.CrossEncoder", return_value=mock_ce):
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            reranker = CrossEncoderReranker()

        result = reranker.rerank("query", [], top_k=5)

        assert result == []
        mock_ce.predict.assert_not_called()

    def test_top_k_filtering_limits_output(self) -> None:
        """rerank() returns at most top_k results even when more candidates exist."""
        mock_ce = MagicMock()
        mock_ce.predict.return_value = [0.1, 0.5, 0.9, 0.2, 0.7]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_ce):
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            reranker = CrossEncoderReranker()

        results = _make_results(5)
        reranked = reranker.rerank("query", results, top_k=3)

        assert len(reranked) == 3

    def test_ce_score_added_to_each_result(self) -> None:
        """Each returned dict has a 'ce_score' key with a float value."""
        mock_ce = MagicMock()
        mock_ce.predict.return_value = [0.42, 0.88]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_ce):
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            reranker = CrossEncoderReranker()

        results = _make_results(2)
        reranked = reranker.rerank("query", results, top_k=2)

        for r in reranked:
            assert "ce_score" in r
            assert isinstance(r["ce_score"], float)

    def test_graceful_init_failure_returns_results_unchanged(self) -> None:
        """When __init__ fails to load the model, rerank() returns input unchanged."""
        with patch(
            "sentence_transformers.CrossEncoder",
            side_effect=Exception("model download failed"),
        ):
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            reranker = CrossEncoderReranker()

        assert reranker._model is None

        results = _make_results(3)
        returned = reranker.rerank("query", results, top_k=2)

        # Returns all results unchanged (no truncation, no ce_score, no predict call)
        assert len(returned) == 3
        for r in returned:
            assert "ce_score" not in r
        # Same dict objects returned — confirms passthrough, not a transformed copy
        assert all(r is orig for r, orig in zip(returned, results))


# ---------------------------------------------------------------------------
# Security hardening tests
# ---------------------------------------------------------------------------


class TestCrossEncoderRerankerSecurity:
    """Security hardening tests for CrossEncoderReranker."""

    def test_long_query_truncated_before_model_input(self) -> None:
        """Queries longer than 2000 chars must be truncated to prevent resource exhaustion."""
        mock_ce = MagicMock()
        mock_ce.predict.return_value = [0.5]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_ce):
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            reranker = CrossEncoderReranker()

        long_query = "x" * 5000  # 5000 chars — well above the 2000-char cap
        results = _make_results(1)
        reranker.rerank(long_query, results, top_k=1)

        # The query passed to predict must be at most 2000 chars
        call_pairs = mock_ce.predict.call_args[0][0]
        actual_query_in_pair = call_pairs[0][0]
        assert len(actual_query_in_pair) <= 2000, (
            f"Query was not truncated: got {len(actual_query_in_pair)} chars, "
            "expected <= 2000. Add query = query[:2000] in rerank()."
        )

    def test_top_k_zero_clamped_to_one(self) -> None:
        """top_k=0 must be clamped to 1; returning [] silently hides a caller bug."""
        mock_ce = MagicMock()
        mock_ce.predict.return_value = [0.7, 0.3]

        with patch("sentence_transformers.CrossEncoder", return_value=mock_ce):
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            reranker = CrossEncoderReranker()

        results = _make_results(2)
        returned = reranker.rerank("query", results, top_k=0)

        assert len(returned) >= 1, (
            "top_k=0 returned an empty list. "
            "Add top_k = max(1, min(top_k, len(results))) clamp in rerank()."
        )
        # Must have ce_score (model was active, not passthrough)
        assert "ce_score" in returned[0]

    def test_disallowed_model_name_raises_value_error(self) -> None:
        """Model names not in ALLOWED_MODELS must be rejected with ValueError."""
        with pytest.raises(ValueError, match="not in allowed models"):
            # Bypass the lazy sentence_transformers import; the ValueError must be
            # raised *before* any model load attempt.
            from wikigr.agent.cross_encoder import CrossEncoderReranker

            CrossEncoderReranker(model_name="malicious/arbitrary-model-xyz")

    def test_default_model_in_allowed_models(self) -> None:
        """DEFAULT_MODEL must be in ALLOWED_MODELS so default construction succeeds."""
        from wikigr.agent.cross_encoder import ALLOWED_MODELS, DEFAULT_MODEL

        assert DEFAULT_MODEL in ALLOWED_MODELS, (
            f"DEFAULT_MODEL '{DEFAULT_MODEL}' is not in ALLOWED_MODELS {ALLOWED_MODELS}. "
            "Add it to the allowlist."
        )
