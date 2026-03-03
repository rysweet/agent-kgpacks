"""Tests for hive mind trust-weighted retrieval.

Covers trust_weighted_score formula, hybrid_score with source_trust,
and query_facts with/without agent trust data.
"""

import pytest

from wikigr.agent.hive_mind.reranker import (
    get_agent_trust,
    hybrid_score,
    query_facts,
    set_agent_trust,
    trust_weighted_score,
)


class TestTrustWeightedScore:
    """Test trust_weighted_score() formula: sim * trust + confidence * 0.01."""

    def test_basic_formula(self):
        """score = semantic_similarity * source_agent_trust + confidence * 0.01"""
        result = trust_weighted_score(
            semantic_similarity=0.8,
            source_agent_trust=0.9,
            confidence=0.5,
        )
        expected = 0.8 * 0.9 + 0.5 * 0.01  # 0.72 + 0.005 = 0.725
        assert result == pytest.approx(expected)

    def test_zero_trust(self):
        """Zero trust should give only the confidence component."""
        result = trust_weighted_score(0.9, 0.0, 0.5)
        assert result == pytest.approx(0.005)  # 0 + 0.5 * 0.01

    def test_full_trust_full_similarity(self):
        """Perfect similarity and trust."""
        result = trust_weighted_score(1.0, 1.0, 1.0)
        assert result == pytest.approx(1.01)  # 1.0 * 1.0 + 1.0 * 0.01

    def test_zero_similarity(self):
        """Zero similarity, only confidence contributes."""
        result = trust_weighted_score(0.0, 0.9, 0.8)
        assert result == pytest.approx(0.008)  # 0 + 0.8 * 0.01

    def test_zero_confidence(self):
        """Zero confidence gives only similarity * trust."""
        result = trust_weighted_score(0.7, 0.6, 0.0)
        assert result == pytest.approx(0.42)  # 0.7 * 0.6 + 0


class TestHybridScore:
    """Test hybrid_score() with source_trust parameter."""

    def test_default_source_trust(self):
        """Default source_trust=1.0 should not affect score."""
        result = hybrid_score(keyword_score=0.5, vector_score=0.8)
        expected = 0.5 * 0.3 + 0.8 * 0.7  # 0.15 + 0.56 = 0.71
        assert result == pytest.approx(expected)

    def test_source_trust_scales_score(self):
        """source_trust=0.5 should halve the base score."""
        full = hybrid_score(keyword_score=0.5, vector_score=0.8, source_trust=1.0)
        half = hybrid_score(keyword_score=0.5, vector_score=0.8, source_trust=0.5)
        assert half == pytest.approx(full * 0.5)

    def test_zero_source_trust(self):
        """Zero trust gives zero score."""
        result = hybrid_score(keyword_score=0.9, vector_score=0.9, source_trust=0.0)
        assert result == pytest.approx(0.0)

    def test_custom_weights_with_trust(self):
        """Custom weights combined with source_trust."""
        result = hybrid_score(
            keyword_score=0.6,
            vector_score=0.4,
            keyword_weight=0.5,
            vector_weight=0.5,
            source_trust=0.8,
        )
        base = 0.6 * 0.5 + 0.4 * 0.5  # 0.5
        assert result == pytest.approx(base * 0.8)  # 0.4


class TestQueryFacts:
    """Test query_facts() scoring with/without agent trust data."""

    def test_facts_scored_by_trust_weighted(self):
        """Facts should be scored using trust_weighted_score formula."""
        facts = [
            {"fact_id": "a", "semantic_similarity": 0.9, "confidence": 0.8},
            {"fact_id": "b", "semantic_similarity": 0.5, "confidence": 0.5},
        ]
        results = query_facts(None, facts)
        assert results[0]["fact_id"] == "a"
        assert results[0]["score"] > results[1]["score"]

    def test_agent_trust_used_when_available(self):
        """Facts with agent_id should use registered trust scores."""
        set_agent_trust("trusted_agent", 1.0)
        set_agent_trust("untrusted_agent", 0.1)

        facts = [
            {"fact_id": "a", "semantic_similarity": 0.8, "confidence": 0.5, "agent_id": "untrusted_agent"},
            {"fact_id": "b", "semantic_similarity": 0.8, "confidence": 0.5, "agent_id": "trusted_agent"},
        ]
        results = query_facts(None, facts)
        # Same similarity and confidence, but b has higher trust
        assert results[0]["fact_id"] == "b"

    def test_default_trust_when_no_agent_id(self):
        """Facts without agent_id should use default trust of 1.0."""
        facts = [
            {"fact_id": "a", "semantic_similarity": 0.8, "confidence": 0.5},
        ]
        results = query_facts(None, facts)
        expected_score = 0.8 * 1.0 + 0.5 * 0.01  # 0.805
        assert results[0]["score"] == pytest.approx(expected_score)

    def test_top_k_limits_results(self):
        """query_facts should return at most top_k results."""
        facts = [
            {"fact_id": f"f{i}", "semantic_similarity": 0.5, "confidence": 0.5}
            for i in range(20)
        ]
        results = query_facts(None, facts, top_k=5)
        assert len(results) == 5


class TestAgentTrustRegistry:
    """Test agent trust set/get."""

    def test_set_and_get_trust(self):
        set_agent_trust("agent_x", 0.75)
        assert get_agent_trust("agent_x") == pytest.approx(0.75)

    def test_default_trust(self):
        assert get_agent_trust("nonexistent") == pytest.approx(1.0)

    def test_trust_clamped(self):
        set_agent_trust("agent_clamp", 1.5)
        assert get_agent_trust("agent_clamp") == pytest.approx(1.0)
        set_agent_trust("agent_clamp", -0.5)
        assert get_agent_trust("agent_clamp") == pytest.approx(0.0)
