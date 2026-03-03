"""Tests for LLM response schema validation (SEC-08).

Verifies that _sanitize_entities() and _sanitize_relationships() correctly
filter corrupt, oversized, or structurally unexpected LLM responses before
data is written to the knowledge graph.
"""

from __future__ import annotations

import pytest

from ..llm_extractor import _sanitize_entities, _sanitize_key_facts, _sanitize_relationships


# ---------------------------------------------------------------------------
# _sanitize_entities
# ---------------------------------------------------------------------------


class TestSanitizeEntities:
    """SEC-08: entity list sanitization."""

    def test_valid_entities_pass_through(self):
        raw = [
            {"name": "Azure", "type": "org", "properties": {}},
            {"name": "Lighthouse", "type": "concept"},
        ]
        result = _sanitize_entities(raw)
        assert len(result) == 2
        assert result[0]["name"] == "Azure"
        assert result[1]["name"] == "Lighthouse"

    def test_non_list_returns_empty(self):
        assert _sanitize_entities(None) == []
        assert _sanitize_entities({}) == []
        assert _sanitize_entities("entities") == []

    def test_entity_missing_name_is_dropped(self):
        raw = [{"type": "concept", "properties": {}}]
        assert _sanitize_entities(raw) == []

    def test_entity_empty_name_is_dropped(self):
        raw = [{"name": "   ", "type": "concept"}]
        assert _sanitize_entities(raw) == []

    def test_entity_non_string_name_is_dropped(self):
        raw = [{"name": 42, "type": "concept"}]
        assert _sanitize_entities(raw) == []

    def test_entity_name_truncated_at_256(self):
        long_name = "A" * 300
        raw = [{"name": long_name, "type": "concept"}]
        result = _sanitize_entities(raw)
        assert len(result) == 1
        assert len(result[0]["name"]) == 256

    def test_entity_missing_type_defaults_to_concept(self):
        raw = [{"name": "Sentinel"}]
        result = _sanitize_entities(raw)
        assert len(result) == 1
        assert result[0]["type"] == "concept"

    def test_entity_empty_type_defaults_to_concept(self):
        raw = [{"name": "Sentinel", "type": ""}]
        result = _sanitize_entities(raw)
        assert len(result) == 1
        assert result[0]["type"] == "concept"

    def test_non_dict_elements_skipped(self):
        raw = [{"name": "Valid", "type": "org"}, "not-a-dict", None, 42]
        result = _sanitize_entities(raw)
        assert len(result) == 1
        assert result[0]["name"] == "Valid"

    def test_empty_list_returns_empty(self):
        assert _sanitize_entities([]) == []

    def test_properties_preserved_on_valid_entity(self):
        raw = [{"name": "AKS", "type": "service", "properties": {"version": "1.28"}}]
        result = _sanitize_entities(raw)
        assert result[0]["properties"] == {"version": "1.28"}


# ---------------------------------------------------------------------------
# _sanitize_relationships
# ---------------------------------------------------------------------------


class TestSanitizeRelationships:
    """SEC-08: relationship list sanitization."""

    def test_valid_relationships_pass_through(self):
        raw = [
            {"source": "A", "target": "B", "relation": "uses", "context": "A uses B"},
        ]
        result = _sanitize_relationships(raw)
        assert len(result) == 1
        assert result[0]["source"] == "A"

    def test_non_list_returns_empty(self):
        assert _sanitize_relationships(None) == []
        assert _sanitize_relationships({}) == []
        assert _sanitize_relationships("rels") == []

    def test_missing_source_drops_relationship(self):
        raw = [{"target": "B", "relation": "uses"}]
        assert _sanitize_relationships(raw) == []

    def test_empty_source_drops_relationship(self):
        raw = [{"source": "", "target": "B", "relation": "uses"}]
        assert _sanitize_relationships(raw) == []

    def test_missing_target_drops_relationship(self):
        raw = [{"source": "A", "relation": "uses"}]
        assert _sanitize_relationships(raw) == []

    def test_empty_target_drops_relationship(self):
        raw = [{"source": "A", "target": "  ", "relation": "uses"}]
        assert _sanitize_relationships(raw) == []

    def test_missing_relation_drops_relationship(self):
        raw = [{"source": "A", "target": "B"}]
        assert _sanitize_relationships(raw) == []

    def test_empty_relation_drops_relationship(self):
        raw = [{"source": "A", "target": "B", "relation": ""}]
        assert _sanitize_relationships(raw) == []

    def test_non_string_field_drops_relationship(self):
        raw = [{"source": 42, "target": "B", "relation": "uses"}]
        assert _sanitize_relationships(raw) == []

    def test_non_dict_elements_skipped(self):
        raw = [
            {"source": "A", "target": "B", "relation": "uses"},
            "not-a-dict",
            None,
        ]
        result = _sanitize_relationships(raw)
        assert len(result) == 1

    def test_empty_list_returns_empty(self):
        assert _sanitize_relationships([]) == []

    def test_context_optional(self):
        """Relationships without a context field should still be valid."""
        raw = [{"source": "A", "target": "B", "relation": "part_of"}]
        result = _sanitize_relationships(raw)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _sanitize_key_facts
# ---------------------------------------------------------------------------


class TestSanitizeKeyFacts:
    """SEC-08: key_facts list sanitization."""

    def test_valid_facts_pass_through(self):
        raw = ["Azure Lighthouse enables cross-tenant management.", "Delegated access is scoped."]
        result = _sanitize_key_facts(raw)
        assert result == raw

    def test_non_list_returns_empty(self):
        assert _sanitize_key_facts(None) == []
        assert _sanitize_key_facts({}) == []
        assert _sanitize_key_facts("a fact") == []

    def test_non_string_elements_dropped(self):
        raw = ["valid fact", 42, None, {"injected": "payload"}, "another fact"]
        result = _sanitize_key_facts(raw)
        assert result == ["valid fact", "another fact"]

    def test_whitespace_only_elements_dropped(self):
        raw = ["  ", "\t", "real fact"]
        result = _sanitize_key_facts(raw)
        assert result == ["real fact"]

    def test_long_fact_truncated_at_1024(self):
        long_fact = "x" * 2000
        result = _sanitize_key_facts([long_fact])
        assert len(result) == 1
        assert len(result[0]) == 1024

    def test_empty_list_returns_empty(self):
        assert _sanitize_key_facts([]) == []

    def test_facts_stripped_of_leading_trailing_whitespace(self):
        raw = ["  trimmed fact  "]
        result = _sanitize_key_facts(raw)
        assert result == ["trimmed fact"]
