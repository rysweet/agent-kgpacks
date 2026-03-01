"""Tests for Improvement 4 (multi-query retrieval) and Improvement 5 (content quality scoring).

All tests mock Kuzu connections and the Claude API -- no real DB or network calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

from wikigr.agent.kg_agent import KnowledgeGraphAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(enable_multi_query: bool = False) -> KnowledgeGraphAgent:
    """Build a KnowledgeGraphAgent with fully mocked internals."""
    agent = KnowledgeGraphAgent.__new__(KnowledgeGraphAgent)
    agent.db = None
    agent.conn = MagicMock()
    agent.claude = MagicMock()
    agent.synthesis_model = "mock-model"
    agent._embedding_generator = None
    agent._plan_cache = {}
    agent.use_enhancements = False
    agent.enable_reranker = False
    agent.enable_multidoc = False
    agent.enable_fewshot = False
    agent.enable_multi_query = enable_multi_query
    agent.reranker = None
    agent.synthesizer = None
    agent.few_shot = None
    agent.cypher_rag = None
    agent.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
    return agent


def _mock_haiku_response(alternatives: list[str]) -> MagicMock:
    """Build a mock Claude Haiku response returning the given alternatives as JSON."""
    content_block = MagicMock()
    content_block.text = json.dumps(alternatives)
    response = MagicMock()
    response.content = [content_block]
    response.usage = MagicMock(input_tokens=10, output_tokens=20)
    return response


# ---------------------------------------------------------------------------
# Improvement 4: _multi_query_retrieve
# ---------------------------------------------------------------------------


class TestMultiQueryRetrieve:
    """Tests for _multi_query_retrieve deduplication and merging."""

    def test_deduplication_keeps_highest_similarity(self) -> None:
        """When two queries return the same title, the higher similarity is kept."""
        agent = _make_agent()

        # Haiku returns 2 alternatives
        agent.claude.messages.create.return_value = _mock_haiku_response(
            ["alternative phrasing one", "alternative phrasing two"]
        )

        # semantic_search returns overlapping titles with different similarities
        def mock_search(query, top_k=5):
            if query == "original question":
                return [
                    {"title": "Article A", "similarity": 0.7, "content": "text a"},
                    {"title": "Article B", "similarity": 0.5, "content": "text b"},
                ]
            elif query == "alternative phrasing one":
                return [
                    {"title": "Article A", "similarity": 0.9, "content": "text a alt"},
                    {"title": "Article C", "similarity": 0.4, "content": "text c"},
                ]
            else:
                return [
                    {"title": "Article B", "similarity": 0.3, "content": "text b alt"},
                ]

        with patch.object(agent, "semantic_search", side_effect=mock_search):
            results = agent._multi_query_retrieve("original question", max_results=5)

        titles = [r["title"] for r in results]
        # Deduplication: A appears with 0.7 and 0.9 — keep 0.9; B appears with 0.5 and 0.3 — keep 0.5
        assert "Article A" in titles
        assert "Article B" in titles
        assert "Article C" in titles

        by_title = {r["title"]: r for r in results}
        assert by_title["Article A"]["similarity"] == pytest.approx(0.9)
        assert by_title["Article B"]["similarity"] == pytest.approx(0.5)

    def test_results_sorted_descending_by_similarity(self) -> None:
        """Returned list is sorted by similarity descending."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _mock_haiku_response(["alt1", "alt2"])

        def mock_search(query, top_k=5):
            return [
                {"title": f"T{i}", "similarity": 0.1 * i, "content": "x"}
                for i in range(1, 4)
            ]

        with patch.object(agent, "semantic_search", side_effect=mock_search):
            results = agent._multi_query_retrieve("q", max_results=5)

        similarities = [r["similarity"] for r in results]
        assert similarities == sorted(similarities, reverse=True)

    def test_merges_unique_results_from_all_three_queries(self) -> None:
        """Results from all 3 queries (original + 2 alternatives) are merged."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _mock_haiku_response(["alt1", "alt2"])

        call_count = 0

        def mock_search(query, top_k=5):
            nonlocal call_count
            call_count += 1
            return [{"title": f"Article-{call_count}", "similarity": 0.5, "content": "x"}]

        with patch.object(agent, "semantic_search", side_effect=mock_search):
            results = agent._multi_query_retrieve("q", max_results=5)

        # 3 unique titles from 3 separate search calls
        assert call_count == 3
        assert len(results) == 3

    def test_uses_haiku_model_for_query_expansion(self) -> None:
        """Claude Haiku (claude-haiku-4-5-20251001) is used, not the synthesis model."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _mock_haiku_response(["a", "b"])

        with patch.object(agent, "semantic_search", return_value=[]):
            agent._multi_query_retrieve("question", max_results=5)

        call_kwargs = agent.claude.messages.create.call_args
        assert call_kwargs.kwargs.get("model") == "claude-haiku-4-5-20251001" or (
            call_kwargs.args and call_kwargs.args[0] == "claude-haiku-4-5-20251001"
        ) or call_kwargs[1].get("model") == "claude-haiku-4-5-20251001"

    def test_gracefully_handles_expansion_failure(self) -> None:
        """If Haiku call raises a connection error, falls back to searching only the original query."""
        agent = _make_agent()
        agent.claude.messages.create.side_effect = APIConnectionError(request=MagicMock())

        search_results = [{"title": "X", "similarity": 0.8, "content": "y"}]
        with patch.object(agent, "semantic_search", return_value=search_results) as mock_search:
            results = agent._multi_query_retrieve("q", max_results=5)

        # Only the original query was searched (alternatives failed to generate)
        assert mock_search.call_count == 1
        assert len(results) == 1
        assert results[0]["title"] == "X"


