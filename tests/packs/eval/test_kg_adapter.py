"""Tests for KG adapter (with mocking)."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wikigr.packs.eval.kg_adapter import format_context_as_markdown, retrieve_from_pack


def test_retrieve_from_pack_no_database(tmp_path: Path):
    """Test retrieve_from_pack raises FileNotFoundError when pack.db missing."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()

    with pytest.raises(FileNotFoundError, match="Knowledge graph unavailable"):
        retrieve_from_pack("What is gravity?", pack_path)


@patch("wikigr.packs.eval.kg_adapter.KnowledgeGraphAgent")
def test_retrieve_from_pack_success(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test successful KG retrieval and formatting."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    db_path = pack_path / "pack.db"
    db_path.touch()

    # Mock KG agent result
    mock_agent = Mock()
    mock_agent.query.return_value = {
        "answer": "Gravity is a force",
        "sources": ["Isaac Newton", "Albert Einstein"],
        "entities": [
            {"name": "Gravity", "type": "concept"},
            {"name": "Force", "type": "concept"},
        ],
        "facts": [
            "Gravity attracts objects",
            "Einstein improved Newton's theory",
        ],
        "cypher_query": "MATCH (e:Entity) WHERE e.name = 'Gravity' RETURN e",
        "query_type": "entity_search",
    }
    mock_agent.__enter__ = Mock(return_value=mock_agent)
    mock_agent.__exit__ = Mock(return_value=False)
    mock_kg_agent_class.return_value = mock_agent

    # Test
    context = retrieve_from_pack("What is gravity?", pack_path, top_k=5)

    # Verify KG agent was called correctly
    mock_kg_agent_class.assert_called_once_with(db_path=str(db_path), read_only=True)
    mock_agent.query.assert_called_once_with("What is gravity?", max_results=5)

    # Verify formatted context
    assert "## Sources" in context
    assert "Isaac Newton" in context
    assert "Albert Einstein" in context
    assert "## Entities" in context
    assert "**Gravity**" in context
    assert "## Facts" in context
    assert "Gravity attracts objects" in context
    assert "## Query Details" in context
    assert "entity_search" in context


@patch("wikigr.packs.eval.kg_adapter.KnowledgeGraphAgent")
def test_retrieve_from_pack_error_handling(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test error handling when KG query fails."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    db_path = pack_path / "pack.db"
    db_path.touch()

    # Mock KG agent to raise exception
    mock_agent = Mock()
    mock_agent.query.side_effect = RuntimeError("Database error")
    mock_agent.__enter__ = Mock(return_value=mock_agent)
    mock_agent.__exit__ = Mock(return_value=False)
    mock_kg_agent_class.return_value = mock_agent

    # Test
    context = retrieve_from_pack("What is gravity?", pack_path)

    # Should return sanitized error message, not raise or expose details
    assert "An error occurred while retrieving context" in context


def test_format_context_as_markdown_complete():
    """Test formatting with all fields present."""
    result = {
        "answer": "Test answer",
        "sources": ["Article1", "Article2", "Article3"],
        "entities": [
            {"name": "Entity1", "type": "person"},
            {"name": "Entity2", "type": "place"},
        ],
        "facts": ["Fact 1", "Fact 2", "Fact 3"],
        "cypher_query": "MATCH (e:Entity) RETURN e",
        "query_type": "entity_search",
    }

    markdown = format_context_as_markdown(result)

    assert "## Sources" in markdown
    assert "- Article1" in markdown
    assert "## Entities" in markdown
    assert "**Entity1** (person)" in markdown
    assert "## Facts" in markdown
    assert "- Fact 1" in markdown
    assert "## Query Details" in markdown
    assert "Query Type: entity_search" in markdown
    assert "```cypher" in markdown


def test_format_context_as_markdown_empty():
    """Test formatting with empty result."""
    result = {
        "sources": [],
        "entities": [],
        "facts": [],
    }

    markdown = format_context_as_markdown(result)
    assert markdown == "No context found in knowledge graph."


def test_format_context_as_markdown_partial():
    """Test formatting with only some fields present."""
    result = {
        "sources": ["Article1"],
        "entities": [],
        "facts": [],
    }

    markdown = format_context_as_markdown(result)

    assert "## Sources" in markdown
    assert "- Article1" in markdown
    assert "## Entities" not in markdown
    assert "## Facts" not in markdown


def test_format_context_as_markdown_truncation():
    """Test that long lists are truncated appropriately."""
    # Generate many sources, entities, facts
    result = {
        "sources": [f"Article{i}" for i in range(20)],
        "entities": [{"name": f"Entity{i}", "type": "test"} for i in range(20)],
        "facts": [f"Fact {i}" for i in range(30)],
        "cypher_query": "MATCH (n) RETURN n",
        "query_type": "test",
    }

    markdown = format_context_as_markdown(result)

    # Should truncate sources to 10
    assert "Article9" in markdown
    assert "Article10" not in markdown

    # Should truncate entities to 10
    assert "Entity9" in markdown
    assert "Entity10" not in markdown

    # Should truncate facts to 15
    assert "Fact 14" in markdown
    assert "Fact 15" not in markdown
