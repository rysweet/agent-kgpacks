"""Contract tests for exception-handling refactoring (docs/design/exception-handling.md).

Written TDD-first: these tests specify the behaviour that CHANGED during the
exception-handling refactoring.  Each class documents what the OLD code did (wrong)
and what the NEW contract requires.

Tests that would FAIL against the old code:
  A1. _identify_seed_articles raised → graph_query silently fell back to word-splitting.
      New: errors propagate; _fallback_seed_extraction method must not exist.
  C.  except Exception blocks swallowed AttributeError / TypeError as programming bugs.
      New: only RuntimeError (Kuzu) is caught; AttributeError propagates.

All tests use fully-mocked agent instances — no real DB or API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

from wikigr.agent.kg_agent import KnowledgeGraphAgent

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _make_agent() -> KnowledgeGraphAgent:
    """Build a KnowledgeGraphAgent with fully mocked internals."""
    agent = KnowledgeGraphAgent.__new__(KnowledgeGraphAgent)
    agent.db = None
    agent.conn = MagicMock()
    agent.claude = MagicMock()
    agent.synthesis_model = "mock-model"
    agent._embedding_generator = None
    agent._plan_cache = {}
    agent.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
    agent.use_enhancements = False
    agent.enable_reranker = True
    agent.enable_multidoc = True
    agent.enable_fewshot = True
    agent.enable_multi_query = False
    agent.reranker = None
    agent.synthesizer = None
    agent.few_shot = None
    agent.cross_encoder = None
    return agent


def _make_response(text: str) -> MagicMock:
    """Build a mock Claude API response with the given text content."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(input_tokens=20, output_tokens=10)
    return resp


# ===========================================================================
# A1 — _identify_seed_articles: no silent word-split fallback
# ===========================================================================


