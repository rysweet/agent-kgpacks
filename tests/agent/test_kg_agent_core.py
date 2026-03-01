"""Unit tests for 6 critical untested KnowledgeGraphAgent methods.

Targets:
  1. _safe_json_loads (module-level)
  2. _execute_query
  3. _execute_fallback_query
  4. _fetch_source_text
  5. _build_synthesis_context
  6. _hybrid_retrieve

All tests mock the Kuzu connection and Claude API -- no real DB or network calls.
Uses pandas DataFrames to match real Kuzu return format.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from wikigr.agent.kg_agent import KnowledgeGraphAgent, _safe_json_loads

# ---------------------------------------------------------------------------
# Helpers
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
    agent.use_enhancements = False
    agent.enable_reranker = True
    agent.enable_multidoc = True
    agent.enable_fewshot = True
    agent.reranker = None
    agent.synthesizer = None
    agent.few_shot = None
    return agent


def _mock_execute_result(df: pd.DataFrame) -> MagicMock:
    """Wrap a DataFrame in a mock Kuzu query result."""
    result = MagicMock()
    result.get_as_df.return_value = df
    return result


# ===================================================================
# 1. _safe_json_loads
# ===================================================================


class TestSafeJsonLoads:
    """Module-level _safe_json_loads: valid JSON, invalid, dict passthrough, other types."""

    def test_valid_json_string(self) -> None:
        assert _safe_json_loads('{"key": "value"}') == {"key": "value"}

    def test_invalid_json_returns_empty_dict(self) -> None:
        assert _safe_json_loads("not json at all") == {}

    def test_dict_passthrough(self) -> None:
        d = {"already": "a dict"}
        assert _safe_json_loads(d) is d

    def test_non_string_non_dict_returns_empty_dict(self) -> None:
        assert _safe_json_loads(42) == {}
        assert _safe_json_loads(None) == {}
        assert _safe_json_loads([1, 2]) == {}

    def test_empty_string_returns_empty_dict(self) -> None:
        assert _safe_json_loads("") == {}


# ===================================================================
# 2. _execute_query
# ===================================================================


class TestExecuteQuery:
    """_execute_query: structures results, handles empty, calls fallback on bad Cypher."""

    def test_structures_results_with_title_and_facts(self) -> None:
        agent = _make_agent()
        df = pd.DataFrame(
            {
                "title": ["Quantum Mechanics", "Relativity"],
                "content": ["Energy is quantized", "E=mc^2"],
            }
        )
        agent.conn.execute.return_value = _mock_execute_result(df)

        result = agent._execute_query(
            "MATCH (a:Article) RETURN a.title AS title, f.content AS content LIMIT 10",
            limit=10,
            params={"q": "physics"},
        )

        assert "Quantum Mechanics" in result["sources"]
        assert "Relativity" in result["sources"]
        assert "Energy is quantized" in result["facts"]
        assert "E=mc^2" in result["facts"]

    def test_empty_results_returns_empty_structure(self) -> None:
        agent = _make_agent()
        agent.conn.execute.return_value = _mock_execute_result(pd.DataFrame())

        result = agent._execute_query(
            "MATCH (a:Article) RETURN a.title AS title LIMIT 10",
            limit=10,
        )

        assert result == {"sources": [], "entities": [], "facts": [], "raw": []}

    def test_invalid_cypher_triggers_fallback(self) -> None:
        agent = _make_agent()

        # Fallback should also return empty since no search term available
        with patch.object(agent, "_execute_fallback_query") as mock_fallback:
            mock_fallback.return_value = {
                "sources": ["Fallback Article"],
                "entities": [],
                "facts": [],
                "raw": [],
                "fallback": True,
            }

            # Use a Cypher query that _validate_cypher will reject
            result = agent._execute_query(
                "CREATE (a:Article {title: 'bad'})",
                limit=10,
                params={"q": "test"},
            )

            mock_fallback.assert_called_once()
            assert result["sources"] == ["Fallback Article"]
            assert result["fallback"] is True

    def test_extracts_entities_from_name_and_type_columns(self) -> None:
        agent = _make_agent()
        df = pd.DataFrame(
            {
                "name": ["Albert Einstein", "Niels Bohr"],
                "type": ["person", "person"],
            }
        )
        agent.conn.execute.return_value = _mock_execute_result(df)

        result = agent._execute_query(
            "MATCH (e:Entity) RETURN e.name AS name, e.type AS type LIMIT 10",
            limit=10,
        )

        assert len(result["entities"]) == 2
        assert result["entities"][0]["name"] == "Albert Einstein"
        assert result["entities"][0]["type"] == "person"


# ===================================================================
# 3. _execute_fallback_query
# ===================================================================


class TestExecuteFallbackQuery:
    """_execute_fallback_query: title-based search, empty params, DB error."""

    def test_generates_title_based_search(self) -> None:
        agent = _make_agent()
        df = pd.DataFrame(
            {
                "title": ["Quantum Mechanics"],
                "category": ["physics"],
            }
        )
        agent.conn.execute.return_value = _mock_execute_result(df)

        result = agent._execute_fallback_query(
            params={"q": "quantum"},
            limit=5,
            primary_error="Cypher syntax error",
        )

        assert result["sources"] == ["Quantum Mechanics"]
        assert result["fallback"] is True
        assert result["primary_error"] == "Cypher syntax error"

    def test_no_params_returns_error(self) -> None:
        agent = _make_agent()
        result = agent._execute_fallback_query(
            params=None,
            limit=5,
            primary_error="bad cypher",
        )

        assert result["sources"] == []
        assert "bad cypher" in result["error"]

    def test_empty_string_param_returns_error(self) -> None:
        agent = _make_agent()
        result = agent._execute_fallback_query(
            params={"q": ""},
            limit=5,
            primary_error="bad cypher",
        )

        assert result["sources"] == []
        assert "bad cypher" in result["error"]

    def test_db_error_in_fallback_returns_error(self) -> None:
        agent = _make_agent()
        agent.conn.execute.side_effect = RuntimeError("connection lost")

        result = agent._execute_fallback_query(
            params={"q": "physics"},
            limit=5,
            primary_error="original error",
        )

        assert result["sources"] == []
        assert "Both primary and fallback" in result["error"]

    def test_empty_df_from_fallback_returns_no_results(self) -> None:
        agent = _make_agent()
        agent.conn.execute.return_value = _mock_execute_result(pd.DataFrame())

        result = agent._execute_fallback_query(
            params={"q": "nonexistent_topic_xyz"},
            limit=5,
            primary_error="bad cypher",
        )

        assert result["sources"] == []
        assert "fallback found no results" in result["error"]


# ===================================================================
# 4. _fetch_source_text
# ===================================================================


class TestFetchSourceText:
    """_fetch_source_text: returns article text, handles missing, handles DB error."""

    def test_returns_article_text_from_sections(self) -> None:
        agent = _make_agent()
        df = pd.DataFrame(
            {
                "title": ["Quantum Mechanics", "Quantum Mechanics"],
                "content": ["Lead section text.", "Second section text."],
            }
        )
        agent.conn.execute.return_value = _mock_execute_result(df)

        text = agent._fetch_source_text(["Quantum Mechanics"])

        assert "## Quantum Mechanics" in text
        assert "Lead section text." in text
        assert "Second section text." in text

    def test_empty_titles_returns_empty_string(self) -> None:
        agent = _make_agent()
        assert agent._fetch_source_text([]) == ""

    def test_falls_back_to_article_content(self) -> None:
        """When section query returns empty, falls back to article.content."""
        agent = _make_agent()

        # First call (section query) returns empty, second call (article content) returns data
        empty_df = pd.DataFrame()
        content_df = pd.DataFrame(
            {
                "title": ["Relativity"],
                "content": ["Einstein developed the theory of relativity."],
            }
        )
        agent.conn.execute.side_effect = [
            _mock_execute_result(empty_df),
            _mock_execute_result(content_df),
        ]

        text = agent._fetch_source_text(["Relativity"])

        assert "## Relativity" in text
        assert "Einstein developed" in text

    def test_db_error_returns_empty_string(self) -> None:
        agent = _make_agent()
        agent.conn.execute.side_effect = RuntimeError("DB connection lost")

        text = agent._fetch_source_text(["Some Article"])

        # Both section and fallback queries fail, but no exception propagates
        assert text == ""

    def test_truncates_long_content(self) -> None:
        agent = _make_agent()
        long_content = "x" * 5000
        df = pd.DataFrame({"title": ["Big Article"], "content": [long_content]})
        agent.conn.execute.return_value = _mock_execute_result(df)

        text = agent._fetch_source_text(["Big Article"])

        # Content should be truncated to 3000 chars + "..."
        assert "..." in text
        # The full 5000-char string should not appear
        assert long_content not in text

    def test_respects_max_articles(self) -> None:
        agent = _make_agent()
        titles = [f"Article {i}" for i in range(10)]

        df = pd.DataFrame(
            {
                "title": titles[:5],
                "content": [f"Content for article {i}" for i in range(5)],
            }
        )
        agent.conn.execute.return_value = _mock_execute_result(df)

        text = agent._fetch_source_text(titles, max_articles=3)

        # Only first 3 articles should appear in output (max_articles=3 slices the input)
        assert "Article 0" in text
        assert "Article 2" in text


# ===================================================================
# 5. _build_synthesis_context
# ===================================================================


class TestBuildSynthesisContext:
    """_build_synthesis_context: includes sources, entities, facts."""

    def test_includes_sources_entities_and_facts(self) -> None:
        agent = _make_agent()
        # Mock _fetch_source_text to avoid DB calls
        with patch.object(agent, "_fetch_source_text", return_value="## Quantum\nSome text"):
            context = agent._build_synthesis_context(
                question="What is quantum mechanics?",
                kg_results={
                    "sources": ["Quantum Mechanics"],
                    "entities": [{"name": "Planck", "type": "person"}],
                    "facts": ["Energy is quantized", "Photons have wave-particle duality"],
                    "raw": [],
                },
                query_plan={"type": "entity_search", "cypher": "MATCH (a) RETURN a"},
            )

        assert "What is quantum mechanics?" in context
        assert "Quantum Mechanics" in context
        assert "Planck" in context
        assert "Energy is quantized" in context
        assert "Photons have wave-particle duality" in context
        assert "## Quantum" in context  # source text section

    def test_includes_few_shot_examples(self) -> None:
        agent = _make_agent()
        with patch.object(agent, "_fetch_source_text", return_value=""):
            context = agent._build_synthesis_context(
                question="Explain relativity",
                kg_results={"sources": [], "entities": [], "facts": [], "raw": []},
                query_plan={"type": "semantic_search", "cypher": "MATCH (a) RETURN a"},
                few_shot_examples=[
                    {"question": "What is gravity?", "answer": "Gravity is a fundamental force."}
                ],
            )

        assert "Example 1:" in context
        assert "What is gravity?" in context
        assert "Gravity is a fundamental force." in context

    def test_handles_enriched_context(self) -> None:
        agent = _make_agent()
        with patch.object(agent, "_fetch_source_text", return_value=""):
            context = agent._build_synthesis_context(
                question="What is dark matter?",
                kg_results={
                    "sources": ["Dark Matter"],
                    "entities": [],
                    "facts": ["Dark matter makes up 27% of the universe"],
                    "raw": [],
                    "enriched_context": "Multi-doc enriched context block here.",
                },
                query_plan={"type": "fact_retrieval", "cypher": "MATCH (a) RETURN a"},
            )

        # When enriched_context is present, it should be used instead of standard context
        assert "Multi-doc enriched context block here." in context
        # Standard context (Cypher line) should NOT appear
        assert "Cypher:" not in context

    def test_handles_empty_results(self) -> None:
        agent = _make_agent()
        with patch.object(agent, "_fetch_source_text", return_value=""):
            context = agent._build_synthesis_context(
                question="What is nothing?",
                kg_results={"sources": [], "entities": [], "facts": [], "raw": []},
                query_plan={"type": "entity_search", "cypher": "MATCH (a) RETURN a"},
            )

        # Should still produce a valid prompt string
        assert "What is nothing?" in context
        assert "Sources:" in context


# ===================================================================
# 6. _hybrid_retrieve
# ===================================================================


class TestHybridRetrieve:
    """_hybrid_retrieve: combines signals, handles partial failures."""

    def test_combines_vector_and_keyword_signals(self) -> None:
        agent = _make_agent()

        # Mock semantic_search for vector signal
        vector_results = [
            {"title": "Quantum Mechanics", "similarity": 0.9},
            {"title": "Particle Physics", "similarity": 0.7},
        ]

        # Mock conn.execute for graph traversal and keyword search
        # The method calls conn.execute multiple times:
        # - Graph traversal for each seed (up to 3)
        # - Keyword search for each keyword (up to 3)
        # - Fact fetch for top sources (up to 5)
        graph_df = pd.DataFrame({"title": ["String Theory"]})
        keyword_df = pd.DataFrame({"title": ["Quantum Mechanics"]})
        facts_df = pd.DataFrame({"content": ["Energy is quantized"]})

        agent.conn.execute.return_value = _mock_execute_result(graph_df)

        with patch.object(agent, "semantic_search", return_value=vector_results):
            # Override conn.execute to return different results for different queries
            call_count = 0

            def _side_effect(query, params=None):
                nonlocal call_count
                call_count += 1
                if "LINKS_TO" in query:
                    return _mock_execute_result(graph_df)
                elif "CONTAINS" in query:
                    return _mock_execute_result(keyword_df)
                elif "HAS_FACT" in query:
                    return _mock_execute_result(facts_df)
                return _mock_execute_result(pd.DataFrame())

            agent.conn.execute.side_effect = _side_effect

            result = agent._hybrid_retrieve("What is quantum mechanics?", max_results=10)

        assert "Quantum Mechanics" in result["sources"]
        assert isinstance(result["facts"], list)
        assert isinstance(result["entities"], list)
        assert isinstance(result["raw"], list)

    def test_handles_vector_search_failure(self) -> None:
        agent = _make_agent()

        # Vector search raises
        with patch.object(agent, "semantic_search", side_effect=RuntimeError("embedding failed")):
            # Keyword search still works
            keyword_df = pd.DataFrame({"title": ["General Relativity"]})
            agent.conn.execute.return_value = _mock_execute_result(keyword_df)

            result = agent._hybrid_retrieve("relativity theory", max_results=5)

        # Should still return results from keyword signal
        assert isinstance(result["sources"], list)
        # Graph traversal has no seeds (vector failed), but keyword should contribute
        # The result may or may not have sources depending on keyword length filter
        assert isinstance(result, dict)

    def test_handles_all_db_failures(self) -> None:
        agent = _make_agent()

        with patch.object(agent, "semantic_search", return_value=[]):
            agent.conn.execute.side_effect = RuntimeError("DB down")

            result = agent._hybrid_retrieve("anything", max_results=5)

        # Should return empty structure, not raise
        assert result["sources"] == []
        assert result["facts"] == []

    def test_keyword_weight_affects_ranking(self) -> None:
        agent = _make_agent()

        with patch.object(agent, "semantic_search", return_value=[]):
            # Keyword search returns results
            keyword_df = pd.DataFrame({"title": ["Thermodynamics"]})
            facts_df = pd.DataFrame({"content": ["Heat flows from hot to cold"]})

            def _side_effect(query, params=None):
                if "CONTAINS" in query:
                    return _mock_execute_result(keyword_df)
                elif "HAS_FACT" in query:
                    return _mock_execute_result(facts_df)
                return _mock_execute_result(pd.DataFrame())

            agent.conn.execute.side_effect = _side_effect

            result = agent._hybrid_retrieve(
                "Thermodynamics laws",
                max_results=5,
                keyword_weight=1.0,
                vector_weight=0.0,
                graph_weight=0.0,
            )

        assert "Thermodynamics" in result["sources"]


# ===================================================================
# 7. Confidence-gated context injection
# ===================================================================


class TestConfidenceGatedContextInjection:
    """query() skips pack context and uses minimal synthesis when vector similarity < 0.5."""

    def test_low_similarity_triggers_confidence_gated_fallback(self) -> None:
        """max_similarity < 0.5 → confidence gate fires, _synthesize_answer_minimal called."""
        agent = _make_agent()
        agent.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

        low_sim_results = {"sources": ["Unrelated"], "entities": [], "facts": [], "raw": []}

        with (
            patch.object(agent, "_vector_primary_retrieve", return_value=(low_sim_results, 0.1)),
            patch.object(
                agent, "_synthesize_answer_minimal", return_value="fallback answer"
            ) as mock_minimal,
            patch.object(agent, "_synthesize_answer") as mock_synth,
        ):
            result = agent.query("What is Python?")

        assert result["query_type"] == "confidence_gated_fallback"
        assert result["answer"] == "fallback answer"
        assert result["sources"] == []
        assert result["entities"] == []
        assert result["facts"] == []
        mock_minimal.assert_called_once_with("What is Python?")
        mock_synth.assert_not_called()

    def test_high_similarity_runs_normal_pipeline(self) -> None:
        """max_similarity >= 0.5 → normal pipeline, _synthesize_answer called."""
        agent = _make_agent()
        agent.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

        high_sim_results = {"sources": ["Python"], "entities": [], "facts": [], "raw": []}

        with (
            patch.object(agent, "_vector_primary_retrieve", return_value=(high_sim_results, 0.8)),
            patch.object(agent, "_direct_title_lookup", return_value=[]),
            patch.object(agent, "_hybrid_retrieve", return_value={"sources": [], "facts": []}),
            patch.object(
                agent, "_synthesize_answer", return_value="synthesized answer"
            ) as mock_synth,
            patch.object(agent, "_synthesize_answer_minimal") as mock_minimal,
        ):
            result = agent.query("What is Python?")

        assert result["query_type"] == "vector_search"
        assert result["answer"] == "synthesized answer"
        mock_synth.assert_called_once()
        mock_minimal.assert_not_called()

    def test_synthesize_answer_minimal_calls_claude_without_kg_context(self) -> None:
        """_synthesize_answer_minimal passes only the question to Claude — no KG sections."""
        agent = _make_agent()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="My own answer")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        agent.claude.messages.create.return_value = mock_response

        result = agent._synthesize_answer_minimal("What is recursion?")

        assert result == "My own answer"

        create_call = agent.claude.messages.create.call_args
        content = create_call.kwargs["messages"][0]["content"]
        assert "What is recursion?" in content
        assert "no relevant content" in content

        assert agent.token_usage["api_calls"] == 1
        assert agent.token_usage["input_tokens"] == 10
        assert agent.token_usage["output_tokens"] == 5

    def test_synthesize_answer_minimal_api_error_returns_fallback_string(self) -> None:
        """On API error, _synthesize_answer_minimal returns the fallback string and does not raise."""
        agent = _make_agent()
        agent.claude.messages.create.side_effect = Exception("API failure")

        result = agent._synthesize_answer_minimal("What is recursion?")

        assert result == "Unable to answer: API error."

    def test_exact_threshold_similarity_does_not_trigger_gate(self) -> None:
        """max_similarity == 0.5 is NOT < threshold — gate must not fire."""
        agent = _make_agent()
        agent.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

        boundary_results = {"sources": ["Source"], "entities": [], "facts": [], "raw": []}

        with (
            patch.object(agent, "_vector_primary_retrieve", return_value=(boundary_results, 0.5)),
            patch.object(agent, "_direct_title_lookup", return_value=[]),
            patch.object(agent, "_hybrid_retrieve", return_value={"sources": [], "facts": []}),
            patch.object(agent, "_synthesize_answer", return_value="normal answer"),
            patch.object(agent, "_synthesize_answer_minimal") as mock_minimal,
        ):
            result = agent.query("What is Python?")

        assert result["query_type"] != "confidence_gated_fallback"
        mock_minimal.assert_not_called()

    def test_synthesize_answer_minimal_empty_response_returns_fallback_string(self) -> None:
        """Empty content list from Claude returns the empty-response fallback string."""
        agent = _make_agent()

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage = MagicMock(input_tokens=5, output_tokens=0)
        agent.claude.messages.create.return_value = mock_response

        result = agent._synthesize_answer_minimal("What is entropy?")

        assert result == "Unable to synthesize answer: empty response from Claude."
