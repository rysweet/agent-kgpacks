"""Gossip protocol for hive mind fact dissemination.

Implements epidemic-style gossip for sharing facts between agents.
Each round, an agent selects a subset of peers (fanout) and shares
its top-k facts, weighted by confidence and trust.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GossipProtocol:
    """Gossip protocol for fact sharing between agents.

    Attributes:
        agent_id: This agent's unique identifier.
        fanout: Number of peers to contact per gossip round (default 3).
        top_k: Maximum facts to share per round (default 10).
        peers: Set of known peer agent IDs.
        fact_versions: Maps fact_id -> version counter for convergence tracking.
    """

    agent_id: str
    fanout: int = 3
    top_k: int = 10
    peers: set[str] = field(default_factory=set)
    fact_versions: dict[str, int] = field(default_factory=dict)

    def add_peer(self, peer_id: str) -> None:
        """Register a peer agent."""
        if peer_id != self.agent_id:
            self.peers.add(peer_id)

    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer agent."""
        self.peers.discard(peer_id)

    def _select_peers(self, peer_weights: dict[str, float] | None = None) -> list[str]:
        """Select peers for this gossip round using weighted random selection.

        Args:
            peer_weights: Optional dict mapping peer_id -> weight for biased selection.
                         Higher weight = more likely to be selected.
                         If None, uniform random selection is used.

        Returns:
            List of selected peer IDs (up to fanout count).
        """
        available = list(self.peers)
        if not available:
            return []

        k = min(self.fanout, len(available))

        if peer_weights is None:
            return random.sample(available, k)

        # Weighted selection without replacement
        weights = [peer_weights.get(p, 1.0) for p in available]
        total = sum(weights)
        if total == 0:
            return random.sample(available, k)

        selected: list[str] = []
        remaining = list(zip(available, weights))
        for _ in range(k):
            if not remaining:
                break
            peers_list, w_list = zip(*remaining)
            total_w = sum(w_list)
            r = random.random() * total_w
            cumulative = 0.0
            chosen_idx = 0
            for idx, w in enumerate(w_list):
                cumulative += w
                if r <= cumulative:
                    chosen_idx = idx
                    break
            selected.append(peers_list[chosen_idx])
            remaining.pop(chosen_idx)

        return selected

    def run_gossip_round(
        self,
        local_facts: list[dict[str, Any]],
        peer_weights: dict[str, float] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Execute one gossip round, selecting peers and preparing fact payloads.

        Selects up to `fanout` peers and prepares the top-k facts (by confidence)
        for each selected peer.

        Args:
            local_facts: This agent's current facts. Each dict should have
                        at least "fact_id" and "confidence" keys.
            peer_weights: Optional weights for biased peer selection.

        Returns:
            Dict mapping selected peer_id -> list of facts to send.
        """
        selected = self._select_peers(peer_weights)
        if not selected:
            return {}

        # Sort facts by confidence descending, take top_k
        sorted_facts = sorted(
            local_facts,
            key=lambda f: f.get("confidence", 0.0),
            reverse=True,
        )
        payload = sorted_facts[: self.top_k]

        # Update version counters for shared facts
        for fact in payload:
            fid = fact.get("fact_id", "")
            if fid:
                self.fact_versions[fid] = self.fact_versions.get(fid, 0) + 1

        return {peer: list(payload) for peer in selected}

    def convergence_check(
        self,
        local_facts: dict[str, Any],
        peer_facts: dict[str, dict[str, Any]],
        threshold: float = 0.95,
    ) -> bool:
        """Check if gossip has converged across peers.

        Convergence is reached when the fraction of facts that are consistent
        (same version or same confidence) across all peers exceeds the threshold.

        Args:
            local_facts: Dict mapping fact_id -> fact dict with "confidence".
            peer_facts: Dict mapping peer_id -> {fact_id -> fact dict}.
            threshold: Fraction of consistent facts required (default 0.95).

        Returns:
            True if gossip has converged, False otherwise.
        """
        if not local_facts or not peer_facts:
            return True  # Nothing to compare = trivially converged

        all_fact_ids = set(local_facts.keys())
        for peer_data in peer_facts.values():
            all_fact_ids |= set(peer_data.keys())

        if not all_fact_ids:
            return True

        consistent = 0
        for fid in all_fact_ids:
            local_conf = local_facts.get(fid, {}).get("confidence")
            peer_confs = [
                pd.get(fid, {}).get("confidence")
                for pd in peer_facts.values()
                if fid in pd
            ]

            if local_conf is not None and peer_confs:
                # Check if all values are within 1% of each other
                all_vals = [local_conf] + peer_confs
                max_val = max(all_vals)
                min_val = min(all_vals)
                if max_val == 0 or (max_val - min_val) / max(max_val, 1e-10) < 0.01:
                    consistent += 1
            elif local_conf is None and not peer_confs:
                consistent += 1

        ratio = consistent / len(all_fact_ids) if all_fact_ids else 1.0
        return ratio >= threshold