class TestIdentifySeedArticlesContract:
    """_identify_seed_articles MUST raise on API failure — no word-split fallback.

    OLD behaviour (removed):
      graph_query() caught errors from _identify_seed_articles and called
      _fallback_seed_extraction(question), which split the question into content
      words as seed titles (silent semantic degradation producing garbage results).

    NEW contract (design/exception-handling.md §A1):
      - APIConnectionError / APIStatusError / APITimeoutError propagate unchanged.
      - ValueError is raised on empty or unparseable LLM response.
      - _fallback_seed_extraction and _FALLBACK_STOP_WORDS must not exist.

    Each test would FAIL against the old code because the old code caught these
    errors and returned word-split seeds instead of raising.
    """

    def test_api_connection_error_propagates(self) -> None:
        """APIConnectionError from Claude propagates from _identify_seed_articles.

        OLD: caught → _fallback_seed_extraction called → ["What", "quantum", ...] returned.
        NEW: APIConnectionError re-raised immediately.
        """
        agent = _make_agent()
        agent.claude.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )

        with pytest.raises(APIConnectionError):
            agent._identify_seed_articles("What is quantum mechanics?")

    def test_api_status_error_propagates(self) -> None:
        """APIStatusError (e.g. 429 rate-limit) propagates from _identify_seed_articles."""
        agent = _make_agent()
        mock_req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        mock_resp = httpx.Response(429, request=mock_req, text="Too Many Requests")
        agent.claude.messages.create.side_effect = APIStatusError(
            "rate limited", response=mock_resp, body=None
        )

        with pytest.raises(APIStatusError):
            agent._identify_seed_articles("Tell me about general relativity")

    def test_api_timeout_error_propagates(self) -> None:
        """APITimeoutError from Claude propagates from _identify_seed_articles."""
        agent = _make_agent()
        agent.claude.messages.create.side_effect = APITimeoutError(
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        )

        with pytest.raises(APITimeoutError):
            agent._identify_seed_articles("Explain neural networks")

    def test_empty_api_response_raises_value_error(self) -> None:
        """Empty content list from Claude raises ValueError (not a silent empty list).

        OLD: would have raised, which _graph_query caught and word-split instead.
        NEW: ValueError propagates to the caller.
        """
        agent = _make_agent()
        mock_resp = MagicMock()
        mock_resp.content = []
        mock_resp.usage = MagicMock(input_tokens=10, output_tokens=0)
        agent.claude.messages.create.return_value = mock_resp

        with pytest.raises(ValueError, match="Empty response"):
            agent._identify_seed_articles("What causes earthquakes?")

    def test_non_json_response_raises_value_error(self) -> None:
        """Non-JSON text in Claude response raises ValueError."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _make_response("Sorry, I cannot answer that.")

        with pytest.raises(ValueError):
            agent._identify_seed_articles("What is gravity?")

    def test_json_object_not_list_raises_value_error(self) -> None:
        """JSON response that is a dict (not list) raises ValueError."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _make_response(
            '{"article": "Quantum mechanics"}'  # dict, not list
        )

        with pytest.raises(ValueError):
            agent._identify_seed_articles("What is quantum mechanics?")

    def test_json_list_of_integers_raises_value_error(self) -> None:
        """JSON list containing non-string elements raises ValueError."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _make_response("[1, 2, 3]")

        with pytest.raises(ValueError):
            agent._identify_seed_articles("What is quantum mechanics?")

    def test_valid_response_returns_titles(self) -> None:
        """Well-formed JSON list of strings is returned (positive path)."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _make_response(
            '["Quantum mechanics", "Wave function", "Heisenberg uncertainty"]'
        )

        titles = agent._identify_seed_articles("What is quantum mechanics?")

        assert titles == ["Quantum mechanics", "Wave function", "Heisenberg uncertainty"]

    def test_valid_response_capped_at_three(self) -> None:
        """Response with more than 3 titles is truncated to 3."""
        agent = _make_agent()
        agent.claude.messages.create.return_value = _make_response('["T1", "T2", "T3", "T4", "T5"]')

        titles = agent._identify_seed_articles("complex question")

        assert len(titles) == 3
        assert titles == ["T1", "T2", "T3"]

    def test_markdown_fenced_response_is_parsed(self) -> None:
        """Titles wrapped in ```json fences are extracted and returned."""
        agent = _make_agent()
        fenced = '```json\n["Machine learning", "Deep learning"]\n```'
        agent.claude.messages.create.return_value = _make_response(fenced)

        titles = agent._identify_seed_articles("Explain deep learning")

        assert titles == ["Machine learning", "Deep learning"]

    def test_no_fallback_seed_extraction_method_exists(self) -> None:
        """_fallback_seed_extraction must NOT exist on KnowledgeGraphAgent.

        OLD code had this method; its removal is part of the A1 contract.
        This test ensures it stays removed.
        """
        agent = _make_agent()
        assert not hasattr(agent, "_fallback_seed_extraction"), (
            "_fallback_seed_extraction was removed in the exception-handling refactoring; "
            "it must not be re-introduced"
        )

    def test_no_fallback_stop_words_constant(self) -> None:
        """_FALLBACK_STOP_WORDS module-level constant must NOT exist.

        OLD code used this in _fallback_seed_extraction to filter words.
        Its removal confirms the fallback path is gone.
        """
        import wikigr.agent.kg_agent as kg_module

        assert not hasattr(kg_module, "_FALLBACK_STOP_WORDS"), (
            "_FALLBACK_STOP_WORDS was removed together with _fallback_seed_extraction; "
            "it must not be re-introduced"
        )


# ===========================================================================
# A1 (integration) — graph_query propagates _identify_seed_articles errors
# ===========================================================================


class TestGraphQueryPropagatesIdentifySeedErrors:
    """graph_query() must propagate errors from _identify_seed_articles to the caller.

    OLD behaviour: graph_query() caught the error and called _fallback_seed_extraction(),
    continuing with garbage word-split seeds instead of signalling the failure.

    NEW contract: graph_query() calls _identify_seed_articles() and lets its
    exceptions propagate unmodified.
    """

    def test_api_connection_error_propagates_from_graph_query(self) -> None:
        """APIConnectionError in _identify_seed_articles propagates from graph_query()."""
        agent = _make_agent()
        with (
            patch.object(
                agent,
                "_identify_seed_articles",
                side_effect=APIConnectionError(
                    request=httpx.Request("POST", "https://api.anthropic.com")
                ),
            ),
            pytest.raises(APIConnectionError),
        ):
            agent.graph_query("What are the applications of machine learning?")

    def test_value_error_propagates_from_graph_query(self) -> None:
        """ValueError from _identify_seed_articles propagates from graph_query()."""
        agent = _make_agent()
        with (
            patch.object(
                agent,
                "_identify_seed_articles",
                side_effect=ValueError("Unexpected response format from _identify_seed_articles"),
            ),
            pytest.raises(ValueError, match="Unexpected response format"),
        ):
            agent.graph_query("What is quantum computing?")

    def test_api_timeout_error_propagates_from_graph_query(self) -> None:
        """APITimeoutError in _identify_seed_articles propagates from graph_query()."""
        agent = _make_agent()
        with (
            patch.object(
                agent,
                "_identify_seed_articles",
                side_effect=APITimeoutError(
                    request=httpx.Request("POST", "https://api.anthropic.com")
                ),
            ),
            pytest.raises(APITimeoutError),
        ):
            agent.graph_query("Explain the theory of relativity")