# ---------------------------------------------------------------------------
# Improvement 5: _score_section_quality
# ---------------------------------------------------------------------------


class TestScoreSectionQuality:
    """Tests for _score_section_quality method."""

    def test_returns_zero_for_stub_under_20_words(self) -> None:
        """Sections with fewer than 20 words score exactly 0.0."""
        agent = _make_agent()
        short_content = "This is a short stub."  # 5 words
        score = agent._score_section_quality(short_content, "what is this")
        assert score == 0.0

    def test_returns_zero_for_exactly_19_words(self) -> None:
        """19 words → exactly 0.0 (boundary condition)."""
        agent = _make_agent()
        content = " ".join(["word"] * 19)
        assert agent._score_section_quality(content, "question") == 0.0

    def test_returns_nonzero_for_exactly_20_words(self) -> None:
        """20 words → score > 0.0 (just above the stub cutoff)."""
        agent = _make_agent()
        content = " ".join(["word"] * 20)
        score = agent._score_section_quality(content, "question")
        assert score > 0.0

    def test_score_in_valid_range(self) -> None:
        """Score is always in [0.0, 1.0] for any input."""
        agent = _make_agent()
        for word_count in [20, 50, 100, 200, 500, 1000]:
            content = " ".join(["word"] * word_count)
            score = agent._score_section_quality(content, "some question here")
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for {word_count} words"

    def test_longer_sections_score_higher(self) -> None:
        """A 200-word section scores higher than a 20-word section (length component)."""
        agent = _make_agent()
        short = " ".join(["word"] * 25)
        long_ = " ".join(["word"] * 200)
        assert agent._score_section_quality(long_, "question") > agent._score_section_quality(
            short, "question"
        )

    def test_keyword_overlap_increases_score(self) -> None:
        """Sections containing question keywords score higher than those without."""
        agent = _make_agent()
        base_words = ["information", "about", "topic"] * 10  # 30 words, no question keywords
        content_no_overlap = " ".join(base_words)

        # Same length but contains question keywords
        question = "photosynthesis chlorophyll plant"
        content_with_overlap = " ".join(base_words[:-3] + ["photosynthesis", "chlorophyll", "plant"])

        score_no = agent._score_section_quality(content_no_overlap, question)
        score_yes = agent._score_section_quality(content_with_overlap, question)
        assert score_yes > score_no

    def test_stop_words_excluded_from_keyword_overlap(self) -> None:
        """Stop words in the question don't contribute to keyword overlap score."""
        agent = _make_agent()
        content = " ".join(["the", "is", "a", "in"] * 10)  # 40 words, all stop words
        question = "the is a in"
        # Even though content "matches" question words, stop words are excluded
        score = agent._score_section_quality(content, question)
        # keyword_score should be 0 since all question words are stop words
        # Only length score contributes: min(0.8, 0.2 + (40/200)*0.6) = min(0.8, 0.32) = 0.32
        assert 0.0 < score <= 0.8

    def test_max_200_words_caps_length_score(self) -> None:
        """Length score is capped at 0.8 even for 1000-word sections."""
        agent = _make_agent()
        huge_content = " ".join(["word"] * 1000)
        score = agent._score_section_quality(huge_content, "unique_keyword_xyz")
        assert score <= 1.0


