"""Tests for pack registry."""

import pytest

from wikigr.packs.manifest import EvalScores, GraphStats, PackManifest, save_manifest
from wikigr.packs.registry import PackRegistry


@pytest.fixture
def packs_dir_with_packs(tmp_path):
    """Create a packs directory with multiple valid packs."""
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()

    # Create physics pack
    physics_dir = packs_dir / "physics-expert"
    physics_dir.mkdir()
    physics_manifest = PackManifest(
        name="physics-expert",
        version="1.0.0",
        description="Expert knowledge in physics",
        graph_stats=GraphStats(articles=5240, entities=18500, relationships=42300, size_mb=420),
        eval_scores=EvalScores(accuracy=0.94, hallucination_rate=0.04, citation_quality=0.98),
        source_urls=["https://en.wikipedia.org/wiki/Portal:Physics"],
        created="2026-02-24T10:30:00Z",
        license="CC-BY-SA-4.0",
    )
    save_manifest(physics_manifest, physics_dir)
    (physics_dir / "pack.db").mkdir()
    (physics_dir / "skill.md").write_text("# Physics Expert\n")
    (physics_dir / "kg_config.json").write_text("{}")

    # Create biology pack
    biology_dir = packs_dir / "biology-expert"
    biology_dir.mkdir()
    biology_manifest = PackManifest(
        name="biology-expert",
        version="2.0.0",
        description="Expert knowledge in biology",
        graph_stats=GraphStats(articles=3100, entities=9500, relationships=21000, size_mb=250),
        eval_scores=EvalScores(accuracy=0.92, hallucination_rate=0.05, citation_quality=0.96),
        source_urls=["https://en.wikipedia.org/wiki/Portal:Biology"],
        created="2026-02-24T11:00:00Z",
        license="CC-BY-SA-4.0",
    )
    save_manifest(biology_manifest, biology_dir)
    (biology_dir / "pack.db").mkdir()
    (biology_dir / "skill.md").write_text("# Biology Expert\n")
    (biology_dir / "kg_config.json").write_text("{}")

    return packs_dir