# ===========================================================================
# A2 — CypherRAG: no _safe_fallback method
# ===========================================================================


class TestCypherRAGNoSafeFallback:
    """CypherRAG._safe_fallback must NOT exist.

    OLD behaviour: generate_cypher() caught all exceptions (API errors, JSON parse
    failures) and returned a generic ``MATCH (a:Article) RETURN *`` as a fallback —
    a semantically wrong query that silently bypassed the intended pipeline.

    NEW contract (design/exception-handling.md §A2):
    - _safe_fallback method is removed; it must not exist.
    - ValueError is raised on empty response; json.JSONDecodeError on bad JSON.
    (The raise behaviour is already tested in test_cypher_rag.py::TestRaisesOnApiError.)
    """

    def test_no_safe_fallback_method_on_cypher_rag(self) -> None:
        """CypherRAG must not have a _safe_fallback method."""
        from wikigr.agent.cypher_rag import CypherRAG

        assert not hasattr(CypherRAG, "_safe_fallback"), (
            "_safe_fallback was removed in the exception-handling refactoring; "
            "it must not be re-introduced"
        )


# ===========================================================================
# C — Narrowed except blocks in query() pipeline
# ===========================================================================


class TestDirectTitleLookupExceptionNarrowing:
    """query() catches only RuntimeError around _direct_title_lookup.

    OLD behaviour: except Exception caught AttributeError/TypeError from programming
    bugs, hiding real defects in the code.

    NEW contract (design/exception-handling.md §C):
    - RuntimeError (Kuzu DB errors) → caught and logged; query() continues.
    - AttributeError / TypeError (programming bugs) → propagate unchanged.

    Each test would FAIL against the old code:
    - The RuntimeError test verifies the happy path (catching DB errors is still correct).
    - The AttributeError test is the NEW requirement — old code would have swallowed it.
    """

    def _high_sim_results(self) -> dict:
        return {"sources": ["Python"], "entities": [], "facts": [], "raw": []}

    def test_runtime_error_in_direct_lookup_is_swallowed(self) -> None:
        """RuntimeError from _direct_title_lookup is logged but does not abort query()."""
        agent = _make_agent()

        with (
            patch.object(
                agent,
                "_vector_primary_retrieve",
                return_value=(self._high_sim_results(), 0.9),
            ),
            patch.object(
                agent,
                "_direct_title_lookup",
                side_effect=RuntimeError("Kuzu: relation 'Article' does not exist"),
            ),
            patch.object(
                agent,
                "_hybrid_retrieve",
                return_value={"sources": [], "facts": [], "entities": [], "raw": []},
            ),
            patch.object(agent, "_synthesize_answer", return_value="synthesized answer"),
        ):
            result = agent.query("What is Python?")

        # query() must succeed despite the RuntimeError
        assert result["answer"] == "synthesized answer"

    def test_attribute_error_in_direct_lookup_propagates(self) -> None:
        """AttributeError from _direct_title_lookup propagates from query().

        OLD code: except Exception caught this → silent bug, query returned normally.
        NEW code: except RuntimeError lets AttributeError through → visible failure.
        """
        agent = _make_agent()

        with (
            patch.object(
                agent,
                "_vector_primary_retrieve",
                return_value=(self._high_sim_results(), 0.9),
            ),
            patch.object(
                agent,
                "_direct_title_lookup",
                side_effect=AttributeError("'NoneType' object has no attribute 'split'"),
            ),
            pytest.raises(AttributeError, match="has no attribute 'split'"),
        ):
            agent.query("What is Python?")

    def test_type_error_in_direct_lookup_propagates(self) -> None:
        """TypeError from _direct_title_lookup propagates from query().

        Programming bugs (wrong types) must not be silently swallowed.
        """
        agent = _make_agent()

        with (
            patch.object(
                agent,
                "_vector_primary_retrieve",
                return_value=(self._high_sim_results(), 0.9),
            ),
            patch.object(
                agent,
                "_direct_title_lookup",
                side_effect=TypeError("unsupported operand type(s)"),
            ),
            pytest.raises(TypeError, match="unsupported operand"),
        ):
            agent.query("What is Python?")