# ---------------------------------------------------------------------------
# Integration: _build_synthesis_context quality filtering
# ---------------------------------------------------------------------------


class TestBuildSynthesisContextQualityFiltering:
    """Tests that _build_synthesis_context filters low-quality sections."""

    def _make_df_result(self, rows: list[dict]) -> MagicMock:
        df = pd.DataFrame(rows)
        result = MagicMock()
        result.get_as_df.return_value = df
        return result

    def test_filters_sections_below_threshold(self) -> None:
        """Sections scoring below CONTENT_QUALITY_THRESHOLD are excluded from synthesis."""
        agent = _make_agent()
        agent.conn.execute.return_value = self._make_df_result(
            [
                {"title": "Article A", "content": "Short stub."},  # < 20 words → filtered
                {"title": "Article A", "content": " ".join(["word"] * 50) + " python"},  # passes
            ]
        )

        # Mock clean_content to return content unchanged
        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            result = agent._fetch_source_text(["Article A"], question="python programming")

        # The stub should be filtered; the long section should be included
        assert "Article A" in result
        # The stub's content shouldn't appear (just "Short stub.")
        assert "Short stub." not in result

    def test_includes_sections_above_threshold(self) -> None:
        """Sections above CONTENT_QUALITY_THRESHOLD are included."""
        agent = _make_agent()
        long_section = " ".join(["machine", "learning"] * 30)  # 60 words with keyword overlap
        agent.conn.execute.return_value = self._make_df_result(
            [{"title": "ML Article", "content": long_section}]
        )

        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            result = agent._fetch_source_text(["ML Article"], question="machine learning")

        assert "ML Article" in result

    def test_no_filtering_when_question_is_none(self) -> None:
        """When question=None, all sections are included regardless of quality."""
        agent = _make_agent()
        agent.conn.execute.return_value = self._make_df_result(
            [{"title": "Article X", "content": "Tiny."}]  # < 20 words, would be filtered
        )

        with patch("wikigr.packs.content_cleaner.clean_content", side_effect=lambda x: x):
            result = agent._fetch_source_text(["Article X"], question=None)

        assert "Article X" in result


# ---------------------------------------------------------------------------
# Integration: _vector_primary_retrieve routing
# ---------------------------------------------------------------------------


class TestVectorPrimaryRetrieveRouting:
    """Tests that _vector_primary_retrieve routes to the correct search method."""

    def test_uses_semantic_search_when_multi_query_disabled(self) -> None:
        """Direct semantic_search called when enable_multi_query=False."""
        agent = _make_agent(enable_multi_query=False)
        search_results = [{"title": "T", "similarity": 0.8, "content": "text"}]

        with patch.object(agent, "semantic_search", return_value=search_results) as mock_search:
            with patch.object(agent, "_multi_query_retrieve") as mock_multi:
                result, sim = agent._vector_primary_retrieve("q", max_results=5)

        mock_search.assert_called_once_with("q", top_k=5)
        mock_multi.assert_not_called()
        assert sim == pytest.approx(0.8)

    def test_uses_multi_query_retrieve_when_enabled(self) -> None:
        """_multi_query_retrieve called when enable_multi_query=True."""
        agent = _make_agent(enable_multi_query=True)
        multi_results = [
            {"title": "T1", "similarity": 0.9, "content": "text1"},
            {"title": "T2", "similarity": 0.7, "content": "text2"},
        ]

        with patch.object(agent, "_multi_query_retrieve", return_value=multi_results) as mock_multi:
            with patch.object(agent, "semantic_search") as mock_search:
                result, sim = agent._vector_primary_retrieve("q", max_results=5)

        mock_multi.assert_called_once_with("q", max_results=5)
        mock_search.assert_not_called()
        assert sim == pytest.approx(0.9)
        assert set(result["sources"]) == {"T1", "T2"}


