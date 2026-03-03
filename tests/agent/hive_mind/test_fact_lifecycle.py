"""Tests for fact TTL, confidence decay, garbage collection, and refresh.

Covers:
- TTL expiry detection
- Exponential confidence decay
- GC sweep removing expired facts
- Confidence refresh for re-validated facts
- Integration with InMemoryHiveGraph enable_ttl
"""

import time

import pytest

from wikigr.agent.hive_mind.fact_lifecycle import (
    FactTTL,
    decay_confidence,
    gc_expired_facts,
    refresh_confidence,
)
from wikigr.agent.hive_mind.hive_graph import InMemoryHiveGraph


class TestFactTTL:
    """Test FactTTL dataclass and expiry detection."""

    def test_not_expired_when_fresh(self):
        """A newly created fact should not be expired."""
        fact = FactTTL(fact_id="f1", created_at=time.time(), ttl_seconds=3600)
        assert not fact.is_expired()

    def test_expired_after_ttl(self):
        """A fact should be expired after its TTL passes."""
        now = time.time()
        fact = FactTTL(fact_id="f1", created_at=now - 100, ttl_seconds=50)
        assert fact.is_expired(now)

    def test_expires_at_property(self):
        """expires_at should equal created_at + ttl_seconds."""
        fact = FactTTL(fact_id="f1", created_at=1000.0, ttl_seconds=500.0)
        assert fact.expires_at == pytest.approx(1500.0)

    def test_boundary_not_expired(self):
        """Fact at exact TTL boundary (now < expires_at) is not expired."""
        fact = FactTTL(fact_id="f1", created_at=1000.0, ttl_seconds=100.0)
        assert not fact.is_expired(now=1099.9)

    def test_boundary_expired(self):
        """Fact at exact TTL boundary (now == expires_at) is expired."""
        fact = FactTTL(fact_id="f1", created_at=1000.0, ttl_seconds=100.0)
        assert fact.is_expired(now=1100.0)


class TestDecayConfidence:
    """Test exponential confidence decay."""

    def test_no_decay_at_zero_elapsed(self):
        """Zero elapsed time should not change confidence."""
        fact = FactTTL(fact_id="f1", confidence=0.9)
        result = decay_confidence(fact, elapsed_seconds=0.0)
        assert result == pytest.approx(0.9)

    def test_confidence_decreases_over_time(self):
        """Confidence should decrease with elapsed time."""
        fact = FactTTL(fact_id="f1", confidence=1.0, decay_rate=0.01)
        result = decay_confidence(fact, elapsed_seconds=100.0)
        assert result < 1.0
        assert result > 0.0

    def test_decay_updates_fact_in_place(self):
        """decay_confidence should update fact.confidence in place."""
        fact = FactTTL(fact_id="f1", confidence=0.8, decay_rate=0.001)
        decay_confidence(fact, elapsed_seconds=50.0)
        assert fact.confidence < 0.8

    def test_large_elapsed_approaches_zero(self):
        """Very large elapsed time should bring confidence near zero."""
        fact = FactTTL(fact_id="f1", confidence=1.0, decay_rate=0.1)
        result = decay_confidence(fact, elapsed_seconds=1000.0)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_decay_never_goes_negative(self):
        """Confidence should never go below 0."""
        fact = FactTTL(fact_id="f1", confidence=0.5, decay_rate=1.0)
        result = decay_confidence(fact, elapsed_seconds=10000.0)
        assert result >= 0.0


class TestGCExpiredFacts:
    """Test garbage collection sweep."""

    def test_removes_expired_facts(self):
        """GC should remove expired facts."""
        now = 2000.0
        facts = [
            FactTTL(fact_id="alive", created_at=1900.0, ttl_seconds=200.0),
            FactTTL(fact_id="dead", created_at=1000.0, ttl_seconds=500.0),
        ]
        result = gc_expired_facts(facts, now=now)
        assert len(result) == 1
        assert result[0].fact_id == "alive"

    def test_keeps_all_fresh_facts(self):
        """GC should not remove non-expired facts."""
        now = 1000.0
        facts = [
            FactTTL(fact_id="f1", created_at=900.0, ttl_seconds=200.0),
            FactTTL(fact_id="f2", created_at=950.0, ttl_seconds=200.0),
        ]
        result = gc_expired_facts(facts, now=now)
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        """GC on empty list returns empty list."""
        result = gc_expired_facts([], now=1000.0)
        assert result == []


class TestRefreshConfidence:
    """Test confidence refresh for re-validated facts."""

    def test_refresh_restores_confidence(self):
        """Refresh should restore confidence to given value."""
        fact = FactTTL(fact_id="f1", confidence=0.3)
        refresh_confidence(fact, new_confidence=0.95)
        assert fact.confidence == pytest.approx(0.95)

    def test_refresh_default_full(self):
        """Default refresh restores to 1.0."""
        fact = FactTTL(fact_id="f1", confidence=0.1)
        refresh_confidence(fact)
        assert fact.confidence == pytest.approx(1.0)

    def test_refresh_extends_ttl(self):
        """Refresh can extend TTL."""
        fact = FactTTL(fact_id="f1", ttl_seconds=100.0)
        refresh_confidence(fact, extend_ttl=50.0)
        assert fact.ttl_seconds == pytest.approx(150.0)

    def test_refresh_clamps_confidence(self):
        """Confidence should be clamped to [0, 1]."""
        fact = FactTTL(fact_id="f1", confidence=0.5)
        refresh_confidence(fact, new_confidence=1.5)
        assert fact.confidence == pytest.approx(1.0)
        refresh_confidence(fact, new_confidence=-0.5)
        assert fact.confidence == pytest.approx(0.0)


class TestHiveGraphTTLIntegration:
    """Test InMemoryHiveGraph with enable_ttl."""

    def test_ttl_disabled_by_default(self):
        """enable_ttl should be False by default."""
        graph = InMemoryHiveGraph()
        assert graph.enable_ttl is False

    def test_ttl_enabled_creates_fact_ttl(self):
        """With enable_ttl=True, adding facts should create FactTTL entries."""
        graph = InMemoryHiveGraph(enable_ttl=True, default_ttl=60.0)
        graph.add_fact("f1", "test fact", confidence=0.9)
        assert "f1" in graph._fact_ttls
        assert graph._fact_ttls["f1"].ttl_seconds == 60.0

    def test_gc_removes_expired_from_graph(self):
        """run_gc should remove expired facts from the graph."""
        graph = InMemoryHiveGraph(enable_ttl=True, default_ttl=10.0)
        now = time.time()
        graph.add_fact("f1", "old fact", confidence=0.9)
        # Backdate the fact
        graph._fact_ttls["f1"].created_at = now - 100.0
        removed = graph.run_gc(now=now)
        assert removed == 1
        assert graph.fact_count == 0

    def test_get_fact_returns_none_for_expired(self):
        """get_fact should return None for expired facts."""
        graph = InMemoryHiveGraph(enable_ttl=True, default_ttl=10.0)
        graph.add_fact("f1", "test fact")
        # Backdate
        graph._fact_ttls["f1"].created_at = time.time() - 100.0
        result = graph.get_fact("f1")
        assert result is None
