"""Tests that verify documentation accuracy for issue #260.

Contracts:
  - docs/reference/pack-manifest.md line ~47: name field description must
    accurately reflect the actual validation regex ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$
    (allows uppercase letters and underscores; must NOT claim lowercase-only).
  - docs/reference/kg-agent-api.md line ~144: PLAN_CACHE_MAX_SIZE row must
    be annotated to clarify it is not currently enforced at runtime.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_MANIFEST_DOC = REPO_ROOT / "docs" / "reference" / "pack-manifest.md"
KG_AGENT_API_DOC = REPO_ROOT / "docs" / "reference" / "kg-agent-api.md"

EXPECTED_PACK_NAME_REGEX = r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$"
EXPECTED_PACK_NAME_PATTERN = re.compile(EXPECTED_PACK_NAME_REGEX)

# Pre-compiled patterns reused across tests — avoids recompilation on every call.
_NAME_ROW_PATTERN = re.compile(r"\|\s*`name`\s*\|.*?(?=\n\||\Z)", re.DOTALL)
_PLAN_CACHE_ROW_PATTERN = re.compile(r"\|\s*`?PLAN_CACHE_MAX_SIZE`?\s*\|[^|]*\|\s*`?(\d+)`?\s*\|")
_CONSTANTS_SECTION_PATTERN = re.compile(
    r"## Class Constants.*?(?=^##|\Z)", re.DOTALL | re.MULTILINE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_doc(path: Path) -> str:
    assert path.exists(), f"Documentation file missing: {path}"
    return path.read_text(encoding="utf-8")


def _assert_any_phrase(text: str, accepted: list, message: str) -> None:
    assert any(
        phrase in text for phrase in accepted
    ), f"{message} Expected one of: {', '.join(repr(p) for p in accepted)}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pack_manifest_text() -> str:
    return _load_doc(PACK_MANIFEST_DOC)


@pytest.fixture(scope="module")
def kg_agent_api_text() -> str:
    return _load_doc(KG_AGENT_API_DOC)


# ---------------------------------------------------------------------------
# pack-manifest.md — name field description
# ---------------------------------------------------------------------------


class TestPackManifestNameFieldDoc:
    """docs/reference/pack-manifest.md must accurately document the name regex."""

    def test_name_field_row_present(self, pack_manifest_text: str):
        """The name field row must be present in the Fields table."""
        assert (
            "| `name` |" in pack_manifest_text
        ), "pack-manifest.md must contain a '| `name` |' table row"

    def test_verbatim_regex_present(self, pack_manifest_text: str):
        """The verbatim regex must appear in the doc so readers can verify it directly."""
        assert EXPECTED_PACK_NAME_REGEX in pack_manifest_text, (
            f"pack-manifest.md must contain the verbatim regex "
            f"'{EXPECTED_PACK_NAME_REGEX}' so readers can verify validation rules"
        )

    def test_uppercase_letters_documented(self, pack_manifest_text: str):
        """Doc must state that uppercase letters are allowed (not lowercase-only)."""
        _assert_any_phrase(
            pack_manifest_text,
            ["upper or lower case", "uppercase", "a-zA-Z"],
            "pack-manifest.md name field must document that uppercase letters are allowed.",
        )

    def test_underscores_documented(self, pack_manifest_text: str):
        """Doc must state that underscores are allowed in pack names."""
        _assert_any_phrase(
            pack_manifest_text,
            ["underscore", "_"],
            "pack-manifest.md name field must document that underscores are allowed.",
        )

    def test_max_length_documented(self, pack_manifest_text: str):
        """Doc must mention the 64-character maximum length."""
        _assert_any_phrase(
            pack_manifest_text,
            ["64", "max 64"],
            "pack-manifest.md name field must document the 64-character maximum.",
        )

    def test_name_must_start_with_alphanumeric_documented(self, pack_manifest_text: str):
        """Doc must mention that the name must start with an alphanumeric character."""
        _assert_any_phrase(
            pack_manifest_text,
            [
                "must start with an alphanumeric",
                "start with alphanumeric",
                "starts with an alphanumeric",
                "[a-zA-Z0-9]",  # covered by the regex itself
            ],
            "pack-manifest.md must document that names must start with an alphanumeric character.",
        )

    def test_doc_does_not_claim_lowercase_only(self, pack_manifest_text: str):
        """Doc must NOT state that only lowercase letters are allowed."""
        name_row_match = _NAME_ROW_PATTERN.search(pack_manifest_text)
        assert (
            name_row_match is not None
        ), "Could not locate the `name` table row in pack-manifest.md"
        name_row_lower = name_row_match.group(0).lower()

        forbidden = [
            "lowercase only",
            "lower-case only",
            "only lowercase",
            "only lower case",
        ]
        for phrase in forbidden:
            assert phrase not in name_row_lower, (
                f"pack-manifest.md name field must NOT contain '{phrase}'; "
                "the actual regex allows uppercase letters"
            )

    def test_example_with_uppercase_present(self, pack_manifest_text: str):
        """At least one example pack name demonstrating uppercase must appear."""
        assert "React_Expert" in pack_manifest_text, (
            "pack-manifest.md should include 'React_Expert' as an example "
            "to demonstrate uppercase and underscore support"
        )

    def test_regex_is_anchored(self, pack_manifest_text: str):
        """The documented regex must be anchored (^ at start, $ at end)."""
        assert (
            "^[a-zA-Z0-9]" in pack_manifest_text
        ), "Regex in pack-manifest.md must be anchored at start with '^[a-zA-Z0-9]'"
        assert (
            "{0,63}$" in pack_manifest_text
        ), "Regex in pack-manifest.md must be anchored at end with '{0,63}$'"

    def test_regex_in_doc_matches_valid_pack_names(self, pack_manifest_text: str):
        """The regex extracted from the doc must accept canonical valid names."""
        valid_names = [
            "go-expert",
            "React_Expert",
            "A",
            "a1",
            "my-Pack_v2",
            "x" * 64,  # max length
        ]
        for name in valid_names:
            assert EXPECTED_PACK_NAME_PATTERN.fullmatch(name), (
                f"Documented regex '{EXPECTED_PACK_NAME_REGEX}' must accept " f"valid name '{name}'"
            )

    def test_regex_in_doc_rejects_invalid_pack_names(self, pack_manifest_text: str):
        """The regex extracted from the doc must reject invalid names."""
        invalid_names = [
            "",  # empty
            "-leading-hyphen",  # starts with hyphen
            "_leading-underscore",  # starts with underscore
            "x" * 65,  # 65 chars — one over the limit
            "has space",  # space not in charset
            "has/slash",  # path separator
            "has.dot",  # dot not in charset
        ]
        for name in invalid_names:
            assert not EXPECTED_PACK_NAME_PATTERN.fullmatch(name), (
                f"Documented regex '{EXPECTED_PACK_NAME_REGEX}' must reject "
                f"invalid name '{name!r}'"
            )


# ---------------------------------------------------------------------------
# kg-agent-api.md — PLAN_CACHE_MAX_SIZE annotation
# ---------------------------------------------------------------------------


class TestKgAgentApiPlanCacheDoc:
    """docs/reference/kg-agent-api.md must annotate PLAN_CACHE_MAX_SIZE as not enforced."""

    def test_plan_cache_max_size_row_present(self, kg_agent_api_text: str):
        """PLAN_CACHE_MAX_SIZE must still appear in the constants table (not removed)."""
        assert (
            "PLAN_CACHE_MAX_SIZE" in kg_agent_api_text
        ), "kg-agent-api.md must contain the PLAN_CACHE_MAX_SIZE constant row"

    def test_plan_cache_unbounded_dict_explanation(self, kg_agent_api_text: str):
        """The annotation must explain that _plan_cache is unbounded at runtime."""
        _assert_any_phrase(
            kg_agent_api_text,
            ["_plan_cache", "unbounded"],
            "kg-agent-api.md PLAN_CACHE_MAX_SIZE annotation must explain that _plan_cache is unbounded at runtime.",
        )

    def test_plan_cache_row_has_correct_default_value(self, kg_agent_api_text: str):
        """The PLAN_CACHE_MAX_SIZE row must document the correct default value of 128."""
        match = _PLAN_CACHE_ROW_PATTERN.search(kg_agent_api_text)
        assert (
            match is not None
        ), "Could not find PLAN_CACHE_MAX_SIZE row with a numeric default value"
        assert (
            match.group(1) == "128"
        ), f"PLAN_CACHE_MAX_SIZE default must be documented as 128, got '{match.group(1)}'"

    def test_plan_cache_annotation_is_in_constants_table(self, kg_agent_api_text: str):
        """The PLAN_CACHE_MAX_SIZE annotation must appear in the Class Constants section."""
        constants_section_match = _CONSTANTS_SECTION_PATTERN.search(kg_agent_api_text)
        assert (
            constants_section_match is not None
        ), "kg-agent-api.md must have a '## Class Constants' section"
        constants_section = constants_section_match.group(0)

        assert (
            "PLAN_CACHE_MAX_SIZE" in constants_section
        ), "PLAN_CACHE_MAX_SIZE must appear in the '## Class Constants' section"
        _assert_any_phrase(
            constants_section,
            ["Not currently enforced", "not currently enforced", "not enforced"],
            "The 'not enforced' annotation must be within the Class Constants section.",
        )

    def test_other_constants_not_removed(self, kg_agent_api_text: str):
        """Ensure other class constants were not accidentally removed."""
        required_constants = [
            "DEFAULT_MODEL",
            "VECTOR_CONFIDENCE_THRESHOLD",
            "CONTEXT_CONFIDENCE_THRESHOLD",
            "MAX_ARTICLE_CHARS",
            "PLAN_MAX_TOKENS",
            "SYNTHESIS_MAX_TOKENS",
        ]
        for constant in required_constants:
            assert (
                constant in kg_agent_api_text
            ), f"kg-agent-api.md must still contain the '{constant}' constant row"


# ---------------------------------------------------------------------------
# Cross-file consistency
# ---------------------------------------------------------------------------


class TestDocumentationConsistency:
    """Cross-file consistency checks for the two changed documentation files."""

    def test_pack_manifest_doc_references_regex_once(self, pack_manifest_text: str):
        """The verbatim regex should appear at least once (multiple occurrences are fine)."""
        count = pack_manifest_text.count(EXPECTED_PACK_NAME_REGEX)
        assert count >= 1, (
            f"Expected regex '{EXPECTED_PACK_NAME_REGEX}' to appear at least once "
            f"in pack-manifest.md, found {count} occurrences"
        )

    def test_neither_doc_was_emptied(self, pack_manifest_text: str, kg_agent_api_text: str):
        """Both doc files must have substantial content (not accidentally cleared)."""
        assert (
            len(pack_manifest_text) > 500
        ), "pack-manifest.md appears to have been truncated or emptied"
        assert (
            len(kg_agent_api_text) > 500
        ), "kg-agent-api.md appears to have been truncated or emptied"
