"""Tests for pack discovery."""

import json

import pytest

from wikigr.packs.discovery import discover_packs, is_valid_pack
from wikigr.packs.manifest import EvalScores, GraphStats, PackManifest, save_manifest


@pytest.fixture
def sample_manifest():
    """Create a sample PackManifest."""
    return PackManifest(
        name="test-pack",
        version="1.0.0",
        description="Test knowledge pack",
        graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
        eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
        source_urls=["https://example.com"],
        created="2026-02-24T10:30:00Z",
        license="MIT",
    )


@pytest.fixture
def valid_pack_dir(tmp_path, sample_manifest):
    """Create a valid pack directory for testing."""
    pack_dir = tmp_path / "test-pack"
    pack_dir.mkdir()

    # Create manifest.json
    save_manifest(sample_manifest, pack_dir)

    # Create pack.db directory (Kuzu database)
    (pack_dir / "pack.db").mkdir()

    # Create skill.md
    (pack_dir / "skill.md").write_text("# Test Pack Skill\n")

    # Create kg_config.json
    kg_config = {"retrieval": {"vector_k": 10}}
    (pack_dir / "kg_config.json").write_text(json.dumps(kg_config))

    return pack_dir


class TestIsValidPack:
    """Test is_valid_pack function."""

    def test_valid_pack_returns_true(self, valid_pack_dir):
        """Test that a valid pack is recognized."""
        assert is_valid_pack(valid_pack_dir) is True

    def test_missing_manifest_returns_false(self, tmp_path):
        """Test that pack without manifest.json is invalid."""
        pack_dir = tmp_path / "invalid-pack"
        pack_dir.mkdir()
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Skill\n")
        (pack_dir / "kg_config.json").write_text("{}")

        assert is_valid_pack(pack_dir) is False

    def test_missing_pack_db_returns_false(self, tmp_path, sample_manifest):
        """Test that pack without pack.db is invalid."""
        pack_dir = tmp_path / "invalid-pack"
        pack_dir.mkdir()
        save_manifest(sample_manifest, pack_dir)
        (pack_dir / "skill.md").write_text("# Skill\n")
        (pack_dir / "kg_config.json").write_text("{}")

        assert is_valid_pack(pack_dir) is False

    def test_missing_skill_md_returns_false(self, tmp_path, sample_manifest):
        """Test that pack without skill.md is invalid."""
        pack_dir = tmp_path / "invalid-pack"
        pack_dir.mkdir()
        save_manifest(sample_manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "kg_config.json").write_text("{}")

        assert is_valid_pack(pack_dir) is False

    def test_missing_kg_config_returns_false(self, tmp_path, sample_manifest):
        """Test that pack without kg_config.json is invalid."""
        pack_dir = tmp_path / "invalid-pack"
        pack_dir.mkdir()
        save_manifest(sample_manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Skill\n")

        assert is_valid_pack(pack_dir) is False

    def test_non_directory_returns_false(self, tmp_path):
        """Test that a file path returns False."""
        file_path = tmp_path / "not-a-directory.txt"
        file_path.write_text("test")

        assert is_valid_pack(file_path) is False

    def test_nonexistent_path_returns_false(self, tmp_path):
        """Test that a non-existent path returns False."""
        nonexistent = tmp_path / "does-not-exist"
        assert is_valid_pack(nonexistent) is False


class TestDiscoverPacks:
    """Test discover_packs function."""

    def test_discover_single_valid_pack(self, tmp_path, sample_manifest):
        """Test discovering a single valid pack."""
        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()

        # Create a valid pack
        pack_dir = packs_dir / "test-pack"
        pack_dir.mkdir()
        save_manifest(sample_manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test Pack\n")
        (pack_dir / "kg_config.json").write_text("{}")

        # Discover packs
        packs = discover_packs(packs_dir)

        assert len(packs) == 1
        assert packs[0].name == "test-pack"
        assert packs[0].version == "1.0.0"
        assert packs[0].path.is_absolute()
        assert packs[0].skill_path.is_absolute()

    def test_discover_multiple_packs(self, tmp_path):
        """Test discovering multiple valid packs."""
        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()

        # Create two valid packs
        for name in ["physics-expert", "biology-expert"]:
            pack_dir = packs_dir / name
            pack_dir.mkdir()

            manifest = PackManifest(
                name=name,
                version="1.0.0",
                description=f"Expert knowledge in {name.split('-')[0]}",
                graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
                eval_scores=EvalScores(
                    accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95
                ),
                source_urls=["https://example.com"],
                created="2026-02-24T10:30:00Z",
                license="MIT",
            )
            save_manifest(manifest, pack_dir)
            (pack_dir / "pack.db").mkdir()
            (pack_dir / "skill.md").write_text(f"# {name}\n")
            (pack_dir / "kg_config.json").write_text("{}")

        # Discover packs
        packs = discover_packs(packs_dir)

        assert len(packs) == 2
        pack_names = {pack.name for pack in packs}
        assert pack_names == {"physics-expert", "biology-expert"}

    def test_skip_invalid_packs(self, tmp_path, sample_manifest):
        """Test that invalid packs are skipped during discovery."""
        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()

        # Create one valid pack
        valid_dir = packs_dir / "valid-pack"
        valid_dir.mkdir()
        save_manifest(sample_manifest, valid_dir)
        (valid_dir / "pack.db").mkdir()
        (valid_dir / "skill.md").write_text("# Valid\n")
        (valid_dir / "kg_config.json").write_text("{}")

        # Create one invalid pack (missing skill.md)
        invalid_dir = packs_dir / "invalid-pack"
        invalid_dir.mkdir()
        save_manifest(sample_manifest, invalid_dir)
        (invalid_dir / "pack.db").mkdir()
        (invalid_dir / "kg_config.json").write_text("{}")

        # Discover packs
        packs = discover_packs(packs_dir)

        # Only valid pack should be discovered
        assert len(packs) == 1
        assert packs[0].name == "test-pack"

    def test_empty_directory_returns_empty_list(self, tmp_path):
        """Test that empty packs directory returns empty list."""
        packs_dir = tmp_path / "empty-packs"
        packs_dir.mkdir()

        packs = discover_packs(packs_dir)
        assert packs == []

    def test_nonexistent_directory_returns_empty_list(self, tmp_path):
        """Test that non-existent directory returns empty list."""
        nonexistent = tmp_path / "does-not-exist"
        packs = discover_packs(nonexistent)
        assert packs == []

    def test_skip_files_in_packs_dir(self, tmp_path, sample_manifest):
        """Test that files in packs directory are skipped."""
        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()

        # Create a file (should be skipped)
        (packs_dir / "not-a-pack.txt").write_text("test")

        # Create a valid pack
        pack_dir = packs_dir / "valid-pack"
        pack_dir.mkdir()
        save_manifest(sample_manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Valid\n")
        (pack_dir / "kg_config.json").write_text("{}")

        # Discover packs
        packs = discover_packs(packs_dir)

        # Only the directory should be processed
        assert len(packs) == 1

    def test_pack_paths_are_absolute(self, tmp_path, sample_manifest):
        """Test that discovered pack paths are absolute."""
        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()

        pack_dir = packs_dir / "test-pack"
        pack_dir.mkdir()
        save_manifest(sample_manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test\n")
        (pack_dir / "kg_config.json").write_text("{}")

        packs = discover_packs(packs_dir)

        assert len(packs) == 1
        assert packs[0].path.is_absolute()
        assert packs[0].skill_path.is_absolute()
