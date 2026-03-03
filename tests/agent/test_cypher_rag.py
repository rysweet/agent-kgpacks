"""Tests for CypherRAG module -- RAG-augmented Cypher query generation.

All tests mock the Claude API and pattern manager -- no real API or DB calls.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from wikigr.agent.cypher_rag import CypherRAG, build_schema_string

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pattern_manager(examples: list[dict] | None = None) -> MagicMock:
    """Build a mock pattern manager with find_similar_examples."""
    mgr = MagicMock()
    if examples is None:
        examples = [
            {
                "question": "What is gravity?",
                "answer": "MATCH (e:Entity) WHERE lower(e.name) CONTAINS lower($q) RETURN e.name AS name LIMIT 10",
            },
            {
                "question": "Tell me about relativity",
                "answer": "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) RETURN a.title AS title LIMIT 10",
            },
        ]
    mgr.find_similar_examples.return_value = examples
    return mgr


def _make_claude_response(content: str) -> MagicMock:
    """Build a mock Claude API response."""
    block = MagicMock()
    block.text = content
    response = MagicMock()
    response.content = [block]
    return response


def _make_cypher_rag(
    pattern_manager: MagicMock | None = None, claude_client: MagicMock | None = None
) -> CypherRAG:
    """Build a CypherRAG with mock dependencies."""
    pm = pattern_manager or _make_pattern_manager()
    client = claude_client or MagicMock()
    return CypherRAG(
        pattern_manager=pm,
        claude_client=client,
        schema="- Article (NODE)\n- Entity (NODE)",
        model="test-model",
    )


# ===================================================================
# test_generate_cypher_returns_valid_plan
# ===================================================================


class TestGenerateCypher:
    """CypherRAG.generate_cypher returns a valid plan from Claude response."""

    def test_returns_valid_plan(self) -> None:
        """A well-formed Claude response produces a complete plan dict."""
        plan_json = json.dumps(
            {
                "type": "entity_search",
                "cypher": "MATCH (e:Entity) WHERE lower(e.name) CONTAINS lower($q) RETURN e.name AS name LIMIT 10",
                "cypher_params": {"q": "gravity"},
                "explanation": "Search for gravity entities",
            }
        )
        client = MagicMock()
        client.messages.create.return_value = _make_claude_response(plan_json)
        rag = _make_cypher_rag(claude_client=client)

        result = rag.generate_cypher("What is gravity?")

        assert result["type"] == "entity_search"
        assert "MATCH" in result["cypher"]
        assert result["cypher_params"]["q"] == "gravity"
        assert result["patterns_used"] == 2  # From mock pattern manager

    def test_handles_markdown_fenced_json(self) -> None:
        """Claude sometimes wraps JSON in markdown code fences."""
        plan = {
            "type": "fact_retrieval",
            "cypher": "MATCH (a:Article)-[:HAS_FACT]->(f:Fact) WHERE lower(a.title) CONTAINS lower($q) RETURN f.content AS fact LIMIT 5",
            "cypher_params": {"q": "physics"},
            "explanation": "Get facts about physics",
        }
        fenced = f"```json\n{json.dumps(plan)}\n```"
        client = MagicMock()
        client.messages.create.return_value = _make_claude_response(fenced)
        rag = _make_cypher_rag(claude_client=client)

        result = rag.generate_cypher("Tell me facts about physics")

        assert result["type"] == "fact_retrieval"
        assert result["cypher_params"]["q"] == "physics"

    def test_handles_plain_fenced_json(self) -> None:
        """Handle ``` fencing without json language tag."""
        plan = {
            "type": "entity_search",
            "cypher": "MATCH (e:Entity) RETURN e.name AS name LIMIT 5",
            "cypher_params": {"q": "test"},
            "explanation": "test",
        }
        fenced = f"```\n{json.dumps(plan)}\n```"
        client = MagicMock()
        client.messages.create.return_value = _make_claude_response(fenced)
        rag = _make_cypher_rag(claude_client=client)

        result = rag.generate_cypher("test query")

        assert result["type"] == "entity_search"


# ===================================================================
# test_prompt_includes_retrieved_patterns
# ===================================================================


class TestPromptIncludesPatterns:
    """The prompt sent to Claude includes retrieved patterns."""

    def test_patterns_in_prompt(self) -> None:
        """Verify the patterns block is populated from the pattern manager."""
        examples = [
            {
                "question": "What is gravity?",
                "answer": "MATCH (e:Entity) WHERE lower(e.name) CONTAINS lower($q) RETURN e.name LIMIT 10",
            },
        ]
        pm = _make_pattern_manager(examples)
        client = MagicMock()
        # Return a valid response so generate_cypher succeeds
        plan_json = json.dumps(
            {
                "type": "entity_search",
                "cypher": "MATCH (e:Entity) RETURN e.name AS name LIMIT 10",
                "cypher_params": {"q": "gravity"},
                "explanation": "test",
            }
        )
        client.messages.create.return_value = _make_claude_response(plan_json)
        rag = _make_cypher_rag(pattern_manager=pm, claude_client=client)

        rag.generate_cypher("What is gravity?")

        # Verify Claude was called with prompt containing the pattern
        call_args = client.messages.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        assert "What is gravity?" in prompt_content
        assert "Pattern 1" in prompt_content
        assert "MATCH (e:Entity)" in prompt_content

    def test_no_patterns_shows_placeholder(self) -> None:
        """When no patterns are retrieved, prompt shows placeholder text."""
        pm = _make_pattern_manager(examples=[])
        client = MagicMock()
        plan_json = json.dumps(
            {
                "type": "entity_search",
                "cypher": "MATCH (a:Article) RETURN a.title AS title LIMIT 10",
                "cypher_params": {"q": "test"},
                "explanation": "test",
            }
        )
        client.messages.create.return_value = _make_claude_response(plan_json)
        rag = _make_cypher_rag(pattern_manager=pm, claude_client=client)

        rag.generate_cypher("Something random")

        call_args = client.messages.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        assert "(no relevant patterns found)" in prompt_content


# ===================================================================
# test_error_propagation_on_api_error
# ===================================================================


class TestRaisesOnApiError:
    """CypherRAG raises errors on API failures (no silent fallback)."""

    def test_claude_api_error_raises(self) -> None:
        """An exception from Claude propagates to the caller."""
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("API timeout")
        rag = _make_cypher_rag(claude_client=client)

        with pytest.raises(RuntimeError):
            rag.generate_cypher("What are black holes?")

    def test_empty_response_raises_value_error(self) -> None:
        """An empty Claude response raises ValueError."""
        response = MagicMock()
        response.content = []
        client = MagicMock()
        client.messages.create.return_value = response
        rag = _make_cypher_rag(claude_client=client)

        with pytest.raises(ValueError, match="Empty response"):
            rag.generate_cypher("What is dark matter?")

    def test_invalid_json_raises_json_decode_error(self) -> None:
        """Non-JSON Claude response raises json.JSONDecodeError."""
        client = MagicMock()
        client.messages.create.return_value = _make_claude_response("This is not JSON at all")
        rag = _make_cypher_rag(claude_client=client)

        with pytest.raises(json.JSONDecodeError):
            rag.generate_cypher("Explain quantum mechanics")

    def test_pattern_retrieval_failure_continues(self) -> None:
        """Pattern retrieval failure does not prevent query generation."""
        pm = MagicMock()
        pm.find_similar_examples.side_effect = RuntimeError("Embedding model unavailable")
        client = MagicMock()
        plan_json = json.dumps(
            {
                "type": "entity_search",
                "cypher": "MATCH (e:Entity) RETURN e.name AS name LIMIT 10",
                "cypher_params": {"q": "test"},
                "explanation": "test",
            }
        )
        client.messages.create.return_value = _make_claude_response(plan_json)
        rag = _make_cypher_rag(pattern_manager=pm, claude_client=client)

        result = rag.generate_cypher("What is energy?")

        # Should succeed using Claude even though patterns failed
        assert result["type"] == "entity_search"
        assert result["patterns_used"] == 0  # No patterns were retrieved


# ===================================================================
# test_cypher_params_always_has_q
# ===================================================================


class TestCypherParamsAlwaysHasQ:
    """cypher_params dict always contains 'q' key."""

    def test_adds_q_when_missing_entirely(self) -> None:
        """If Claude response has no cypher_params, one is created with 'q'."""
        plan_json = json.dumps(
            {
                "type": "entity_search",
                "cypher": "MATCH (e:Entity) RETURN e.name AS name LIMIT 10",
                "explanation": "test",
            }
        )
        client = MagicMock()
        client.messages.create.return_value = _make_claude_response(plan_json)
        rag = _make_cypher_rag(claude_client=client)

        result = rag.generate_cypher("What is gravity?")

        assert "q" in result["cypher_params"]
        assert result["cypher_params"]["q"] == "What is gravity?"

    def test_adds_q_when_params_exist_but_no_q(self) -> None:
        """If cypher_params exists but lacks 'q', 'q' is added."""
        plan_json = json.dumps(
            {
                "type": "entity_search",
                "cypher": "MATCH (e:Entity) WHERE e.type = $entity_type RETURN e.name AS name LIMIT 10",
                "cypher_params": {"entity_type": "PERSON"},
                "explanation": "test",
            }
        )
        client = MagicMock()
        client.messages.create.return_value = _make_claude_response(plan_json)
        rag = _make_cypher_rag(claude_client=client)

        result = rag.generate_cypher("Find all people")

        assert result["cypher_params"]["q"] == "Find all people"
        assert result["cypher_params"]["entity_type"] == "PERSON"

    def test_preserves_existing_q(self) -> None:
        """If Claude already provides 'q', it is preserved."""
        plan_json = json.dumps(
            {
                "type": "entity_search",
                "cypher": "MATCH (e:Entity) WHERE lower(e.name) CONTAINS lower($q) RETURN e.name AS name LIMIT 10",
                "cypher_params": {"q": "Einstein"},
                "explanation": "test",
            }
        )
        client = MagicMock()
        client.messages.create.return_value = _make_claude_response(plan_json)
        rag = _make_cypher_rag(claude_client=client)

        result = rag.generate_cypher("Tell me about Einstein")

        assert result["cypher_params"]["q"] == "Einstein"


# ===================================================================
# test_build_schema_string
# ===================================================================


class TestBuildSchemaString:
    """build_schema_string extracts schema from Kuzu connection."""

    def test_returns_formatted_schema(self) -> None:
        """Schema tables are formatted as '- Name (type)' lines."""
        df = pd.DataFrame(
            {"name": ["Article", "Entity", "HAS_ENTITY"], "type": ["NODE", "NODE", "REL"]}
        )
        mock_result = MagicMock()
        mock_result.get_as_df.return_value = df
        conn = MagicMock()
        conn.execute.return_value = mock_result

        schema = build_schema_string(conn)

        assert "- Article (NODE)" in schema
        assert "- Entity (NODE)" in schema
        assert "- HAS_ENTITY (REL)" in schema

    def test_returns_unavailable_on_error(self) -> None:
        """Schema extraction failure returns placeholder string."""
        conn = MagicMock()
        conn.execute.side_effect = RuntimeError("DB error")

        schema = build_schema_string(conn)

        assert schema == "(schema unavailable)"

    def test_returns_unavailable_on_empty_tables(self) -> None:
        """Empty table list returns placeholder string."""
        df = pd.DataFrame({"name": [], "type": []})
        mock_result = MagicMock()
        mock_result.get_as_df.return_value = df
        conn = MagicMock()
        conn.execute.return_value = mock_result

        schema = build_schema_string(conn)

        assert schema == "(schema unavailable)"


# TestKGAgentCypherRagIntegration removed: _plan_query_uncached was deleted in #252
