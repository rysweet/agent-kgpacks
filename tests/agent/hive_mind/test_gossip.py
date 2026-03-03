"""Tests for gossip protocol fact dissemination.

Covers:
- Gossip round execution
- Convergence detection
- Fanout limits
- Weighted peer selection
- Integration with InMemoryHiveGraph enable_gossip
"""

import pytest

from wikigr.agent.hive_mind.gossip import GossipProtocol
from wikigr.agent.hive_mind.hive_graph import InMemoryHiveGraph


class TestGossipRound:
    """Test run_gossip_round() execution."""

    def test_round_sends_to_selected_peers(self):
        """Gossip round should send facts to selected peers."""
        gp = GossipProtocol(agent_id="a1", fanout=2)
        gp.add_peer("p1")
        gp.add_peer("p2")
        gp.add_peer("p3")

        facts = [
            {"fact_id": "f1", "confidence": 0.9},
            {"fact_id": "f2", "confidence": 0.5},
        ]
        result = gp.run_gossip_round(facts)

        assert len(result) == 2  # fanout=2
        for peer_facts in result.values():
            assert len(peer_facts) == 2

    def test_round_with_no_peers(self):
        """Gossip round with no peers returns empty dict."""
        gp = GossipProtocol(agent_id="a1", fanout=2)
        facts = [{"fact_id": "f1", "confidence": 0.9}]
        result = gp.run_gossip_round(facts)
        assert result == {}

    def test_round_selects_top_k_facts(self):
        """Only top_k facts by confidence should be shared."""
        gp = GossipProtocol(agent_id="a1", fanout=1, top_k=2)
        gp.add_peer("p1")

        facts = [
            {"fact_id": "f1", "confidence": 0.3},
            {"fact_id": "f2", "confidence": 0.9},
            {"fact_id": "f3", "confidence": 0.6},
        ]
        result = gp.run_gossip_round(facts)

        sent = list(result.values())[0]
        assert len(sent) == 2
        # Should be f2 (0.9) and f3 (0.6), not f1 (0.3)
        sent_ids = {f["fact_id"] for f in sent}
        assert "f2" in sent_ids
        assert "f3" in sent_ids

    def test_round_updates_version_counters(self):
        """Gossip round should increment version counters for shared facts."""
        gp = GossipProtocol(agent_id="a1", fanout=1)
        gp.add_peer("p1")

        facts = [{"fact_id": "f1", "confidence": 0.9}]
        gp.run_gossip_round(facts)
        assert gp.fact_versions.get("f1") == 1

        gp.run_gossip_round(facts)
        assert gp.fact_versions.get("f1") == 2


class TestConvergence:
    """Test convergence_check()."""

    def test_converged_when_all_match(self):
        """Should converge when all peers have same confidence values."""
        gp = GossipProtocol(agent_id="a1")
        local = {
            "f1": {"confidence": 0.9},
            "f2": {"confidence": 0.8},
        }
        peer_facts = {
            "p1": {"f1": {"confidence": 0.9}, "f2": {"confidence": 0.8}},
            "p2": {"f1": {"confidence": 0.9}, "f2": {"confidence": 0.8}},
        }
        assert gp.convergence_check(local, peer_facts) is True

    def test_not_converged_when_divergent(self):
        """Should not converge when peers have different values."""
        gp = GossipProtocol(agent_id="a1")
        local = {"f1": {"confidence": 0.9}}
        peer_facts = {
            "p1": {"f1": {"confidence": 0.1}},  # very different
        }
        assert gp.convergence_check(local, peer_facts, threshold=0.95) is False

    def test_empty_facts_trivially_converged(self):
        """Empty fact sets should be considered converged."""
        gp = GossipProtocol(agent_id="a1")
        assert gp.convergence_check({}, {}) is True

    def test_convergence_threshold_respected(self):
        """Convergence should respect the threshold parameter."""
        gp = GossipProtocol(agent_id="a1")
        local = {
            "f1": {"confidence": 0.9},
            "f2": {"confidence": 0.8},
        }
        # f1 matches, f2 diverges
        peer_facts = {
            "p1": {"f1": {"confidence": 0.9}, "f2": {"confidence": 0.1}},
        }
        # 50% converged — threshold 0.4 should pass, 0.9 should fail
        assert gp.convergence_check(local, peer_facts, threshold=0.4) is True
        assert gp.convergence_check(local, peer_facts, threshold=0.9) is False


