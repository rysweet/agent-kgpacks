"""Unit tests for wikigr.agent.synthesizer module.

Targets:
  1. build_synthesis_context — builds the full synthesis prompt string
  2. synthesize_answer_minimal — Claude-only answer without KG context
  3. synthesize_answer — full synthesis using KG results + Claude

All tests mock the Anthropic client — no real DB or network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

from wikigr.agent.synthesizer import (
    build_synthesis_context,
    synthesize_answer,
    synthesize_answer_minimal,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_claude_response(text: str) -> MagicMock:
    """Build a mock Claude API response with the given text content."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(input_tokens=20, output_tokens=10)
    return resp


def _mock_empty_response() -> MagicMock:
    """Build a mock Claude API response with an empty content list."""
    resp = MagicMock()
    resp.content = []
    resp.usage = MagicMock(input_tokens=5, output_tokens=0)
    return resp


def _make_kg_results(
    sources: list[str] | None = None,
    entities: list | None = None,
    facts: list[str] | None = None,
    raw: list | None = None,
    error: str | None = None,
) -> dict:
    """Build a KG results dict with optional fields."""
    result: dict = {
        "sources": sources or [],
        "entities": entities or [],
        "facts": facts or [],
        "raw": raw or [],
    }
    if error is not None:
        result["error"] = error
    return result


def _noop_track(response: object) -> None:
    """No-op tracker for token usage."""


def _noop_fetch(sources: list[str], question: str = "") -> str:
    """No-op fetch_source_text returning empty string."""
    return ""


# ===================================================================
# 1. build_synthesis_context
# ===================================================================


class TestBuildSynthesisContext:
    """build_synthesis_context: builds prompt with sources, entities, facts, few-shot."""

    def test_includes_question_and_sources(self) -> None:
        """Prompt contains the question and listed sources."""
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="What is quantum mechanics?",
            kg_results=_make_kg_results(sources=["Quantum Mechanics", "Wave Function"]),
            query_plan={"type": "entity_search"},
        )

        assert "What is quantum mechanics?" in context
        assert "Quantum Mechanics" in context
        assert "Wave Function" in context

    def test_includes_entities_and_facts(self) -> None:
        """Prompt contains entity and fact data from KG results."""
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="Tell me about Planck",
            kg_results=_make_kg_results(
                entities=[{"name": "Planck", "type": "person"}],
                facts=["Energy is quantized", "E=hf"],
            ),
            query_plan={"type": "entity_search"},
        )

        assert "Planck" in context
        assert "Energy is quantized" in context
        assert "E=hf" in context

    def test_includes_query_type(self) -> None:
        """Prompt includes the query plan type."""
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "semantic_search"},
        )

        assert "Query Type: semantic_search" in context

    def test_includes_source_text_when_available(self) -> None:
        """When fetch_source_text_fn returns text, it appears in the prompt."""

        def fetch_fn(sources, question=""):
            return "## Quantum\nThe theory of quantum mechanics..."

        context = build_synthesis_context(
            fetch_source_text_fn=fetch_fn,
            question="Explain quantum mechanics",
            kg_results=_make_kg_results(sources=["Quantum"]),
            query_plan={"type": "entity_search"},
        )

        assert "Original Article Text (for grounding):" in context
        assert "The theory of quantum mechanics..." in context

    def test_omits_source_text_section_when_empty(self) -> None:
        """When fetch_source_text_fn returns empty, 'Original Article Text' section is absent."""
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
        )

        assert "Original Article Text" not in context

    def test_includes_few_shot_examples(self) -> None:
        """Few-shot examples appear in the prompt when provided."""
        examples = [
            {"question": "What is gravity?", "answer": "Gravity is a fundamental force."},
            {"query": "Define entropy", "ground_truth": "Entropy is a measure of disorder."},
        ]
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="What is magnetism?",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
            few_shot_examples=examples,
        )

        assert "Example 1:" in context
        assert "What is gravity?" in context
        assert "Gravity is a fundamental force." in context
        assert "Example 2:" in context
        assert "Define entropy" in context
        assert "Entropy is a measure of disorder." in context

    def test_few_shot_capped_at_three(self) -> None:
        """Only the first 3 few-shot examples are included."""
        examples = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(5)]
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
            few_shot_examples=examples,
        )

        assert "Example 3:" in context
        assert "Example 4:" not in context

    def test_no_few_shot_section_when_none(self) -> None:
        """No few-shot section when few_shot_examples is None."""
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
            few_shot_examples=None,
        )

        assert "Example 1:" not in context
        assert "similar questions" not in context

    def test_no_few_shot_section_when_empty_list(self) -> None:
        """No few-shot section when few_shot_examples is an empty list."""
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
            few_shot_examples=[],
        )

        assert "Example 1:" not in context
        assert "similar questions" not in context

    def test_sources_capped_at_five(self) -> None:
        """Only the first 5 sources are passed to fetch_source_text_fn."""
        sources = [f"Article_{i}" for i in range(10)]
        received_sources: list[list[str]] = []

        def tracking_fetch(src_list, question=""):
            received_sources.append(src_list)
            return ""

        build_synthesis_context(
            fetch_source_text_fn=tracking_fetch,
            question="test",
            kg_results=_make_kg_results(sources=sources),
            query_plan={"type": "entity_search"},
        )

        assert len(received_sources[0]) == 5

    def test_entities_capped_at_ten(self) -> None:
        """Only the first 10 entities appear in the prompt."""
        entities = [{"name": f"Entity_{i}"} for i in range(15)]
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="test",
            kg_results=_make_kg_results(entities=entities),
            query_plan={"type": "entity_search"},
        )

        assert "Entity_9" in context
        assert "Entity_10" not in context

    def test_facts_capped_at_ten(self) -> None:
        """Only the first 10 facts appear in the prompt."""
        facts = [f"Fact number {i}" for i in range(15)]
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="test",
            kg_results=_make_kg_results(facts=facts),
            query_plan={"type": "entity_search"},
        )

        assert "Fact number 9" in context
        assert "Fact number 10" not in context

    def test_handles_empty_kg_results(self) -> None:
        """Empty KG results produce a valid prompt string."""
        context = build_synthesis_context(
            fetch_source_text_fn=_noop_fetch,
            question="What is nothing?",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
        )

        assert "What is nothing?" in context
        assert "Sources:" in context
        assert isinstance(context, str)


