"""Tests for pack information data models."""

from pathlib import Path

import pytest

from wikigr.agent.manifest import EvalScores, GraphStats, PackManifest
from wikigr.agent.models import PackInfo


class TestPackInfo:
    """Test PackInfo dataclass."""

    def test_creation_with_valid_data(self):
        """Test PackInfo creation with valid absolute paths."""
        manifest = PackManifest(
            name="physics-expert",
            version="1.0.0",
            description="Expert knowledge in physics",
            graph_stats=GraphStats(articles=5240, entities=18500, relationships=42300, size_mb=420),
            eval_scores=EvalScores(accuracy=0.94, hallucination_rate=0.04, citation_quality=0.98),
            source_urls=["https://en.wikipedia.org/wiki/Portal:Physics"],
            created="2026-02-24T10:30:00Z",
            license="CC-BY-SA-4.0",
        )

        pack_dir = Path("/home/user/.wikigr/packs/physics-expert").resolve()
        skill_path = (pack_dir / "skill.md").resolve()

        pack_info = PackInfo(
            name="physics-expert",
            version="1.0.0",
            path=pack_dir,
            manifest=manifest,
            skill_path=skill_path,
        )

        assert pack_info.name == "physics-expert"
        assert pack_info.version == "1.0.0"
        assert pack_info.path == pack_dir
        assert pack_info.manifest == manifest
        assert pack_info.skill_path == skill_path

    def test_path_must_be_absolute(self):
        """Test that relative paths are rejected."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        # Relative path should raise ValueError
        with pytest.raises(ValueError, match="Pack path must be absolute"):
            PackInfo(
                name="test-pack",
                version="1.0.0",
                path=Path("relative/path"),  # Relative path
                manifest=manifest,
                skill_path=Path("/absolute/skill.md"),
            )

    def test_skill_path_must_be_absolute(self):
        """Test that relative skill paths are rejected."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        # Relative skill path should raise ValueError
        with pytest.raises(ValueError, match="Skill path must be absolute"):
            PackInfo(
                name="test-pack",
                version="1.0.0",
                path=Path("/absolute/path"),
                manifest=manifest,
                skill_path=Path("relative/skill.md"),  # Relative path
            )

    def test_attributes_accessible(self):
        """Test that all attributes are accessible."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        pack_dir = Path("/home/user/.wikigr/packs/test-pack").resolve()
        skill_path = (pack_dir / "skill.md").resolve()

        pack_info = PackInfo(
            name="test-pack",
            version="1.0.0",
            path=pack_dir,
            manifest=manifest,
            skill_path=skill_path,
        )

        # All attributes should be accessible
        assert pack_info.name
        assert pack_info.version
        assert pack_info.path.is_absolute()
        assert pack_info.manifest
        assert pack_info.skill_path.is_absolute()
