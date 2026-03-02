"""Tests for PACK_NAME_RE as a module-level constant in wikigr.packs.manifest.

These tests define the contract established by extracting the regex to a
shared constant so that cli.py and validate_pack_urls.py can both import it
without re-defining the pattern locally.

TDD: written to specify behaviour BEFORE (or alongside) implementation.
"""

from __future__ import annotations

import re


class TestPackNameReModuleLevelExport:
    """PACK_NAME_RE must be importable directly from wikigr.packs.manifest."""

    def test_pack_name_re_is_importable(self):
        """PACK_NAME_RE can be imported from wikigr.packs.manifest at module level."""
        from wikigr.packs.manifest import PACK_NAME_RE  # noqa: PLC0415

        assert PACK_NAME_RE is not None

    def test_pack_name_re_is_compiled_pattern(self):
        """PACK_NAME_RE is a compiled re.Pattern, not a raw string."""
        from wikigr.packs.manifest import PACK_NAME_RE  # noqa: PLC0415

        assert isinstance(PACK_NAME_RE, re.Pattern)

    def test_pack_name_re_pattern_string(self):
        """PACK_NAME_RE uses the canonical pattern with anchors and allowed chars."""
        from wikigr.packs.manifest import PACK_NAME_RE  # noqa: PLC0415

        assert PACK_NAME_RE.pattern == r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$"


class TestPackNameReValidNames:
    """PACK_NAME_RE must accept all legitimate pack short-names."""

    def setup_method(self):
        from wikigr.packs.manifest import PACK_NAME_RE  # noqa: PLC0415

        self.re = PACK_NAME_RE

    def test_simple_lowercase(self):
        assert self.re.match("physics")

    def test_hyphen_separated(self):
        assert self.re.match("physics-expert")

    def test_underscore_separated(self):
        assert self.re.match("physics_expert")

    def test_mixed_case(self):
        assert self.re.match("PhysicsExpert")

    def test_starts_with_digit(self):
        assert self.re.match("3d-printing")

    def test_single_char(self):
        assert self.re.match("a")

    def test_exactly_64_chars(self):
        # First char + 63 more = 64 total, which is the maximum allowed
        name = "a" + "b" * 63
        assert len(name) == 64
        assert self.re.match(name)

    def test_alphanumeric_mixed(self):
        assert self.re.match("go-expert2024")

    def test_dotnet_style(self):
        assert self.re.match("dotnet-expert")


class TestPackNameReInvalidNames:
    """PACK_NAME_RE must reject all unsafe or malformed pack names."""

    def setup_method(self):
        from wikigr.packs.manifest import PACK_NAME_RE  # noqa: PLC0415

        self.re = PACK_NAME_RE

    # --- Path traversal regression tests (required by design spec) ---

    def test_rejects_double_dot_traversal(self):
        """'../traversal' must be rejected — path traversal attempt."""
        assert not self.re.match("../traversal")

    def test_rejects_parent_relative(self):
        """'../parent' must be rejected — path traversal attempt."""
        assert not self.re.match("../parent")

    def test_rejects_deep_traversal(self):
        """'../../etc/passwd' must be rejected."""
        assert not self.re.match("../../etc/passwd")

    # --- Spaces regression test (required by design spec) ---

    def test_rejects_name_with_spaces(self):
        """'name with spaces' must be rejected."""
        assert not self.re.match("name with spaces")

    def test_rejects_leading_space(self):
        assert not self.re.match(" physics")

    def test_rejects_trailing_space(self):
        assert not self.re.match("physics ")

    # --- Other unsafe characters ---

    def test_rejects_empty_string(self):
        assert not self.re.match("")

    def test_rejects_starts_with_hyphen(self):
        assert not self.re.match("-starts-with-hyphen")

    def test_rejects_starts_with_underscore(self):
        assert not self.re.match("_starts_with_underscore")

    def test_rejects_absolute_path(self):
        assert not self.re.match("/absolute/path")

    def test_rejects_forward_slash(self):
        assert not self.re.match("has/slash")

    def test_rejects_backslash(self):
        assert not self.re.match("has\\slash")

    def test_rejects_dot(self):
        assert not self.re.match("has.dot")

    def test_rejects_null_byte(self):
        assert not self.re.match("has\x00null")

    def test_rejects_65_chars(self):
        # 65 chars = one over the maximum
        name = "a" + "b" * 64
        assert len(name) == 65
        assert not self.re.match(name)

    def test_rejects_colon(self):
        assert not self.re.match("win:colon")

    def test_rejects_semicolon(self):
        assert not self.re.match("semi;colon")

    def test_rejects_star(self):
        assert not self.re.match("star*glob")

    def test_rejects_question_mark(self):
        assert not self.re.match("query?mark")


class TestPackNameReUsedInValidateManifest:
    """validate_manifest() must use the module-level PACK_NAME_RE, not a local copy."""

    def _make_manifest(self, name: str):
        from wikigr.packs.manifest import EvalScores, GraphStats, PackManifest

        return PackManifest(
            name=name,
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )

    def test_valid_name_no_errors(self):
        from wikigr.packs.manifest import validate_manifest

        manifest = self._make_manifest("valid-name")
        errors = validate_manifest(manifest)
        assert not any("invalid characters" in e for e in errors)

    def test_traversal_name_rejected_by_validate_manifest(self):
        """validate_manifest rejects '../traversal' via PACK_NAME_RE."""
        from wikigr.packs.manifest import validate_manifest

        manifest = self._make_manifest("../traversal")
        errors = validate_manifest(manifest)
        assert any("invalid characters" in e or "invalid" in e.lower() for e in errors)

    def test_space_name_rejected_by_validate_manifest(self):
        """validate_manifest rejects 'name with spaces' via PACK_NAME_RE."""
        from wikigr.packs.manifest import validate_manifest

        manifest = self._make_manifest("name with spaces")
        errors = validate_manifest(manifest)
        assert any("invalid characters" in e or "invalid" in e.lower() for e in errors)
