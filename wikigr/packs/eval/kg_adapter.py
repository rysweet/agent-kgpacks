"""Knowledge Graph adapter for pack evaluation.

This module provides integration between the knowledge pack evaluator and
the WikiGR KG Agent, enabling real knowledge graph retrieval during evaluation.
"""

import logging
from pathlib import Path

from wikigr.agent.kg_agent import KnowledgeGraphAgent

logger = logging.getLogger(__name__)

# Maximum question length (10KB)
MAX_QUESTION_LENGTH = 10000


def validate_question(question: str) -> str:
    """Validate and sanitize question input.

    Args:
        question: Question text to validate

    Returns:
        Sanitized question text

    Raises:
        ValueError: If question is empty or exceeds maximum length
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"Question exceeds maximum length of {MAX_QUESTION_LENGTH} characters")

    return question.strip()


def retrieve_from_pack(question: str, pack_path: Path, top_k: int = 5) -> str:
    """Retrieve context from pack's knowledge graph using KG Agent.

    Args:
        question: Natural language question to retrieve context for
        pack_path: Path to knowledge pack directory
        top_k: Maximum number of results to retrieve

    Returns:
        Formatted markdown context for LLM consumption

    Raises:
        ValueError: If question is invalid
        FileNotFoundError: If pack database doesn't exist
    """
    # Validate question input
    question = validate_question(question)

    db_path = pack_path / "pack.db"
    if not db_path.exists():
        logger.error(f"KG retrieval failed: Database not found at {db_path}")
        raise FileNotFoundError("Knowledge graph unavailable. Please check configuration.")

    # Query KG agent with read-only access
    try:
        with KnowledgeGraphAgent(db_path=str(db_path), read_only=True) as kg_agent:
            result = kg_agent.query(question, max_results=top_k)
            return format_context_as_markdown(result)
    except FileNotFoundError:
        # Re-raise with sanitized message
        raise
    except Exception as e:
        logger.error(f"KG retrieval failed: {e}", exc_info=True)
        return "An error occurred while retrieving context. Please try again later."


def format_context_as_markdown(result: dict) -> str:
    """Format KG Agent results as markdown for LLM consumption.

    Args:
        result: Dictionary from KG Agent containing answer, sources, entities, facts

    Returns:
        Formatted markdown string with all context information
    """
    parts = []

    # Add sources (article titles)
    sources = result.get("sources", [])
    if sources:
        parts.append("## Sources")
        for source in sources[:10]:
            parts.append(f"- {source}")
        parts.append("")

    # Add entities found
    entities = result.get("entities", [])
    if entities:
        parts.append("## Entities")
        for entity in entities[:10]:
            name = entity.get("name", "Unknown")
            entity_type = entity.get("type", "unknown")
            parts.append(f"- **{name}** ({entity_type})")
        parts.append("")

    # Add facts/relationships
    facts = result.get("facts", [])
    if facts:
        parts.append("## Facts")
        for fact in facts[:15]:
            # Clean up fact text
            fact_text = str(fact).strip()
            if fact_text:
                parts.append(f"- {fact_text}")
        parts.append("")

    # Add Cypher query for transparency
    cypher = result.get("cypher_query", "")
    query_type = result.get("query_type", "unknown")
    if cypher:
        parts.append("## Query Details")
        parts.append(f"Query Type: {query_type}")
        parts.append("```cypher")
        parts.append(cypher)
        parts.append("```")
        parts.append("")

    return "\n".join(parts) if parts else "No context found in knowledge graph."
