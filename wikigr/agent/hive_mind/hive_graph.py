"""In-memory hive graph for multi-agent fact sharing.

Provides InMemoryHiveGraph which stores facts contributed by multiple agents
with optional TTL-based expiration and gossip-based dissemination.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .fact_lifecycle import FactTTL, decay_confidence, gc_expired_facts
from .gossip import GossipProtocol


@dataclass
class InMemoryHiveGraph:
    """In-memory graph of shared facts between agents.

    Attributes:
        enable_ttl: Enable fact TTL and garbage collection (default False).
        enable_gossip: Enable gossip protocol for fact sharing (default False).
        gossip_fanout: Number of peers per gossip round (default 3).
        default_ttl: Default TTL in seconds for new facts (default 3600).
    """

    enable_ttl: bool = False
    enable_gossip: bool = False
    gossip_fanout: int = 3
    default_ttl: float = 3600.0

    _facts: dict[str, dict[str, Any]] = field(default_factory=dict)
    _fact_ttls: dict[str, FactTTL] = field(default_factory=dict)
    _gossip: GossipProtocol | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.enable_gossip:
            self._gossip = GossipProtocol(
                agent_id="hive_graph",
                fanout=self.gossip_fanout,
            )

    def add_fact(
        self,
        fact_id: str,
        content: str,
        agent_id: str = "unknown",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        """Add a fact to the hive graph.

        Args:
            fact_id: Unique identifier for the fact.
            content: Text content of the fact.
            agent_id: ID of the contributing agent.
            confidence: Confidence level (0-1).
            metadata: Optional extra metadata.
            ttl_seconds: Custom TTL (uses default_ttl if None).
        """
        fact = {
            "fact_id": fact_id,
            "content": content,
            "agent_id": agent_id,
            "confidence": confidence,
            "metadata": metadata or {},
            "created_at": time.time(),
        }
        self._facts[fact_id] = fact

        if self.enable_ttl:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            self._fact_ttls[fact_id] = FactTTL(
                fact_id=fact_id,
                created_at=fact["created_at"],
                ttl_seconds=ttl,
                confidence=confidence,
            )

    def get_fact(self, fact_id: str) -> dict[str, Any] | None:
        """Retrieve a fact by ID, respecting TTL if enabled."""
        if self.enable_ttl and fact_id in self._fact_ttls:
            if self._fact_ttls[fact_id].is_expired():
                self.remove_fact(fact_id)
                return None
        return self._facts.get(fact_id)

    def remove_fact(self, fact_id: str) -> None:
        """Remove a fact from the graph."""
        self._facts.pop(fact_id, None)
        self._fact_ttls.pop(fact_id, None)

    def get_all_facts(self) -> list[dict[str, Any]]:
        """Return all non-expired facts."""
        if self.enable_ttl:
            self.run_gc()
        return list(self._facts.values())

    def run_gc(self, now: float | None = None) -> int:
        """Run garbage collection, removing expired facts.

        Returns:
            Number of facts removed.
        """
        if not self.enable_ttl:
            return 0

        if now is None:
            now = time.time()

        expired_ids = [
            fid for fid, ttl in self._fact_ttls.items() if ttl.is_expired(now)
        ]
        for fid in expired_ids:
            self.remove_fact(fid)
        return len(expired_ids)

    def get_gossip_protocol(self) -> GossipProtocol | None:
        """Get the gossip protocol instance if enabled."""
        return self._gossip

    @property
    def fact_count(self) -> int:
        """Number of facts currently stored."""
        return len(self._facts)
