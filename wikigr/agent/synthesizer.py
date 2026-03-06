"""Synthesis functions extracted from KnowledgeGraphAgent.

All functions take explicit parameters instead of ``self``, enabling
independent testing and reuse.  The parent ``KnowledgeGraphAgent`` class
wraps each function so that its public (and private) method API is
unchanged.
"""

from __future__ import annotations

import json
import logging

from anthropic import APIConnectionError, APIStatusError, APITimeoutError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Build synthesis context
# ---------------------------------------------------------------------------


def build_synthesis_context(
    fetch_source_text_fn,
    question: str,
    kg_results: dict,
    query_plan: dict,
    few_shot_examples: list[dict] | None = None,
) -> str:
    """Build the synthesis prompt for Claude (used by both blocking and streaming).

    Includes both structured KG results (entities, facts, triples) AND
    the original article section text for grounded, accurate synthesis.
    Optionally includes few-shot examples when Phase 1 enhancements are enabled.

    Args:
        fetch_source_text_fn: Callable(source_titles, question=question) -> str.
        question: User question.
        kg_results: Dictionary with sources, entities, facts, raw results.
        query_plan: Dictionary with type and other plan metadata.
        few_shot_examples: Optional list of few-shot example dicts.

    Returns:
        Full synthesis prompt string for Claude.
    """
    sources = kg_results.get("sources", [])[:5]

    # Fetch original article text for grounded synthesis (with quality filtering)
    source_text = fetch_source_text_fn(sources, question=question)

    # Build few-shot examples section if provided
    few_shot_section = ""
    if few_shot_examples:
        few_shot_section = "\nHere are similar questions and their answers:\n\n"
        for i, example in enumerate(few_shot_examples[:3], 1):
            few_shot_section += f"Example {i}:\n"
            few_shot_section += f"Q: {example.get('question', example.get('query', ''))}\n"
            few_shot_section += f"A: {example.get('answer', example.get('ground_truth', ''))}\n\n"

    context = f"""Query Type: {query_plan["type"]}

Sources: {", ".join(sources)}

Entities found: {json.dumps(kg_results.get("entities", [])[:10], indent=2)}

Facts:
{chr(10).join(f"- {fact}" for fact in kg_results.get("facts", [])[:10])}

Raw results: {json.dumps(kg_results.get("raw", [])[:5], indent=2, default=str)}
"""

    # Add original text if available
    if source_text:
        context += f"""
Original Article Text (for grounding):
{source_text}
"""

    return f"""{few_shot_section}You are a knowledgeable expert. Answer the question below using BOTH your own expertise AND the retrieved content from a knowledge graph.

When the retrieved content provides specific, detailed, or up-to-date information, prefer it and cite the source articles. When the retrieved content is limited or irrelevant, draw on your own knowledge to provide the best possible answer.

Question: {question}

Retrieved Knowledge Graph Content:
{context}

Provide a clear, accurate, comprehensive answer. Cite source articles when you use retrieved content."""


# ---------------------------------------------------------------------------
# Minimal synthesis (no pack context)
# ---------------------------------------------------------------------------


def synthesize_answer_minimal(
    claude_client,
    synthesis_model: str,
    synthesis_max_tokens: int,
    track_response_fn,
    question: str,
) -> str:
    """Synthesize answer using Claude's own knowledge when pack has no relevant content.

    Args:
        claude_client: Anthropic client instance.
        synthesis_model: Model identifier for Claude.
        synthesis_max_tokens: Maximum tokens for synthesis response.
        track_response_fn: Callable to track token usage from API responses.
        question: User question.

    Returns:
        Answer string.
    """
    prompt = (
        "The knowledge pack for this query contained no relevant content. "
        "Answer the following question using your own expertise:\n\n"
        f"Question: {question}"
    )
    try:
        response = claude_client.messages.create(
            model=synthesis_model,
            max_tokens=synthesis_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        track_response_fn(response)
    except (APIConnectionError, APIStatusError, APITimeoutError) as e:
        logger.warning(f"Claude API error in _synthesize_answer_minimal: {e}")
        return "Unable to answer: API error."

    if not response.content:
        return "Unable to synthesize answer: empty response from Claude."

    return response.content[0].text


# ---------------------------------------------------------------------------
# Full synthesis
# ---------------------------------------------------------------------------


def synthesize_answer(
    claude_client,
    synthesis_model: str,
    synthesis_max_tokens: int,
    track_response_fn,
    build_synthesis_context_fn,
    question: str,
    kg_results: dict,
    query_plan: dict,
    few_shot_examples: list[dict] | None = None,
) -> str:
    """Use Claude to synthesize natural language answer from KG results.

    Args:
        claude_client: Anthropic client instance.
        synthesis_model: Model identifier for Claude.
        synthesis_max_tokens: Maximum tokens for synthesis response.
        track_response_fn: Callable to track token usage from API responses.
        build_synthesis_context_fn: Callable to build the full synthesis prompt.
        question: User question.
        kg_results: Dictionary with sources, entities, facts, raw results.
        query_plan: Dictionary with type and other plan metadata.
        few_shot_examples: Optional list of few-shot example dicts.

    Returns:
        Answer string.
    """
    # Handle error case
    if "error" in kg_results:
        return f"Query execution failed: {kg_results['error']}"

    prompt = build_synthesis_context_fn(
        question, kg_results, query_plan, few_shot_examples=few_shot_examples or []
    )

    try:
        response = claude_client.messages.create(
            model=synthesis_model,
            max_tokens=synthesis_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        track_response_fn(response)
    except (APIConnectionError, APIStatusError, APITimeoutError) as e:
        logger.warning(f"Claude API error in _synthesize_answer: {e}")
        sources = ", ".join(kg_results.get("sources", [])[:5])
        return f"Found relevant sources: {sources}" if sources else "No results found."

    if not response.content:
        return "Unable to synthesize answer: empty response from Claude."

    return response.content[0].text