class TestFanout:
    """Test fanout limits on peer selection."""

    def test_fanout_limits_peers(self):
        """Should not select more peers than fanout."""
        gp = GossipProtocol(agent_id="a1", fanout=2)
        for i in range(10):
            gp.add_peer(f"p{i}")

        facts = [{"fact_id": "f1", "confidence": 0.9}]
        result = gp.run_gossip_round(facts)
        assert len(result) <= 2

    def test_fanout_exceeds_peers(self):
        """When fanout > available peers, select all peers."""
        gp = GossipProtocol(agent_id="a1", fanout=10)
        gp.add_peer("p1")
        gp.add_peer("p2")

        facts = [{"fact_id": "f1", "confidence": 0.9}]
        result = gp.run_gossip_round(facts)
        assert len(result) == 2  # only 2 peers available


class TestWeightedSelection:
    """Test weighted peer selection."""

    def test_weighted_selection_respects_weights(self):
        """Higher-weighted peers should be selected more often."""
        # Run many rounds and check distribution
        selected_counts: dict[str, int] = {"p1": 0, "p2": 0}
        for _ in range(200):
            gp = GossipProtocol(agent_id="a1", fanout=1)
            gp.add_peer("p1")
            gp.add_peer("p2")
            facts = [{"fact_id": "f1", "confidence": 0.9}]
            weights = {"p1": 10.0, "p2": 1.0}
            result = gp.run_gossip_round(facts, peer_weights=weights)
            for peer in result:
                selected_counts[peer] += 1

        # p1 (weight 10) should be selected much more than p2 (weight 1)
        assert selected_counts["p1"] > selected_counts["p2"]

    def test_uniform_selection_without_weights(self):
        """Without weights, selection should be roughly uniform."""
        selected_counts: dict[str, int] = {"p1": 0, "p2": 0}
        for _ in range(200):
            gp = GossipProtocol(agent_id="a1", fanout=1)
            gp.add_peer("p1")
            gp.add_peer("p2")
            facts = [{"fact_id": "f1", "confidence": 0.9}]
            result = gp.run_gossip_round(facts)
            for peer in result:
                selected_counts[peer] += 1

        # Should be roughly 50/50 — allow wide margin
        total = selected_counts["p1"] + selected_counts["p2"]
        ratio = selected_counts["p1"] / total
        assert 0.25 < ratio < 0.75


class TestPeerManagement:
    """Test peer add/remove."""

    def test_add_peer(self):
        gp = GossipProtocol(agent_id="a1")
        gp.add_peer("p1")
        assert "p1" in gp.peers

    def test_cannot_add_self(self):
        """Agent should not be added as its own peer."""
        gp = GossipProtocol(agent_id="a1")
        gp.add_peer("a1")
        assert "a1" not in gp.peers

    def test_remove_peer(self):
        gp = GossipProtocol(agent_id="a1")
        gp.add_peer("p1")
        gp.remove_peer("p1")
        assert "p1" not in gp.peers


class TestHiveGraphGossipIntegration:
    """Test InMemoryHiveGraph with enable_gossip."""

    def test_gossip_disabled_by_default(self):
        """enable_gossip should be False by default."""
        graph = InMemoryHiveGraph()
        assert graph.enable_gossip is False
        assert graph.get_gossip_protocol() is None

    def test_gossip_enabled_creates_protocol(self):
        """With enable_gossip=True, gossip protocol should be created."""
        graph = InMemoryHiveGraph(enable_gossip=True, gossip_fanout=5)
        gp = graph.get_gossip_protocol()
        assert gp is not None
        assert gp.fanout == 5
