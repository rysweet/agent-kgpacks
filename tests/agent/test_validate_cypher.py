"""Unit tests for KnowledgeGraphAgent._validate_cypher() security boundary.

Tests verify the allowlist/blocklist logic that prevents destructive Cypher
queries from reaching the database.  The method is a @staticmethod so no
agent instantiation or connection mock is required.

Closes #174.
"""

from __future__ import annotations

import pytest

from wikigr.agent.kg_agent import KnowledgeGraphAgent

_validate = KnowledgeGraphAgent._validate_cypher


# ── Allow-list tests ────────────────────────────────────────────────


class TestAllowedQueries:
    """Queries that must pass validation without raising."""

    def test_validate_cypher_allows_match_query(self) -> None:
        _validate("MATCH (a:Article) RETURN a LIMIT 10")

    def test_validate_cypher_allows_vector_index_call(self) -> None:
        _validate(
            "CALL QUERY_VECTOR_INDEX('Section', 'embedding_idx', $query, 10) "
            "RETURN node.title, node.content, score"
        )

    def test_validate_cypher_allows_return_with_limit(self) -> None:
        _validate(
            "MATCH (a:Article)-[:HAS_SECTION]->(s:Section) "
            "RETURN a.title, s.heading, s.content LIMIT 25"
        )


# ── Block-list tests ────────────────────────────────────────────────


class TestBlockedKeywords:
    """Dangerous write/DDL keywords must be rejected."""

    def test_validate_cypher_blocks_create(self) -> None:
        with pytest.raises(ValueError, match="Write operation rejected.*CREATE"):
            _validate("MATCH (a:Article) CREATE (b:Article {title: 'hack'})")

    def test_validate_cypher_blocks_delete(self) -> None:
        with pytest.raises(ValueError, match="Write operation rejected.*DELETE"):
            _validate("MATCH (a:Article) DELETE a")

    def test_validate_cypher_blocks_drop(self) -> None:
        with pytest.raises(ValueError, match="Write operation rejected.*DROP"):
            _validate("MATCH (a:Article) DROP a")

    def test_validate_cypher_blocks_set(self) -> None:
        with pytest.raises(ValueError, match="Write operation rejected.*SET"):
            _validate("MATCH (a:Article) SET a.title = 'pwned'")


# ── Prefix validation ──────────────────────────────────────────────


class TestPrefixValidation:
    """Queries that don't start with an allowed prefix must be rejected."""

    def test_validate_cypher_rejects_non_match_prefix(self) -> None:
        with pytest.raises(ValueError, match="must start with MATCH"):
            _validate("RETURN 1 AS one")


# ── Bypass resistance ──────────────────────────────────────────────


class TestBypassResistance:
    """Dangerous keywords inside string literals must NOT trigger rejection."""

    def test_validate_cypher_ignores_keywords_in_strings(self) -> None:
        # "DELETE ME" is inside a string literal -- should be stripped before
        # keyword scanning, so this query must pass.
        _validate('MATCH (a:Article) WHERE a.name = "DELETE ME" RETURN a')


# ── Unbounded path tests ───────────────────────────────────────────


class TestUnboundedPaths:
    """Unbounded variable-length paths must be rejected."""

    def test_validate_cypher_blocks_unbounded_path(self) -> None:
        with pytest.raises(ValueError, match="Unbounded variable-length path"):
            _validate("MATCH (a)-[:LINKS_TO*]->(b) RETURN b LIMIT 10")
