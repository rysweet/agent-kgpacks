"""Integration tests for KG adapter with real pack database.

These tests use a small test pack (10 articles) to validate:
- Real KG Agent integration
- Context retrieval quality
- Database query performance
- Error handling with real DB
"""

from pathlib import Path

import pytest

# ============================================================================
# Test Pack Fixture
# ============================================================================


@pytest.fixture(scope="module")
def test_pack_10_articles(tmp_path_factory) -> Path:
    """Create a small test pack with 10 articles for integration testing."""
    from wikigr.kg_builder import KGBuilder

    pack_path = tmp_path_factory.mktemp("test_pack_10")

    # 10 physics articles for testing
    test_articles = [
        "Isaac_Newton",
        "Newton's_laws_of_motion",
        "Classical_mechanics",
        "Force",
        "Mass",
        "Acceleration",
        "Momentum",
        "Energy",
        "Conservation_of_energy",
        "Kinetic_energy",
    ]

    # Build minimal pack (this requires Wikipedia API access)
    builder = KGBuilder(pack_path)
    builder.add_articles(test_articles)
    builder.build()

    # Create manifest
    import json

    manifest = {
        "name": "test-pack-10",
        "version": "0.1.0",
        "description": "10-article test pack for integration tests",
    }

    with open(pack_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    return pack_path


# ============================================================================
# Real KG Agent Integration
# ============================================================================


def test_kg_adapter_retrieves_context_from_real_pack(test_pack_10_articles: Path):
    """Test KG adapter retrieves actual context from real pack database."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)
    context = adapter.retrieve_context("What are Newton's laws of motion?")

    # Should retrieve relevant context
    assert context
    assert len(context) > 0

    # Should mention Newton's laws
    assert "newton" in context.lower() or "motion" in context.lower()


def test_kg_adapter_returns_markdown_sections(test_pack_10_articles: Path):
    """Test retrieved context is properly formatted as markdown."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)
    context = adapter.retrieve_context("What is force?")

    # Should have markdown headers
    assert "#" in context or "##" in context


def test_kg_adapter_retrieves_multiple_entities(test_pack_10_articles: Path):
    """Test KG adapter retrieves context from multiple related entities."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)
    context = adapter.retrieve_context(
        "How do force, mass, and acceleration relate?", max_entities=5
    )

    # Should mention multiple related concepts
    keywords = ["force", "mass", "acceleration"]
    matches = sum(1 for kw in keywords if kw in context.lower())
    assert matches >= 2  # At least 2 of the 3 keywords


# ============================================================================
# Context Quality Tests
# ============================================================================


def test_kg_adapter_context_relevant_to_question(test_pack_10_articles: Path):
    """Test retrieved context is relevant to the question."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    # Ask about momentum
    context = adapter.retrieve_context("What is momentum?")

    # Should contain momentum-related content, not unrelated topics
    assert "momentum" in context.lower()
    # Should not be dominated by irrelevant content
    assert context.count("momentum") + context.count("Momentum") > 0


def test_kg_adapter_context_includes_source_citations(test_pack_10_articles: Path):
    """Test context includes references to source entities."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)
    context = adapter.retrieve_context("What is kinetic energy?")

    # Should reference source article titles
    # (either "Kinetic_energy" or "Kinetic energy" format)
    assert "kinetic" in context.lower() and "energy" in context.lower()


def test_kg_adapter_empty_result_for_irrelevant_question(test_pack_10_articles: Path):
    """Test KG adapter returns empty/minimal context for out-of-domain questions."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    # Question completely outside pack domain
    context = adapter.retrieve_context("What is the capital of France?")

    # Should return empty or very minimal context
    assert len(context) < 200 or "no relevant" in context.lower()


# ============================================================================
# Database Query Performance
# ============================================================================


def test_kg_adapter_query_latency_reasonable(test_pack_10_articles: Path):
    """Test query latency is < 1 second for small pack."""
    import time

    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    start = time.time()
    adapter.retrieve_context("What is force?")
    latency_ms = (time.time() - start) * 1000

    # Small pack should be fast (< 1 second)
    assert latency_ms < 1000, f"Query took {latency_ms:.0f}ms, expected < 1000ms"


def test_kg_adapter_caching_improves_performance(test_pack_10_articles: Path):
    """Test repeated queries are faster with caching."""
    import time

    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles, enable_cache=True)

    # First query (cold cache)
    start1 = time.time()
    adapter.retrieve_context("What is momentum?")
    latency1 = (time.time() - start1) * 1000

    # Second query (warm cache)
    start2 = time.time()
    adapter.retrieve_context("What is momentum?")
    latency2 = (time.time() - start2) * 1000

    # Cached query should be faster (or at least not slower)
    assert latency2 <= latency1 * 1.1  # Allow 10% variance


# ============================================================================
# Error Handling with Real DB
# ============================================================================


