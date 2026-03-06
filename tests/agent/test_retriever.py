"""Unit tests for wikigr.agent.retriever module.

Targets all 7 public / semi-public functions:
  1. _safe_query
  2. direct_title_lookup
  3. multi_query_retrieve
  4. vector_primary_retrieve
  5. hybrid_retrieve
  6. score_section_quality
  7. fetch_source_text

All tests mock external dependencies (kuzu.Connection, Anthropic client,
EmbeddingGenerator) -- no real DB or network calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

from wikigr.agent.retriever import (
    _safe_query,
    direct_title_lookup,
    fetch_source_text,
    hybrid_retrieve,
    multi_query_retrieve,
    score_section_quality,
    vector_primary_retrieve,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STOP_WORDS: frozenset[str] = frozenset(
    {"the", "is", "a", "an", "of", "in", "to", "and", "for", "on"}
)


@pytest.fixture()
def mock_conn() -> MagicMock:
    """Return a mock Kuzu connection."""
    return MagicMock()


def _mock_execute_result(df: pd.DataFrame) -> MagicMock:
    """Wrap a DataFrame in a mock Kuzu query result."""
    result = MagicMock()
    result.get_as_df.return_value = df
    return result


def _mock_haiku_response(alternatives: list[str]) -> MagicMock:
    """Build a mock Claude Haiku response returning the given alternatives as JSON."""
    content_block = MagicMock()
    content_block.text = json.dumps(alternatives)
    response = MagicMock()
    response.content = [content_block]
    response.usage = MagicMock(input_tokens=10, output_tokens=20)
    return response


# ===================================================================
# 1. _safe_query
# ===================================================================


class TestSafeQuery:
    """_safe_query: wraps conn.execute and returns DataFrame or None."""

    def test_returns_dataframe_on_success(self, mock_conn: MagicMock) -> None:
        df = pd.DataFrame({"col": [1, 2, 3]})
        mock_conn.execute.return_value = _mock_execute_result(df)

        result = _safe_query(mock_conn, "MATCH (n) RETURN n")

        assert result is not None
        assert list(result["col"]) == [1, 2, 3]

    def test_returns_none_on_empty_dataframe(self, mock_conn: MagicMock) -> None:
        mock_conn.execute.return_value = _mock_execute_result(pd.DataFrame())

        result = _safe_query(mock_conn, "MATCH (n) RETURN n")

        assert result is None

    def test_returns_none_on_runtime_error(self, mock_conn: MagicMock) -> None:
        mock_conn.execute.side_effect = RuntimeError("DB connection lost")

        result = _safe_query(mock_conn, "MATCH (n) RETURN n")

        assert result is None

    def test_passes_params(self, mock_conn: MagicMock) -> None:
        df = pd.DataFrame({"col": [42]})
        mock_conn.execute.return_value = _mock_execute_result(df)

        _safe_query(mock_conn, "MATCH (n) WHERE n.id = $id RETURN n", {"id": 42})

        mock_conn.execute.assert_called_once_with("MATCH (n) WHERE n.id = $id RETURN n", {"id": 42})

    def test_passes_empty_params_when_none(self, mock_conn: MagicMock) -> None:
        df = pd.DataFrame({"col": [1]})
        mock_conn.execute.return_value = _mock_execute_result(df)

        _safe_query(mock_conn, "MATCH (n) RETURN n")

        mock_conn.execute.assert_called_once_with("MATCH (n) RETURN n", {})


# ===================================================================
# 2. direct_title_lookup
# ===================================================================


class TestDirectTitleLookup:
    """direct_title_lookup: exact then partial title matching."""

    def test_exact_match_returns_title(self, mock_conn: MagicMock) -> None:
        exact_df = pd.DataFrame({"a.title": ["Quantum Mechanics"]})
        mock_conn.execute.return_value = _mock_execute_result(exact_df)

        result = direct_title_lookup(mock_conn, "What is Quantum Mechanics?")

        assert result == ["Quantum Mechanics"]

    def test_partial_match_when_no_exact(self, mock_conn: MagicMock) -> None:
        # First call (exact match) returns empty, second (partial) returns data.
        empty = pd.DataFrame()
        partial_df = pd.DataFrame({"a.title": ["Quantum Mechanics", "Quantum Computing"]})
        mock_conn.execute.side_effect = [
            _mock_execute_result(empty),
            _mock_execute_result(partial_df),
        ]

        result = direct_title_lookup(mock_conn, "What is quantum?")

        assert "Quantum Mechanics" in result
        assert "Quantum Computing" in result

    def test_limits_to_three_results(self, mock_conn: MagicMock) -> None:
        df = pd.DataFrame({"a.title": [f"Article {i}" for i in range(5)]})
        mock_conn.execute.return_value = _mock_execute_result(df)

        result = direct_title_lookup(mock_conn, "Article")

        assert len(result) <= 3

    def test_empty_on_db_error(self, mock_conn: MagicMock) -> None:
        mock_conn.execute.side_effect = RuntimeError("DB down")

        result = direct_title_lookup(mock_conn, "anything")

        assert result == []

    def test_strips_question_prefix(self, mock_conn: MagicMock) -> None:
        """Verifies that prefixes like 'what is' are stripped before querying."""
        df = pd.DataFrame({"a.title": ["Python"]})
        mock_conn.execute.return_value = _mock_execute_result(df)

        direct_title_lookup(mock_conn, "What is Python?")

        # The query parameter should have 'python' (lowercased, prefix stripped, punctuation removed)
        call_args = mock_conn.execute.call_args_list[0]
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        # The param 'q' should be 'python' (stripped of "what is " prefix and trailing "?")
        assert params["q"] == "python"

    def test_empty_question_returns_empty(self, mock_conn) -> None:
        """Empty or whitespace-only question should return empty list."""
        result = direct_title_lookup(mock_conn, "")
        assert result == []

        result = direct_title_lookup(mock_conn, "   ")
        assert result == []


# ===================================================================
# 3. multi_query_retrieve
# ===================================================================


class TestMultiQueryRetrieve:
    """multi_query_retrieve: expands query via LLM, deduplicates, sorts."""

    def test_happy_path_deduplicates_and_sorts(self) -> None:
        claude_client = MagicMock()
        claude_client.messages.create.return_value = _mock_haiku_response(
            ["Alternative phrasing 1", "Alternative phrasing 2"]
        )
        track_fn = MagicMock()

        # The semantic search returns overlapping results for different queries
        call_count = 0

        def _semantic_search(query, top_k=5):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    {"title": "Article A", "similarity": 0.9},
                    {"title": "Article B", "similarity": 0.7},
                ]
            elif call_count == 2:
                return [
                    {"title": "Article A", "similarity": 0.85},  # duplicate, lower score
                    {"title": "Article C", "similarity": 0.8},
                ]
            else:
                return [{"title": "Article B", "similarity": 0.75}]  # dup, higher score

        results = multi_query_retrieve(
            claude_client, _semantic_search, track_fn, "What is gravity?"
        )

        # Dedup keeps highest similarity: A=max(0.9,0.85)=0.9, B=max(0.7,0.75)=0.75, C=0.8
        assert len(results) == 3
        assert results[0]["title"] == "Article A"
        assert results[0]["similarity"] == 0.9
        # sorted descending: A(0.9), C(0.8), B(0.75)
        assert results[1]["title"] == "Article C"
        assert results[2]["title"] == "Article B"
        assert results[2]["similarity"] == 0.75

    def test_falls_back_on_api_timeout(self) -> None:
        claude_client = MagicMock()
        claude_client.messages.create.side_effect = APITimeoutError(request=MagicMock())
        track_fn = MagicMock()

        search_results = [{"title": "Fallback", "similarity": 0.6}]

        results = multi_query_retrieve(
            claude_client, lambda q, top_k=5: search_results, track_fn, "question"
        )

        # Only original query is used (no alternatives generated)
        assert len(results) == 1
        assert results[0]["title"] == "Fallback"

    def test_falls_back_on_connection_error(self) -> None:
        import httpx

        claude_client = MagicMock()
        claude_client.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )
        track_fn = MagicMock()

        results = multi_query_retrieve(
            claude_client, lambda q, top_k=5: [{"title": "X", "similarity": 0.5}], track_fn, "q"
        )

        assert len(results) == 1

    def test_falls_back_on_rate_limit(self) -> None:
        claude_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        claude_client.messages.create.side_effect = APIStatusError(
            message="rate limited",
            response=mock_response,
            body={"error": {"message": "rate limited"}},
        )
        track_fn = MagicMock()

        results = multi_query_retrieve(
            claude_client, lambda q, top_k=5: [{"title": "Y", "similarity": 0.4}], track_fn, "q"
        )

        assert len(results) == 1

    def test_falls_back_on_invalid_json(self) -> None:
        content_block = MagicMock()
        content_block.text = "not valid json"
        response = MagicMock()
        response.content = [content_block]
        response.usage = MagicMock(input_tokens=5, output_tokens=5)

        claude_client = MagicMock()
        claude_client.messages.create.return_value = response
        track_fn = MagicMock()

        results = multi_query_retrieve(
            claude_client, lambda q, top_k=5: [{"title": "Z", "similarity": 0.3}], track_fn, "q"
        )

        assert len(results) == 1

    def test_skips_results_without_title(self) -> None:
        claude_client = MagicMock()
        claude_client.messages.create.return_value = _mock_haiku_response([])
        track_fn = MagicMock()

        def _search(q, top_k=5):
            return [
                {"title": "", "similarity": 0.9},
                {"similarity": 0.8},  # no title key at all
                {"title": "Valid", "similarity": 0.7},
            ]

        results = multi_query_retrieve(claude_client, _search, track_fn, "question")

        assert len(results) == 1
        assert results[0]["title"] == "Valid"

    def test_clamps_max_results(self) -> None:
        claude_client = MagicMock()
        claude_client.messages.create.return_value = _mock_haiku_response([])
        track_fn = MagicMock()

        calls = []

        def _search(q, top_k=5):
            calls.append(top_k)
            return []

        # max_results=0 should be clamped to 1
        multi_query_retrieve(claude_client, _search, track_fn, "q", max_results=0)
        assert calls[-1] == 1

        # max_results=100 should be clamped to 20
        multi_query_retrieve(claude_client, _search, track_fn, "q", max_results=100)
        assert calls[-1] == 20

    def test_handles_semantic_search_error(self) -> None:
        claude_client = MagicMock()
        claude_client.messages.create.return_value = _mock_haiku_response([])
        track_fn = MagicMock()

        def _search(q, top_k=5):
            raise RuntimeError("embedding service down")

        results = multi_query_retrieve(claude_client, _search, track_fn, "question")

        assert results == []


# ===================================================================
# 4. vector_primary_retrieve
# ===================================================================


class TestVectorPrimaryRetrieve:
    """vector_primary_retrieve: vector search with optional cross-encoder reranking."""

    def test_happy_path_without_cross_encoder(self) -> None:
        def _search(q, top_k=5):
            return [
                {"title": "Relativity", "similarity": 0.9, "content": "Einstein's theory."},
                {"title": "Gravity", "similarity": 0.7, "content": "Force of attraction."},
            ]

        result, max_sim = vector_primary_retrieve(
            semantic_search_fn=_search,
            multi_query_retrieve_fn=MagicMock(),
            cross_encoder=None,
            enable_multi_query=False,
            question="What is relativity?",
            max_results=5,
        )

        assert result is not None
        assert max_sim == 0.9
        assert "Relativity" in result["sources"]
        assert "Gravity" in result["sources"]
        assert len(result["facts"]) == 2
        assert result["entities"] == []

    def test_with_cross_encoder(self) -> None:
        def _search(q, top_k=5):
            return [
                {"title": "A", "similarity": 0.6, "content": "Content A."},
                {"title": "B", "similarity": 0.9, "content": "Content B."},
            ]

        cross_encoder = MagicMock()
        # Reranker reverses order
        cross_encoder.rerank.return_value = [
            {"title": "B", "similarity": 0.95, "content": "Content B."},
        ]

        result, max_sim = vector_primary_retrieve(
            semantic_search_fn=_search,
            multi_query_retrieve_fn=MagicMock(),
            cross_encoder=cross_encoder,
            enable_multi_query=False,
            question="What is B?",
            max_results=1,
        )

        assert result is not None
        assert max_sim == 0.95
        assert result["sources"] == ["B"]
        # candidate_k should be min(1*2, 40)=2 when cross_encoder is not None
        cross_encoder.rerank.assert_called_once()

    def test_with_multi_query_enabled(self) -> None:
        multi_query_fn = MagicMock(
            return_value=[
                {"title": "MQ", "similarity": 0.85, "content": "Multi-query result."},
            ]
        )
        semantic_fn = MagicMock()

        result, max_sim = vector_primary_retrieve(
            semantic_search_fn=semantic_fn,
            multi_query_retrieve_fn=multi_query_fn,
            cross_encoder=None,
            enable_multi_query=True,
            question="What is MQ?",
            max_results=5,
        )

        assert result is not None
        assert max_sim == 0.85
        multi_query_fn.assert_called_once()
        semantic_fn.assert_not_called()

    def test_empty_results_returns_none(self) -> None:
        result, max_sim = vector_primary_retrieve(
            semantic_search_fn=lambda q, top_k=5: [],
            multi_query_retrieve_fn=MagicMock(),
            cross_encoder=None,
            enable_multi_query=False,
            question="anything",
            max_results=5,
        )

        assert result is None
        assert max_sim == 0.0

    def test_runtime_error_returns_none(self) -> None:
        def _failing_search(q, top_k=5):
            raise RuntimeError("embedding model unavailable")

        result, max_sim = vector_primary_retrieve(
            semantic_search_fn=_failing_search,
            multi_query_retrieve_fn=MagicMock(),
            cross_encoder=None,
            enable_multi_query=False,
            question="anything",
            max_results=5,
        )

        assert result is None
        assert max_sim == 0.0

    def test_truncates_long_content(self) -> None:
        long_content = "x" * 1000
        result, _ = vector_primary_retrieve(
            semantic_search_fn=lambda q, top_k=5: [
                {"title": "Big", "similarity": 0.7, "content": long_content}
            ],
            multi_query_retrieve_fn=MagicMock(),
            cross_encoder=None,
            enable_multi_query=False,
            question="anything",
            max_results=5,
        )

        assert result is not None
        # Content is truncated to 500 chars in facts
        assert len(result["facts"][0]) <= 500 + len("[Big] ")


# ===================================================================
# 5. hybrid_retrieve
# ===================================================================


class TestHybridRetrieve:
    """hybrid_retrieve: combines vector, graph, and keyword signals."""

    def test_combines_all_three_signals(self, mock_conn: MagicMock) -> None:
        vector_results = [{"title": "Quantum Mechanics", "similarity": 0.9}]

        graph_df = pd.DataFrame({"title": ["String Theory"]})
        keyword_df = pd.DataFrame({"title": ["Quantum Mechanics"]})
        facts_df = pd.DataFrame({"content": ["Energy is quantized"]})

        def _side_effect(query, params=None):
            if "LINKS_TO" in query:
                return _mock_execute_result(graph_df)
            elif "CONTAINS" in query:
                return _mock_execute_result(keyword_df)
            elif "HAS_FACT" in query:
                return _mock_execute_result(facts_df)
            return _mock_execute_result(pd.DataFrame())

        mock_conn.execute.side_effect = _side_effect

        result = hybrid_retrieve(
            mock_conn,
            lambda q, top_k=10: vector_results,
            STOP_WORDS,
            "What is quantum mechanics?",
        )

        assert "Quantum Mechanics" in result["sources"]
        assert isinstance(result["facts"], list)
        assert isinstance(result["raw"], list)

    def test_handles_vector_search_failure(self, mock_conn: MagicMock) -> None:
        def _failing_search(q, top_k=10):
            raise RuntimeError("embedding failed")

        keyword_df = pd.DataFrame({"title": ["Relativity"]})
        facts_df = pd.DataFrame({"content": ["E=mc2"]})

        def _side_effect(query, params=None):
            if "CONTAINS" in query:
                return _mock_execute_result(keyword_df)
            elif "HAS_FACT" in query:
                return _mock_execute_result(facts_df)
            return _mock_execute_result(pd.DataFrame())

        mock_conn.execute.side_effect = _side_effect

        result = hybrid_retrieve(mock_conn, _failing_search, STOP_WORDS, "relativity theory")

        assert isinstance(result, dict)
        assert isinstance(result["sources"], list)

    def test_all_db_failures_returns_empty(self, mock_conn: MagicMock) -> None:
        mock_conn.execute.side_effect = RuntimeError("DB down")

        result = hybrid_retrieve(mock_conn, lambda q, top_k=10: [], STOP_WORDS, "anything")

        assert result["sources"] == []
        assert result["facts"] == []

    def test_precomputed_vector_avoids_search_call(self, mock_conn: MagicMock) -> None:
        """When _precomputed_vector is provided, semantic_search_fn is not called."""
        search_fn = MagicMock()
        precomputed = [{"title": "Pre", "similarity": 0.8}]

        # DB calls for graph/keyword/facts
        mock_conn.execute.side_effect = RuntimeError("DB down")

        result = hybrid_retrieve(
            mock_conn,
            search_fn,
            STOP_WORDS,
            "question",
            _precomputed_vector=precomputed,
        )

        search_fn.assert_not_called()
        assert "Pre" in result["sources"]

    def test_keyword_weight_zero_excludes_keyword_signal(self, mock_conn: MagicMock) -> None:
        mock_conn.execute.return_value = _mock_execute_result(pd.DataFrame())

        result = hybrid_retrieve(
            mock_conn,
            lambda q, top_k=10: [{"title": "Vec", "similarity": 0.6}],
            STOP_WORDS,
            "quantum physics",
            keyword_weight=0.0,
            vector_weight=1.0,
            graph_weight=0.0,
        )

        assert "Vec" in result["sources"]


# ===================================================================
# 6. score_section_quality
# ===================================================================


class TestScoreSectionQuality:
    """score_section_quality: scores section quality for synthesis context."""

    def test_short_content_returns_zero(self) -> None:
        short = " ".join(["word"] * 10)
        assert score_section_quality(short, "What is this?", STOP_WORDS) == 0.0

    def test_exactly_19_words_returns_zero(self) -> None:
        text = " ".join(["word"] * 19)
        assert score_section_quality(text, "question", STOP_WORDS) == 0.0

    def test_20_words_returns_positive(self) -> None:
        text = " ".join(["word"] * 20)
        score = score_section_quality(text, "question", STOP_WORDS)
        assert score > 0.0

    def test_longer_content_higher_score(self) -> None:
        short = " ".join(["word"] * 25)
        long = " ".join(["word"] * 150)
        short_score = score_section_quality(short, "question", STOP_WORDS)
        long_score = score_section_quality(long, "question", STOP_WORDS)
        assert long_score > short_score

    def test_keyword_overlap_increases_score(self) -> None:
        # Same length content, but one has keyword overlap
        base = " ".join(["filler"] * 25)
        overlap = " ".join(["filler"] * 20 + ["quantum", "mechanics", "physics", "energy", "wave"])
        base_score = score_section_quality(base, "quantum mechanics", STOP_WORDS)
        overlap_score = score_section_quality(overlap, "quantum mechanics", STOP_WORDS)
        assert overlap_score > base_score

    def test_score_capped_at_one(self) -> None:
        huge = " ".join(["word"] * 1000)
        score = score_section_quality(huge, "word", STOP_WORDS)
        assert score <= 1.0

    def test_precomputed_keywords(self) -> None:
        text = " ".join(["quantum", "energy"] + ["filler"] * 25)
        q_keywords = frozenset({"quantum", "energy"})
        score = score_section_quality(text, "ignored question", STOP_WORDS, _q_keywords=q_keywords)
        assert score > 0.0

    def test_empty_question_keywords(self) -> None:
        """When all question words are stop words, keyword_score is 0."""
        text = " ".join(["word"] * 30)
        # All stop words → question_keywords is empty
        score = score_section_quality(text, "the is a an", STOP_WORDS)
        # Only length score contributes
        assert score > 0.0


# ===================================================================
# 7. fetch_source_text
# ===================================================================


class TestFetchSourceText:
    """fetch_source_text: fetches section text, falls back to article content."""

    def test_returns_sections_for_articles(self, mock_conn: MagicMock) -> None:
        df = pd.DataFrame(
            {
                "title": ["Quantum", "Quantum"],
                "content": ["Lead section text here.", "Second section text here."],
            }
        )
        mock_conn.execute.return_value = _mock_execute_result(df)

        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            text = fetch_source_text(
                mock_conn,
                score_section_quality_fn=lambda c, q, _q_keywords=None: 1.0,
                stop_words=STOP_WORDS,
                max_article_chars=3000,
                content_quality_threshold=0.3,
                source_titles=["Quantum"],
            )

        assert "## Quantum" in text
        assert "Lead section text here." in text

    def test_empty_titles_returns_empty(self, mock_conn: MagicMock) -> None:
        result = fetch_source_text(
            mock_conn,
            score_section_quality_fn=MagicMock(),
            stop_words=STOP_WORDS,
            max_article_chars=3000,
            content_quality_threshold=0.3,
            source_titles=[],
        )

        assert result == ""

    def test_falls_back_to_article_content(self, mock_conn: MagicMock) -> None:
        """When section query returns empty, falls back to article.content."""
        empty_df = pd.DataFrame()
        content_df = pd.DataFrame(
            {
                "title": ["Relativity"],
                "content": ["Einstein developed the theory."],
            }
        )
        mock_conn.execute.side_effect = [
            _mock_execute_result(empty_df),
            _mock_execute_result(content_df),
        ]

        text = fetch_source_text(
            mock_conn,
            score_section_quality_fn=MagicMock(),
            stop_words=STOP_WORDS,
            max_article_chars=3000,
            content_quality_threshold=0.3,
            source_titles=["Relativity"],
        )

        assert "## Relativity" in text
        assert "Einstein developed" in text

    def test_db_error_returns_empty(self, mock_conn: MagicMock) -> None:
        mock_conn.execute.side_effect = RuntimeError("DB down")

        text = fetch_source_text(
            mock_conn,
            score_section_quality_fn=MagicMock(),
            stop_words=STOP_WORDS,
            max_article_chars=3000,
            content_quality_threshold=0.3,
            source_titles=["Some Article"],
        )

        assert text == ""

    def test_truncates_long_content(self, mock_conn: MagicMock) -> None:
        long_content = "x " * 2000  # about 4000 chars
        df = pd.DataFrame({"title": ["Big"], "content": [long_content]})
        mock_conn.execute.return_value = _mock_execute_result(df)

        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            text = fetch_source_text(
                mock_conn,
                score_section_quality_fn=lambda c, q, _q_keywords=None: 1.0,
                stop_words=STOP_WORDS,
                max_article_chars=500,
                content_quality_threshold=0.3,
                source_titles=["Big"],
            )

        assert "..." in text

    def test_quality_filter_excludes_low_quality_sections(self, mock_conn: MagicMock) -> None:
        """Sections below quality threshold are filtered out."""
        df = pd.DataFrame(
            {
                "title": ["Article", "Article"],
                "content": ["High quality section content.", "Low quality stub."],
            }
        )
        mock_conn.execute.return_value = _mock_execute_result(df)

        def _quality_fn(content, question=None, _q_keywords=None):
            if "High quality" in content:
                return 0.8
            return 0.1  # below threshold

        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            text = fetch_source_text(
                mock_conn,
                score_section_quality_fn=_quality_fn,
                stop_words=STOP_WORDS,
                max_article_chars=3000,
                content_quality_threshold=0.5,
                source_titles=["Article"],
                question="test question",
            )

        assert "High quality" in text
        assert "Low quality" not in text

    def test_no_quality_filter_when_no_question(self, mock_conn: MagicMock) -> None:
        """When question is None, quality filter is not applied."""
        df = pd.DataFrame(
            {
                "title": ["Article"],
                "content": ["Some section content here."],
            }
        )
        mock_conn.execute.return_value = _mock_execute_result(df)

        quality_fn = MagicMock(return_value=0.0)  # Would be below any threshold

        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            text = fetch_source_text(
                mock_conn,
                score_section_quality_fn=quality_fn,
                stop_words=STOP_WORDS,
                max_article_chars=3000,
                content_quality_threshold=0.5,
                source_titles=["Article"],
                question=None,  # No question → no quality filter
            )

        # quality_fn should not be called because q_keywords is None when question is None
        quality_fn.assert_not_called()
        assert "Some section content here." in text

    def test_respects_max_articles(self, mock_conn: MagicMock) -> None:
        """Only first max_articles titles are processed."""
        titles = [f"Article {i}" for i in range(10)]
        df = pd.DataFrame(
            {
                "title": titles[:2],
                "content": [f"Content for article {i}" for i in range(2)],
            }
        )
        mock_conn.execute.return_value = _mock_execute_result(df)

        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            text = fetch_source_text(
                mock_conn,
                score_section_quality_fn=lambda c, q, _q_keywords=None: 1.0,
                stop_words=STOP_WORDS,
                max_article_chars=3000,
                content_quality_threshold=0.3,
                source_titles=titles,
                max_articles=2,
            )

        assert "Article 0" in text
        assert "Article 1" in text
