"""Fact TTL and garbage collection for hive mind knowledge graphs.

Manages fact expiration through time-to-live (TTL) tracking,
exponential confidence decay, garbage collection of expired facts,
and confidence refresh for re-validated facts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class FactTTL:
    """Tracks TTL metadata for a single fact.

    Attributes:
        fact_id: Unique identifier for the fact.
        created_at: Unix timestamp when the fact was created.
        ttl_seconds: Time-to-live in seconds (default 3600 = 1 hour).
        confidence: Current confidence level (0-1, default 1.0).
        decay_rate: Exponential decay rate per second (default 0.001).
    """

    fact_id: str
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 3600.0
    confidence: float = 1.0
    decay_rate: float = 0.001

    @property
    def expires_at(self) -> float:
        """Unix timestamp when this fact expires."""
        return self.created_at + self.ttl_seconds

    def is_expired(self, now: float | None = None) -> bool:
        """Check if the fact has exceeded its TTL."""
        if now is None:
            now = time.time()
        return now >= self.expires_at


def decay_confidence(fact: FactTTL, elapsed_seconds: float) -> float:
    """Apply exponential confidence decay to a fact.

    Formula: new_confidence = confidence * exp(-decay_rate * elapsed_seconds)

    Since we avoid importing math for simplicity, we use the approximation:
        exp(-x) ≈ (1 - decay_rate) ** elapsed_seconds  for small decay_rate

    For correctness we use: confidence * e^(-decay_rate * elapsed)

    Args:
        fact: The fact whose confidence to decay.
        elapsed_seconds: Time elapsed since last decay application.

    Returns:
        The new confidence value (also updates fact.confidence in place).
    """
    import math

    new_conf = fact.confidence * math.exp(-fact.decay_rate * elapsed_seconds)
    new_conf = max(0.0, min(1.0, new_conf))
    fact.confidence = new_conf
    return new_conf


def gc_expired_facts(facts: list[FactTTL], now: float | None = None) -> list[FactTTL]:
    """Remove expired facts from a list (garbage collection sweep).

    Args:
        facts: List of FactTTL instances to filter.
        now: Current time (defaults to time.time()).

    Returns:
        New list containing only non-expired facts.
    """
    if now is None:
        now = time.time()
    return [f for f in facts if not f.is_expired(now)]


def refresh_confidence(fact: FactTTL, new_confidence: float = 1.0, extend_ttl: float = 0.0) -> None:
    """Refresh a fact's confidence and optionally extend its TTL.

    Used when a fact is re-validated by an agent, restoring trust.

    Args:
        fact: The fact to refresh.
        new_confidence: New confidence value (default 1.0 = full confidence).
        extend_ttl: Additional seconds to add to TTL (default 0 = no extension).
    """
    fact.confidence = max(0.0, min(1.0, new_confidence))
    if extend_ttl > 0:
        fact.ttl_seconds += extend_ttl