# ===================================================================
# 2. synthesize_answer_minimal
# ===================================================================


class TestSynthesizeAnswerMinimal:
    """synthesize_answer_minimal: Claude-only answer, no KG context."""

    def test_happy_path_returns_text(self) -> None:
        """Successful API call returns the text from Claude's response."""
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("My own answer")
        tracker = MagicMock()

        result = synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="claude-test",
            synthesis_max_tokens=1024,
            track_response_fn=tracker,
            question="What is recursion?",
        )

        assert result == "My own answer"
        tracker.assert_called_once()

    def test_prompt_contains_question_and_no_relevant_content(self) -> None:
        """The prompt sent to Claude contains the question and the 'no relevant content' note."""
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("answer")
        tracker = MagicMock()

        synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="claude-test",
            synthesis_max_tokens=1024,
            track_response_fn=tracker,
            question="What is recursion?",
        )

        create_call = client.messages.create.call_args
        content = create_call.kwargs["messages"][0]["content"]
        assert "What is recursion?" in content
        assert "no relevant content" in content

    def test_uses_correct_model_and_max_tokens(self) -> None:
        """The API call uses the model and max_tokens passed as arguments."""
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("ok")

        synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="claude-3-haiku",
            synthesis_max_tokens=2048,
            track_response_fn=_noop_track,
            question="test",
        )

        create_call = client.messages.create.call_args
        assert create_call.kwargs["model"] == "claude-3-haiku"
        assert create_call.kwargs["max_tokens"] == 2048

    def test_api_connection_error_returns_fallback(self) -> None:
        """APIConnectionError returns the fallback string, does not raise."""
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )

        result = synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            question="test",
        )

        assert result == "Unable to answer: API error."

    def test_api_status_error_returns_fallback(self) -> None:
        """APIStatusError (e.g. 429) returns the fallback string."""
        client = MagicMock()
        mock_req = httpx.Request("POST", "https://api.anthropic.com")
        mock_resp = httpx.Response(429, request=mock_req, text="Too Many Requests")
        client.messages.create.side_effect = APIStatusError(
            "rate limited", response=mock_resp, body=None
        )

        result = synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            question="test",
        )

        assert result == "Unable to answer: API error."

    def test_api_timeout_error_returns_fallback(self) -> None:
        """APITimeoutError returns the fallback string."""
        client = MagicMock()
        client.messages.create.side_effect = APITimeoutError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )

        result = synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            question="test",
        )

        assert result == "Unable to answer: API error."

    def test_empty_response_returns_fallback(self) -> None:
        """Empty content list from Claude returns the empty-response fallback."""
        client = MagicMock()
        client.messages.create.return_value = _mock_empty_response()

        result = synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            question="test",
        )

        assert result == "Unable to synthesize answer: empty response from Claude."

    def test_tracker_not_called_on_api_error(self) -> None:
        """track_response_fn is not called when the API raises."""
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )
        tracker = MagicMock()

        synthesize_answer_minimal(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=tracker,
            question="test",
        )

        tracker.assert_not_called()


# ===================================================================
# 3. synthesize_answer
# ===================================================================