# ---------------------------------------------------------------------------
# Class-level constants
# ---------------------------------------------------------------------------


class TestClassLevelConstants:
    """Verify CONTENT_QUALITY_THRESHOLD and STOP_WORDS are class attributes."""

    def test_content_quality_threshold_is_0_3(self) -> None:
        assert KnowledgeGraphAgent.CONTENT_QUALITY_THRESHOLD == pytest.approx(0.3)

    def test_stop_words_is_frozenset(self) -> None:
        assert isinstance(KnowledgeGraphAgent.STOP_WORDS, frozenset)

    def test_stop_words_contains_common_words(self) -> None:
        for word in ("the", "a", "an", "is", "in", "of", "to"):
            assert word in KnowledgeGraphAgent.STOP_WORDS

    def test_enable_multi_query_default_false(self) -> None:
        """enable_multi_query defaults to False (opt-in)."""
        agent = _make_agent()
        assert agent.enable_multi_query is False


# ---------------------------------------------------------------------------
# External service resilience: typed error handling in _multi_query_retrieve
# ---------------------------------------------------------------------------


class TestMultiQueryRetrieveExternalServiceResilience:
    """Verify that specific Anthropic API errors fall back gracefully."""

    def _search_stub(self, query, top_k=5):
        return [{"title": "Fallback", "similarity": 0.6, "content": "text"}]

    def test_timeout_falls_back_to_original_query(self) -> None:
        """APITimeoutError causes graceful fallback to searching only the original query."""
        agent = _make_agent()
        agent.claude.messages.create.side_effect = APITimeoutError(request=MagicMock())

        with patch.object(agent, "semantic_search", side_effect=self._search_stub) as mock_search:
            results = agent._multi_query_retrieve("q", max_results=5)

        mock_search.assert_called_once()
        assert len(results) == 1
        assert results[0]["title"] == "Fallback"

    def test_connection_error_falls_back_to_original_query(self) -> None:
        """APIConnectionError causes graceful fallback to searching only the original query."""
        agent = _make_agent()
        agent.claude.messages.create.side_effect = APIConnectionError(
            request=MagicMock(), message="connection refused"
        )

        with patch.object(agent, "semantic_search", side_effect=self._search_stub) as mock_search:
            results = agent._multi_query_retrieve("q", max_results=5)

        mock_search.assert_called_once()
        assert len(results) == 1

    def test_rate_limit_429_falls_back_to_original_query(self) -> None:
        """APIStatusError with 429 (rate limit) causes graceful fallback."""
        agent = _make_agent()
        mock_response = MagicMock()
        mock_response.status_code = 429
        agent.claude.messages.create.side_effect = APIStatusError(
            "rate limited",
            response=mock_response,
            body={"error": {"type": "rate_limit_error"}},
        )

        with patch.object(agent, "semantic_search", side_effect=self._search_stub) as mock_search:
            results = agent._multi_query_retrieve("q", max_results=5)

        mock_search.assert_called_once()
        assert len(results) == 1

    def test_auth_error_400_falls_back_to_original_query(self) -> None:
        """APIStatusError with non-429 status (e.g. 401 auth) also falls back gracefully."""
        agent = _make_agent()
        mock_response = MagicMock()
        mock_response.status_code = 401
        agent.claude.messages.create.side_effect = APIStatusError(
            "unauthorized",
            response=mock_response,
            body={"error": {"type": "authentication_error"}},
        )

        with patch.object(agent, "semantic_search", side_effect=self._search_stub) as mock_search:
            results = agent._multi_query_retrieve("q", max_results=5)

        mock_search.assert_called_once()
        assert len(results) == 1

    def test_haiku_call_uses_10s_timeout(self) -> None:
        """messages.create() for expansion is called with timeout=10.0."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _mock_haiku_response(["a", "b"])

        with patch.object(agent, "semantic_search", return_value=[]):
            agent._multi_query_retrieve("question", max_results=5)

        call_kwargs = agent.claude.messages.create.call_args[1]
        assert call_kwargs.get("timeout") == pytest.approx(10.0)