class TestHybridRetrieveExceptionNarrowing:
    """query() catches only RuntimeError around _hybrid_retrieve.

    OLD behaviour: except Exception caught everything.
    NEW contract: AttributeError propagates.
    """

    def _high_sim_results(self) -> dict:
        return {"sources": ["Python"], "entities": [], "facts": [], "raw": []}

    def test_runtime_error_in_hybrid_retrieve_is_swallowed(self) -> None:
        """RuntimeError from _hybrid_retrieve is logged; query() returns normally."""
        agent = _make_agent()

        with (
            patch.object(
                agent,
                "_vector_primary_retrieve",
                return_value=(self._high_sim_results(), 0.9),
            ),
            patch.object(agent, "_direct_title_lookup", return_value=[]),
            patch.object(
                agent,
                "_hybrid_retrieve",
                side_effect=RuntimeError("Kuzu connection reset during hybrid"),
            ),
            patch.object(agent, "_synthesize_answer", return_value="partial answer"),
        ):
            result = agent.query("What is Python?")

        assert result["answer"] == "partial answer"

    def test_attribute_error_in_hybrid_retrieve_propagates(self) -> None:
        """AttributeError from _hybrid_retrieve propagates from query().

        OLD code: except Exception swallowed it.
        NEW code: except RuntimeError lets it through.
        """
        agent = _make_agent()

        with (
            patch.object(
                agent,
                "_vector_primary_retrieve",
                return_value=(self._high_sim_results(), 0.9),
            ),
            patch.object(agent, "_direct_title_lookup", return_value=[]),
            patch.object(
                agent,
                "_hybrid_retrieve",
                side_effect=AttributeError("mock programming bug in hybrid"),
            ),
            pytest.raises(AttributeError, match="programming bug"),
        ):
            agent.query("What is Python?")


# ===========================================================================
# A3 / A4 — Stage name renames
# ===========================================================================


class TestPipelineStageNames:
    """Pipeline stage names in query() result must use the new naming.

    OLD: "confidence_gated_fallback" / "vector_fallback" (misleading "fallback" label).
    NEW: "training_only_response" / "vector_search" (describes the actual behaviour).

    These tests complement tests in test_kg_agent_core.py and test_kg_agent_semantic.py.
    They assert the OLD strings no longer appear anywhere in the codebase.
    """

    def test_confidence_gated_fallback_string_not_in_source(self) -> None:
        """'confidence_gated_fallback' must not appear in kg_agent.py source."""
        import inspect

        import wikigr.agent.kg_agent as module

        source = inspect.getsource(module)
        assert "confidence_gated_fallback" not in source, (
            "'confidence_gated_fallback' was renamed to 'training_only_response'; "
            "it must not appear in kg_agent.py"
        )

    def test_vector_fallback_string_not_in_source(self) -> None:
        """'vector_fallback' must not appear in kg_agent.py source."""
        import inspect

        import wikigr.agent.kg_agent as module

        source = inspect.getsource(module)
        assert (
            "vector_fallback" not in source
        ), "'vector_fallback' was renamed to 'vector_search'; it must not appear in kg_agent.py"

    def test_training_only_response_returned_on_low_similarity(self) -> None:
        """query_type 'training_only_response' is returned when max_similarity < 0.5."""
        agent = _make_agent()
        low_sim_results = {"sources": ["Unrelated"], "entities": [], "facts": [], "raw": []}

        with (
            patch.object(agent, "_vector_primary_retrieve", return_value=(low_sim_results, 0.1)),
            patch.object(agent, "_synthesize_answer_minimal", return_value="training answer"),
        ):
            result = agent.query("completely off-topic question")

        assert result["query_type"] == "training_only_response"

    def test_vector_search_returned_on_high_similarity(self) -> None:
        """query_type 'vector_search' is returned when the normal pipeline runs."""
        agent = _make_agent()
        high_sim_results = {"sources": ["Python"], "entities": [], "facts": [], "raw": []}

        with (
            patch.object(agent, "_vector_primary_retrieve", return_value=(high_sim_results, 0.85)),
            patch.object(agent, "_direct_title_lookup", return_value=[]),
            patch.object(
                agent,
                "_hybrid_retrieve",
                return_value={"sources": [], "facts": [], "entities": [], "raw": []},
            ),
            patch.object(agent, "_synthesize_answer", return_value="synthesized"),
        ):
            result = agent.query("What is Python?")

        assert result["query_type"] == "vector_search"
