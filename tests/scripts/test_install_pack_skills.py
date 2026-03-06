"""Tests for scripts/install_pack_skills.py — load_manifest, generate_skill_md, find_all_packs."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test by file path to avoid package resolution issues.
# ---------------------------------------------------------------------------
_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "install_pack_skills.py"
_spec = importlib.util.spec_from_file_location("install_pack_skills", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["install_pack_skills"] = _mod
_spec.loader.exec_module(_mod)

load_manifest = _mod.load_manifest
generate_skill_md = _mod.generate_skill_md
find_all_packs = _mod.find_all_packs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MANIFEST = {
    "description": "Comprehensive Rust language reference with ownership, lifetimes, and async patterns.",
    "graph_stats": {"articles": 120, "entities": 450, "relationships": 980},
    "source_urls": [
        "https://doc.rust-lang.org/book/",
        "https://doc.rust-lang.org/std/",
    ],
    "tags": ["rust", "ownership", "lifetimes", "async"],
}


@pytest.fixture()
def pack_with_manifest(tmp_path: Path) -> Path:
    """Create a minimal pack directory with manifest.json and pack.db."""
    pack_dir = tmp_path / "rust-expert"
    pack_dir.mkdir()
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(json.dumps(SAMPLE_MANIFEST))
    # Create a stub pack.db file
    (pack_dir / "pack.db").write_text("")
    return pack_dir


@pytest.fixture()
def pack_without_manifest(tmp_path: Path) -> Path:
    """Create a pack directory with NO manifest.json."""
    pack_dir = tmp_path / "empty-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.db").write_text("")
    return pack_dir


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------


class TestLoadManifest:
    def test_loads_valid_manifest(self, pack_with_manifest: Path) -> None:
        result = load_manifest(pack_with_manifest)
        assert result is not None
        assert result["description"] == SAMPLE_MANIFEST["description"]
        assert result["graph_stats"]["articles"] == 120

    def test_returns_none_when_no_manifest(self, pack_without_manifest: Path) -> None:
        result = load_manifest(pack_without_manifest)
        assert result is None

    def test_returns_none_for_nonexistent_dir(self, tmp_path: Path) -> None:
        result = load_manifest(tmp_path / "does-not-exist")
        assert result is None

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        pack_dir = tmp_path / "bad-json"
        pack_dir.mkdir()
        (pack_dir / "manifest.json").write_text("{invalid json!!")
        with pytest.raises(json.JSONDecodeError):
            load_manifest(pack_dir)


# ---------------------------------------------------------------------------
# generate_skill_md
# ---------------------------------------------------------------------------


class TestGenerateSkillMd:
    def test_contains_frontmatter(self, pack_with_manifest: Path) -> None:
        md = generate_skill_md("rust-expert", SAMPLE_MANIFEST, pack_with_manifest)
        assert md.startswith("---")
        assert "name: rust-expert" in md
        assert 'description: "' in md

    def test_contains_pack_stats(self, pack_with_manifest: Path) -> None:
        md = generate_skill_md("rust-expert", SAMPLE_MANIFEST, pack_with_manifest)
        assert "120 articles" in md
        assert "450 entities" in md
        assert "980 relationships" in md

    def test_contains_source_urls(self, pack_with_manifest: Path) -> None:
        md = generate_skill_md("rust-expert", SAMPLE_MANIFEST, pack_with_manifest)
        assert "https://doc.rust-lang.org/book/" in md
        assert "https://doc.rust-lang.org/std/" in md

    def test_contains_db_path(self, pack_with_manifest: Path) -> None:
        md = generate_skill_md("rust-expert", SAMPLE_MANIFEST, pack_with_manifest)
        resolved = str((pack_with_manifest / "pack.db").resolve())
        assert resolved in md

    def test_contains_python_usage_snippet(self, pack_with_manifest: Path) -> None:
        md = generate_skill_md("rust-expert", SAMPLE_MANIFEST, pack_with_manifest)
        assert "KnowledgeGraphAgent" in md
        assert "agent.query" in md

    def test_short_description_is_concise(self, pack_with_manifest: Path) -> None:
        md = generate_skill_md("rust-expert", SAMPLE_MANIFEST, pack_with_manifest)
        # The frontmatter description line should exist and be under 120 chars
        for line in md.splitlines():
            if line.startswith("description:"):
                # Remove the `description: "` prefix and trailing `"`
                desc = line.split('"')[1]
                assert len(desc) <= 120
                break

    def test_handles_missing_graph_stats(self, pack_with_manifest: Path) -> None:
        manifest_no_stats = {
            "description": "A pack without stats",
            "source_urls": [],
            "tags": [],
        }
        md = generate_skill_md("no-stats-pack", manifest_no_stats, pack_with_manifest)
        assert "0 articles" in md
        assert "0 entities" in md

    def test_uses_shorter_template_for_long_names(self, pack_with_manifest: Path) -> None:
        """When the primary template > 120 chars, the shorter fallback template is used."""
        long_name = "extremely-long-name-that-exceeds-many-characters-expert"
        manifest = {**SAMPLE_MANIFEST, "tags": ["a", "b"]}
        md = generate_skill_md(long_name, manifest, pack_with_manifest)
        for line in md.splitlines():
            if line.startswith("description:"):
                desc = line.split('"')[1]
                # The fallback uses "Expert {base} knowledge. Use for {base} questions and coding."
                # which is shorter than the primary template for the same base name.
                assert "Expert " in desc
                assert "questions and coding" in desc
                # The primary template would contain "Use when coding with or asking about"
                assert "Use when coding with or asking about" not in desc
                break

    def test_title_replaces_dashes(self, pack_with_manifest: Path) -> None:
        md = generate_skill_md("rust-expert", SAMPLE_MANIFEST, pack_with_manifest)
        assert "# Rust Expert" in md


# ---------------------------------------------------------------------------
# find_all_packs
# ---------------------------------------------------------------------------


class TestFindAllPacks:
    def test_finds_packs_with_db_and_manifest(self, tmp_path: Path) -> None:
        packs_dir = tmp_path / "data" / "packs"
        packs_dir.mkdir(parents=True)

        # Good pack
        p1 = packs_dir / "alpha-expert"
        p1.mkdir()
        (p1 / "pack.db").write_text("")
        (p1 / "manifest.json").write_text(json.dumps(SAMPLE_MANIFEST))

        with patch.object(_mod, "PACKS_DIR", packs_dir):
            result = find_all_packs()

        assert len(result) == 1
        assert result[0]["name"] == "alpha-expert"
        assert result[0]["manifest"]["graph_stats"]["articles"] == 120

    def test_skips_packs_without_db(self, tmp_path: Path) -> None:
        packs_dir = tmp_path / "data" / "packs"
        packs_dir.mkdir(parents=True)
        p1 = packs_dir / "no-db"
        p1.mkdir()
        (p1 / "manifest.json").write_text(json.dumps(SAMPLE_MANIFEST))

        with patch.object(_mod, "PACKS_DIR", packs_dir):
            result = find_all_packs()

        assert len(result) == 0

    def test_skips_packs_without_manifest(self, tmp_path: Path) -> None:
        packs_dir = tmp_path / "data" / "packs"
        packs_dir.mkdir(parents=True)
        p1 = packs_dir / "no-manifest"
        p1.mkdir()
        (p1 / "pack.db").write_text("")

        with patch.object(_mod, "PACKS_DIR", packs_dir):
            result = find_all_packs()

        assert len(result) == 0

    def test_skips_non_directories(self, tmp_path: Path) -> None:
        packs_dir = tmp_path / "data" / "packs"
        packs_dir.mkdir(parents=True)
        # Create a file instead of a directory
        (packs_dir / "not-a-dir").write_text("I am a file")

        with patch.object(_mod, "PACKS_DIR", packs_dir):
            result = find_all_packs()

        assert len(result) == 0

    def test_returns_sorted_by_name(self, tmp_path: Path) -> None:
        packs_dir = tmp_path / "data" / "packs"
        packs_dir.mkdir(parents=True)
        for name in ("charlie", "alpha", "bravo"):
            d = packs_dir / name
            d.mkdir()
            (d / "pack.db").write_text("")
            (d / "manifest.json").write_text(json.dumps(SAMPLE_MANIFEST))

        with patch.object(_mod, "PACKS_DIR", packs_dir):
            result = find_all_packs()

        names = [p["name"] for p in result]
        assert names == ["alpha", "bravo", "charlie"]

    def test_empty_packs_dir(self, tmp_path: Path) -> None:
        packs_dir = tmp_path / "data" / "packs"
        packs_dir.mkdir(parents=True)

        with patch.object(_mod, "PACKS_DIR", packs_dir):
            result = find_all_packs()

        assert result == []