class TestSynthesizeAnswer:
    """synthesize_answer: full synthesis using KG results + Claude."""

    def test_happy_path_returns_text(self) -> None:
        """Successful API call returns the synthesized text."""
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("Synthesized answer")
        tracker = MagicMock()

        def build_ctx(question, kg_results, query_plan, few_shot_examples=None):
            return f"prompt for: {question}"

        result = synthesize_answer(
            claude_client=client,
            synthesis_model="claude-test",
            synthesis_max_tokens=1024,
            track_response_fn=tracker,
            build_synthesis_context_fn=build_ctx,
            question="What is gravity?",
            kg_results=_make_kg_results(sources=["Gravity"]),
            query_plan={"type": "entity_search"},
        )

        assert result == "Synthesized answer"
        tracker.assert_called_once()

    def test_error_in_kg_results_returns_error_message(self) -> None:
        """When kg_results contains 'error', return the error message immediately."""
        client = MagicMock()

        result = synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=lambda *a, **kw: "unused",
            question="test",
            kg_results=_make_kg_results(error="Cypher syntax error"),
            query_plan={"type": "entity_search"},
        )

        assert result == "Query execution failed: Cypher syntax error"
        client.messages.create.assert_not_called()

    def test_calls_build_synthesis_context_fn(self) -> None:
        """build_synthesis_context_fn is called with the correct arguments."""
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("ok")
        build_ctx = MagicMock(return_value="built prompt")

        kg = _make_kg_results(sources=["Python"])
        plan = {"type": "semantic_search"}
        examples = [{"question": "Q1", "answer": "A1"}]

        synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=build_ctx,
            question="What is Python?",
            kg_results=kg,
            query_plan=plan,
            few_shot_examples=examples,
        )

        build_ctx.assert_called_once_with("What is Python?", kg, plan, few_shot_examples=examples)

    def test_few_shot_defaults_to_empty_list(self) -> None:
        """When few_shot_examples is None, an empty list is passed to build_synthesis_context_fn."""
        client = MagicMock()
        client.messages.create.return_value = _mock_claude_response("ok")
        build_ctx = MagicMock(return_value="built prompt")

        synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=build_ctx,
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
            few_shot_examples=None,
        )

        _, kwargs = build_ctx.call_args
        assert kwargs["few_shot_examples"] == []

    def test_api_connection_error_returns_sources_fallback(self) -> None:
        """APIConnectionError returns a fallback string listing sources."""
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )

        result = synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(sources=["Article A", "Article B"]),
            query_plan={"type": "entity_search"},
        )

        assert result == "Found relevant sources: Article A, Article B"

    def test_api_error_no_sources_returns_no_results(self) -> None:
        """APIConnectionError with no sources returns 'No results found.'."""
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )

        result = synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
        )

        assert result == "No results found."

    def test_api_status_error_returns_fallback(self) -> None:
        """APIStatusError returns the sources fallback."""
        client = MagicMock()
        mock_req = httpx.Request("POST", "https://api.anthropic.com")
        mock_resp = httpx.Response(500, request=mock_req, text="Internal Server Error")
        client.messages.create.side_effect = APIStatusError(
            "server error", response=mock_resp, body=None
        )

        result = synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(sources=["Source1"]),
            query_plan={"type": "entity_search"},
        )

        assert result == "Found relevant sources: Source1"

    def test_api_timeout_error_returns_fallback(self) -> None:
        """APITimeoutError returns the sources fallback."""
        client = MagicMock()
        client.messages.create.side_effect = APITimeoutError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )

        result = synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(sources=["TimeoutSource"]),
            query_plan={"type": "entity_search"},
        )

        assert result == "Found relevant sources: TimeoutSource"

    def test_empty_response_returns_fallback(self) -> None:
        """Empty content list from Claude returns the empty-response fallback."""
        client = MagicMock()
        client.messages.create.return_value = _mock_empty_response()

        result = synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
        )

        assert result == "Unable to synthesize answer: empty response from Claude."

    def test_sources_fallback_caps_at_five(self) -> None:
        """API error fallback lists at most 5 sources."""
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )

        sources = [f"Source_{i}" for i in range(10)]
        result = synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=_noop_track,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(sources=sources),
            query_plan={"type": "entity_search"},
        )

        assert "Source_0" in result
        assert "Source_4" in result
        assert "Source_5" not in result

    def test_tracker_not_called_on_api_error(self) -> None:
        """track_response_fn is not called when the API raises."""
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        )
        tracker = MagicMock()

        synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=tracker,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(),
            query_plan={"type": "entity_search"},
        )

        tracker.assert_not_called()

    def test_tracker_not_called_on_kg_error(self) -> None:
        """track_response_fn is not called when kg_results has an error key."""
        client = MagicMock()
        tracker = MagicMock()

        synthesize_answer(
            claude_client=client,
            synthesis_model="mock",
            synthesis_max_tokens=1024,
            track_response_fn=tracker,
            build_synthesis_context_fn=lambda *a, **kw: "prompt",
            question="test",
            kg_results=_make_kg_results(error="boom"),
            query_plan={"type": "entity_search"},
        )

        tracker.assert_not_called()
        client.messages.create.assert_not_called()