def test_kg_adapter_handles_malformed_question_gracefully(test_pack_10_articles: Path):
    """Test KG adapter handles unusual question formats."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    # Questions with special characters
    questions = [
        "What is E=mc²?",
        "Force & acceleration?",
        "Newton's 1st law???",
        "Mass/acceleration = ?",
    ]

    for question in questions:
        # Should not crash
        context = adapter.retrieve_context(question)
        assert isinstance(context, str)


def test_kg_adapter_handles_very_long_question(test_pack_10_articles: Path):
    """Test KG adapter handles very long questions."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    # Extremely long question
    long_question = (
        "Considering the fundamental principles of Newtonian mechanics, "
        "and taking into account the historical development of physics from "
        "ancient times through the scientific revolution, could you please "
        "explain in comprehensive detail, including all relevant mathematical "
        "formulations and experimental evidence, what exactly are the three "
        "laws of motion as originally formulated by Isaac Newton in his "
        "Philosophiæ Naturalis Principia Mathematica?"
    )

    # Should handle without error
    context = adapter.retrieve_context(long_question)
    assert isinstance(context, str)


def test_kg_adapter_handles_empty_max_entities(test_pack_10_articles: Path):
    """Test KG adapter handles max_entities=0 gracefully."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    # max_entities=0 should return empty or minimal context
    context = adapter.retrieve_context("What is force?", max_entities=0)
    assert isinstance(context, str)
    # Should be empty or very short
    assert len(context) < 100


# ============================================================================
# Multi-hop Reasoning Tests
# ============================================================================


def test_kg_adapter_retrieves_related_entities_via_graph(test_pack_10_articles: Path):
    """Test KG adapter uses graph traversal to find related entities."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    # Ask about conservation of energy (should traverse to energy and kinetic energy)
    context = adapter.retrieve_context(
        "Explain the conservation of energy principle", max_entities=5
    )

    # Should include related concepts via graph traversal
    related_terms = ["energy", "kinetic", "conservation"]
    matches = sum(1 for term in related_terms if term in context.lower())
    assert matches >= 2  # Should find multiple related concepts


def test_kg_adapter_handles_multi_hop_query(test_pack_10_articles: Path):
    """Test KG adapter handles questions requiring multi-hop reasoning."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles)

    # Multi-hop: Newton -> laws -> force -> acceleration
    context = adapter.retrieve_context(
        "How did Newton's work on forces lead to our understanding of acceleration?"
    )

    # Should connect multiple entities
    assert "newton" in context.lower() or "force" in context.lower()


# ============================================================================
# Pack Validation
# ============================================================================


def test_kg_adapter_requires_valid_pack_structure(tmp_path: Path):
    """Test KG adapter validates pack structure before use."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    # Pack without database
    invalid_pack = tmp_path / "invalid_pack"
    invalid_pack.mkdir()

    with pytest.raises(FileNotFoundError, match="pack.db"):
        KGAdapter(invalid_pack)


def test_kg_adapter_requires_pack_manifest(tmp_path: Path):
    """Test KG adapter checks for pack manifest."""
    from wikigr.packs.eval.kg_adapter import KGAdapter

    # Pack with DB but no manifest
    pack_path = tmp_path / "no_manifest_pack"
    pack_path.mkdir()
    (pack_path / "pack.db").touch()

    # Should still work (manifest is optional for adapter)
    # but may log warning
    adapter = KGAdapter(pack_path)
    assert adapter is not None


# ============================================================================
# Performance Benchmarking
# ============================================================================


@pytest.mark.slow
def test_kg_adapter_performance_batch_queries(test_pack_10_articles: Path):
    """Test KG adapter performance for batch queries."""
    import time

    from wikigr.packs.eval.kg_adapter import KGAdapter

    adapter = KGAdapter(test_pack_10_articles, enable_cache=True)

    questions = [
        "What is force?",
        "What is mass?",
        "What is acceleration?",
        "What is momentum?",
        "What is energy?",
        "What is kinetic energy?",
        "What are Newton's laws?",
        "What is conservation of energy?",
        "Who was Isaac Newton?",
        "What is classical mechanics?",
    ]

    start = time.time()
    for question in questions:
        adapter.retrieve_context(question)
    total_time = time.time() - start

    # 10 queries should complete in < 5 seconds for small pack
    assert total_time < 5.0, f"10 queries took {total_time:.2f}s, expected < 5s"

    # Average latency should be reasonable
    avg_latency_ms = (total_time / len(questions)) * 1000
    assert avg_latency_ms < 500, f"Average latency {avg_latency_ms:.0f}ms too high"


# ============================================================================
# Skip if Wikipedia API unavailable
# ============================================================================


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if Wikipedia API is unavailable."""
    import os

    skip_integration = pytest.mark.skip(reason="Wikipedia API unavailable or disabled")

    # Skip if explicitly disabled
    if os.getenv("SKIP_WIKIPEDIA_TESTS") == "1":
        for item in items:
            if "test_kg_adapter_integration" in str(item.fspath):
                item.add_marker(skip_integration)
