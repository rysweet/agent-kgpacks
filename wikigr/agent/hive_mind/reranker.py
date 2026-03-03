"""Trust-weighted retrieval for hive mind fact scoring.

Provides trust_weighted_score() which combines semantic similarity with
source agent trust, and an updated hybrid_score() that accepts source_trust.

Formula:
    trust_weighted_score = semantic_similarity * source_agent_trust + confidence * 0.01
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def trust_weighted_score(
    semantic_similarity: float,
    source_agent_trust: float,
    confidence: float,
) -> float:
    """Compute trust-weighted score for a fact.

    Args:
        semantic_similarity: Cosine similarity between query and fact (0-1).
        source_agent_trust: Trust level of the agent that contributed the fact (0-1).
        confidence: Confidence score of the fact itself (0-1).

    Returns:
        Combined score: semantic_similarity * source_agent_trust + confidence * 0.01
    """
    return semantic_similarity * source_agent_trust + confidence * 0.01


def hybrid_score(
    keyword_score: float,
    vector_score: float,
    keyword_weight: float = 0.3,
    vector_weight: float = 0.7,
    source_trust: float = 1.0,
) -> float:
    """Compute hybrid retrieval score combining keyword and vector scores.

    When source_trust < 1.0, the combined score is scaled down proportionally.

    Args:
        keyword_score: BM25 or keyword match score (0-1).
        vector_score: Vector/semantic similarity score (0-1).
        keyword_weight: Weight for keyword component (default 0.3).
        vector_weight: Weight for vector component (default 0.7).
        source_trust: Trust level of the source agent (0-1, default 1.0).

    Returns:
        Weighted hybrid score scaled by source trust.
    """
    base = keyword_score * keyword_weight + vector_score * vector_weight
    return base * source_trust


@dataclass
class _AgentTrustRegistry:
    """Simple in-memory registry mapping agent IDs to trust scores."""

    _trust: dict[str, float] = field(default_factory=dict)

    def set_trust(self, agent_id: str, trust: float) -> None:
        self._trust[agent_id] = max(0.0, min(1.0, trust))

    def get_trust(self, agent_id: str, default: float = 1.0) -> float:
        return self._trust.get(agent_id, default)


# Module-level registry for agent trust data
_agent_trust = _AgentTrustRegistry()


def set_agent_trust(agent_id: str, trust: float) -> None:
    """Set the trust score for a given agent."""
    _agent_trust.set_trust(agent_id, trust)


def get_agent_trust(agent_id: str, default: float = 1.0) -> float:
    """Get the trust score for a given agent."""
    return _agent_trust.get_trust(agent_id, default)


def query_facts(
    query_embedding: list[float] | None,
    facts: list[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Score and rank facts using trust-weighted retrieval.

    Each fact dict should have:
        - "content": str
        - "semantic_similarity": float (precomputed similarity to query)
        - "confidence": float
        - "agent_id": str (optional, for trust lookup)

    Args:
        query_embedding: Not used directly; similarity is precomputed in facts.
        facts: List of fact dicts with precomputed similarities.
        top_k: Maximum number of results to return.

    Returns:
        Top-k facts sorted by trust-weighted score (descending),
        each augmented with a "score" field.
    """
    scored: list[dict[str, Any]] = []
    for fact in facts:
        sim = fact.get("semantic_similarity", 0.0)
        conf = fact.get("confidence", 0.5)
        agent_id = fact.get("agent_id")

        if agent_id is not None:
            agent_trust = get_agent_trust(agent_id)
        else:
            agent_trust = 1.0

        score = trust_weighted_score(sim, agent_trust, conf)
        entry = {**fact, "score": score}
        scored.append(entry)

    scored.sort(key=lambda f: f["score"], reverse=True)
    return scored[:top_k]
