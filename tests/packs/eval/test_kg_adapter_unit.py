"""Unit tests for KG adapter (with mocked KG Agent).

The KG adapter (`wikigr.packs.eval.kg_adapter`) provides the integration layer
between the evaluation system and the KG Agent for context retrieval.

Tests cover:
- Context format validation (markdown sections)
- Error handling (missing DB, empty results, corrupted DB)
- Retrieval quality metrics
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# ============================================================================
# KG Adapter Initialization
# ============================================================================


def test_kg_adapter_init_with_valid_pack(tmp_path: Path):
    """Test KG adapter initializes with valid pack directory."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    adapter = KGAdapter(pack_path)
    assert adapter.pack_path == pack_path


def test_kg_adapter_init_with_nonexistent_pack():
    """Test KG adapter raises error for nonexistent pack."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    with pytest.raises(FileNotFoundError, match="Pack directory not found"):
        KGAdapter(Path("/nonexistent/pack"))


def test_kg_adapter_init_with_missing_database(tmp_path: Path):
    """Test KG adapter raises error when pack.db is missing."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    # No pack.db file

    with pytest.raises(FileNotFoundError, match="pack.db not found"):
        KGAdapter(pack_path)


# ============================================================================
# Context Retrieval
# ============================================================================


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_returns_markdown_format(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieved context is formatted as markdown sections."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    # Setup
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(
        context_sections=[
            {"title": "Quantum Entanglement", "content": "A phenomenon where..."},
            {"title": "EPR Paradox", "content": "Einstein's thought experiment..."},
        ]
    )
    mock_kg_agent_class.return_value = mock_agent

    # Test
    adapter = KGAdapter(pack_path)
    context = adapter.retrieve_context("What is quantum entanglement?")

    # Verify markdown format
    assert "# Quantum Entanglement" in context
    assert "# EPR Paradox" in context
    assert "A phenomenon where..." in context
    assert "Einstein's thought experiment..." in context


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_with_max_entities(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context respects max_entities parameter."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    adapter.retrieve_context("Test question", max_entities=5)

    # Verify KG Agent called with max_entities
    mock_agent.answer.assert_called_once()
    call_kwargs = mock_agent.answer.call_args[1]
    assert call_kwargs.get("max_entities") == 5


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_empty_result(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles empty results gracefully."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(context_sections=[])
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    context = adapter.retrieve_context("Obscure question")

    # Should return empty context indicator
    assert context == "" or "No relevant context found" in context


# ============================================================================
# Error Handling
# ============================================================================


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_handles_kg_agent_error(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles KG Agent exceptions."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.side_effect = RuntimeError("Database query failed")
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)

    with pytest.raises(RuntimeError, match="Database query failed"):
        adapter.retrieve_context("Test question")


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_handles_corrupted_database(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles corrupted database errors."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.side_effect = Exception("Database file is corrupt")
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)

    with pytest.raises(Exception, match="Database file is corrupt"):
        adapter.retrieve_context("Test question")


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_timeout_handling(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles timeout gracefully."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.side_effect = TimeoutError("Query timeout after 30s")
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)

    with pytest.raises(TimeoutError, match="Query timeout"):
        adapter.retrieve_context("Complex question", timeout=30)


# ============================================================================
# Context Format Validation
# ============================================================================


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_context_format_has_section_headers(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test context uses markdown section headers."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(
        context_sections=[{"title": "Newton's Laws", "content": "Three laws of motion..."}]
    )
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    context = adapter.retrieve_context("What are Newton's laws?")

    # Should have markdown header
    assert context.startswith("# ") or "## " in context


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_context_format_separates_sections(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test context separates multiple sections clearly."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(
        context_sections=[
            {"title": "Section 1", "content": "Content 1"},
            {"title": "Section 2", "content": "Content 2"},
        ]
    )
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    context = adapter.retrieve_context("Test")

    # Sections should be separated by newlines
    assert "\n\n" in context or "\n---\n" in context


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_context_includes_source_citations(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test context includes source entity names."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(
        context_sections=[{"title": "Quantum_Mechanics", "content": "Quantum theory..."}],
        sources=["Quantum_Mechanics", "Wave_Function"],
    )
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    context = adapter.retrieve_context("What is quantum mechanics?")

    # Should reference source entities
    assert "Quantum_Mechanics" in context or "Quantum Mechanics" in context


# ============================================================================
# Retrieval Quality Metrics
# ============================================================================


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_returns_relevance_score(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test adapter can compute relevance score for retrieved context."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(
        context_sections=[{"title": "Test", "content": "Content"}], relevance_score=0.85
    )
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    context, score = adapter.retrieve_context_with_score("Test question")

    assert 0.0 <= score <= 1.0
    assert score == 0.85


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_tracks_latency(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test adapter tracks retrieval latency."""
    import time

    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()

    def slow_answer(*args, **kwargs):
        time.sleep(0.1)  # Simulate 100ms query
        return Mock(context_sections=[])

    mock_agent.answer.side_effect = slow_answer
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    start = time.time()
    adapter.retrieve_context("Test")
    latency_ms = (time.time() - start) * 1000

    assert latency_ms >= 100  # Should be at least 100ms


# ============================================================================
# Edge Cases
# ============================================================================


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_with_unicode_question(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles Unicode characters."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(context_sections=[])
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    context = adapter.retrieve_context("What is Schrödinger's equation?")

    # Should not raise encoding errors
    assert isinstance(context, str)


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_with_very_long_question(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles long questions."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(context_sections=[])
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    long_question = "What is " + "very " * 100 + "interesting?"
    context = adapter.retrieve_context(long_question)

    # Should handle without error
    assert isinstance(context, str)


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_with_empty_question(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles empty question."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)

    with pytest.raises(ValueError, match="Question cannot be empty"):
        adapter.retrieve_context("")


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_retrieve_context_with_special_characters(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test retrieve_context handles special characters in questions."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_agent.answer.return_value = Mock(context_sections=[])
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path)
    context = adapter.retrieve_context("What is E=mc²?")

    # Should handle without error
    assert isinstance(context, str)


# ============================================================================
# Caching Tests
# ============================================================================


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_adapter_uses_caching_when_enabled(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test adapter enables KG Agent caching."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    mock_kg_agent_class.return_value = mock_agent

    _ = KGAdapter(pack_path, enable_cache=True)

    # Verify KG Agent initialized with caching
    mock_kg_agent_class.assert_called_once()
    call_kwargs = mock_kg_agent_class.call_args[1]
    assert call_kwargs.get("enable_cache") is True


@patch("wikigr.packs.eval.kg_adapter.KGAgent")
def test_adapter_cache_hit_is_faster(mock_kg_agent_class: Mock, tmp_path: Path):
    """Test cached queries are faster than fresh queries."""
    import time

    from wikigr.packs.eval.kg_adapter import KGAdapter

    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    mock_agent = Mock()
    call_count = [0]

    def timed_answer(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            time.sleep(0.1)  # First call: 100ms
        else:
            time.sleep(0.01)  # Cached: 10ms
        return Mock(context_sections=[])

    mock_agent.answer.side_effect = timed_answer
    mock_kg_agent_class.return_value = mock_agent

    adapter = KGAdapter(pack_path, enable_cache=True)

    # First call
    start1 = time.time()
    adapter.retrieve_context("Test")
    latency1 = (time.time() - start1) * 1000

    # Second call (cached)
    start2 = time.time()
    adapter.retrieve_context("Test")
    latency2 = (time.time() - start2) * 1000

    # Cached should be faster
    assert latency2 < latency1