class TestPackRegistry:
    """Test PackRegistry class."""

    def test_initialization_with_empty_directory(self, tmp_path):
        """Test initializing registry with empty directory."""
        packs_dir = tmp_path / "empty-packs"
        packs_dir.mkdir()

        registry = PackRegistry(packs_dir)

        assert registry.packs_dir == packs_dir
        assert len(registry.packs) == 0

    def test_initialization_with_packs(self, packs_dir_with_packs):
        """Test initializing registry with existing packs."""
        registry = PackRegistry(packs_dir_with_packs)

        assert len(registry.packs) == 2
        assert "physics-expert" in registry.packs
        assert "biology-expert" in registry.packs

    def test_initialization_with_nonexistent_directory(self, tmp_path):
        """Test initializing registry with non-existent directory."""
        nonexistent = tmp_path / "does-not-exist"
        registry = PackRegistry(nonexistent)

        # Should not raise error, just have no packs
        assert len(registry.packs) == 0

    def test_get_pack_existing(self, packs_dir_with_packs):
        """Test getting an existing pack by name."""
        registry = PackRegistry(packs_dir_with_packs)

        pack_info = registry.get_pack("physics-expert")

        assert pack_info is not None
        assert pack_info.name == "physics-expert"
        assert pack_info.version == "1.0.0"

    def test_get_pack_nonexistent(self, packs_dir_with_packs):
        """Test getting a non-existent pack returns None."""
        registry = PackRegistry(packs_dir_with_packs)

        pack_info = registry.get_pack("nonexistent-pack")

        assert pack_info is None

    def test_list_packs(self, packs_dir_with_packs):
        """Test listing all packs."""
        registry = PackRegistry(packs_dir_with_packs)

        packs = registry.list_packs()

        assert len(packs) == 2
        pack_names = [pack.name for pack in packs]
        assert "physics-expert" in pack_names
        assert "biology-expert" in pack_names

    def test_list_packs_sorted_by_name(self, packs_dir_with_packs):
        """Test that list_packs returns packs sorted by name."""
        registry = PackRegistry(packs_dir_with_packs)

        packs = registry.list_packs()

        # Should be sorted alphabetically
        pack_names = [pack.name for pack in packs]
        assert pack_names == sorted(pack_names)

    def test_list_packs_empty_registry(self, tmp_path):
        """Test listing packs from empty registry."""
        packs_dir = tmp_path / "empty-packs"
        packs_dir.mkdir()
        registry = PackRegistry(packs_dir)

        packs = registry.list_packs()

        assert packs == []

    def test_has_pack_existing(self, packs_dir_with_packs):
        """Test has_pack returns True for existing pack."""
        registry = PackRegistry(packs_dir_with_packs)

        assert registry.has_pack("physics-expert") is True
        assert registry.has_pack("biology-expert") is True

    def test_has_pack_nonexistent(self, packs_dir_with_packs):
        """Test has_pack returns False for non-existent pack."""
        registry = PackRegistry(packs_dir_with_packs)

        assert registry.has_pack("nonexistent-pack") is False

    def test_count(self, packs_dir_with_packs):
        """Test counting packs in registry."""
        registry = PackRegistry(packs_dir_with_packs)

        assert registry.count() == 2

    def test_count_empty_registry(self, tmp_path):
        """Test counting packs in empty registry."""
        packs_dir = tmp_path / "empty-packs"
        packs_dir.mkdir()
        registry = PackRegistry(packs_dir)

        assert registry.count() == 0

    def test_refresh_discovers_new_pack(self, tmp_path):
        """Test that refresh picks up newly added packs."""
        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()

        # Initialize registry with empty directory
        registry = PackRegistry(packs_dir)
        assert registry.count() == 0

        # Add a new pack
        new_pack_dir = packs_dir / "new-pack"
        new_pack_dir.mkdir()
        manifest = PackManifest(
            name="new-pack",
            version="1.0.0",
            description="New pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )
        save_manifest(manifest, new_pack_dir)
        (new_pack_dir / "pack.db").mkdir()
        (new_pack_dir / "skill.md").write_text("# New Pack\n")
        (new_pack_dir / "kg_config.json").write_text("{}")

        # Refresh registry
        registry.refresh()

        # New pack should now be in registry
        assert registry.count() == 1
        assert registry.has_pack("new-pack")

    def test_refresh_removes_deleted_pack(self, packs_dir_with_packs):
        """Test that refresh removes packs that no longer exist."""
        registry = PackRegistry(packs_dir_with_packs)
        assert registry.count() == 2

        # Delete a pack directory
        import shutil

        physics_dir = packs_dir_with_packs / "physics-expert"
        shutil.rmtree(physics_dir)

        # Refresh registry
        registry.refresh()

        # Physics pack should be gone
        assert registry.count() == 1
        assert not registry.has_pack("physics-expert")
        assert registry.has_pack("biology-expert")

    def test_pack_info_has_absolute_paths(self, packs_dir_with_packs):
        """Test that PackInfo objects have absolute paths."""
        registry = PackRegistry(packs_dir_with_packs)

        pack_info = registry.get_pack("physics-expert")

        assert pack_info.path.is_absolute()
        assert pack_info.skill_path.is_absolute()

    def test_registry_ignores_invalid_packs(self, tmp_path):
        """Test that registry ignores invalid pack directories."""
        packs_dir = tmp_path / "packs"
        packs_dir.mkdir()

        # Create a valid pack
        valid_dir = packs_dir / "valid-pack"
        valid_dir.mkdir()
        manifest = PackManifest(
            name="valid-pack",
            version="1.0.0",
            description="Valid pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )
        save_manifest(manifest, valid_dir)
        (valid_dir / "pack.db").mkdir()
        (valid_dir / "skill.md").write_text("# Valid\n")
        (valid_dir / "kg_config.json").write_text("{}")

        # Create an invalid pack (missing skill.md)
        invalid_dir = packs_dir / "invalid-pack"
        invalid_dir.mkdir()
        save_manifest(manifest, invalid_dir)
        (invalid_dir / "pack.db").mkdir()
        (invalid_dir / "kg_config.json").write_text("{}")

        # Initialize registry
        registry = PackRegistry(packs_dir)

        # Only valid pack should be registered
        assert registry.count() == 1
        assert registry.has_pack("valid-pack")
        assert not registry.has_pack("invalid-pack")
