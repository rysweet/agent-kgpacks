"""Tests for skill template generation."""

from pathlib import Path

from wikigr.packs.manifest import EvalScores, GraphStats, PackManifest
from wikigr.packs.skill_template import generate_skill_md


class TestGenerateSkillMd:
    """Test generate_skill_md function."""

    def test_basic_skill_generation(self):
        """Test basic skill.md generation."""
        manifest = PackManifest(
            name="physics-expert",
            version="1.0.0",
            description="Expert knowledge in quantum mechanics and relativity",
            graph_stats=GraphStats(articles=5240, entities=18500, relationships=42300, size_mb=420),
            eval_scores=EvalScores(accuracy=0.94, hallucination_rate=0.04, citation_quality=0.98),
            source_urls=["https://en.wikipedia.org/wiki/Portal:Physics"],
            created="2026-02-24T10:30:00Z",
            license="CC-BY-SA-4.0",
        )

        kg_config_path = Path("/home/user/.wikigr/packs/physics-expert/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # Check frontmatter
        assert "---" in skill_content
        assert "name: physics-expert" in skill_content
        assert "version: 1.0.0" in skill_content
        assert "description: Expert knowledge in quantum mechanics and relativity" in skill_content
        assert "triggers:" in skill_content

        # Check content sections
        assert "# Physics Expert Skill" in skill_content
        assert "5,240 articles" in skill_content
        assert "18,500 entities" in skill_content
        assert "42,300 relationships" in skill_content

        # Check quality metrics
        assert "Accuracy: 94.0%" in skill_content
        assert "Hallucination Rate: 4.0%" in skill_content
        assert "Citation Quality: 98.0%" in skill_content

        # Check license and sources
        assert "CC-BY-SA-4.0" in skill_content
        assert "https://en.wikipedia.org/wiki/Portal:Physics" in skill_content

    def test_frontmatter_structure(self):
        """Test that frontmatter has correct YAML structure."""
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

        kg_config_path = Path("/home/user/.wikigr/packs/test-pack/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # Frontmatter should be at the beginning
        lines = skill_content.split("\n")
        assert lines[0] == "---"

        # Find the closing ---
        closing_index = lines[1:].index("---") + 1
        assert closing_index > 0

        # Check frontmatter fields
        frontmatter = "\n".join(lines[: closing_index + 1])
        assert "name:" in frontmatter
        assert "version:" in frontmatter
        assert "description:" in frontmatter
        assert "triggers:" in frontmatter

    def test_physics_triggers(self):
        """Test that physics packs get appropriate triggers."""
        manifest = PackManifest(
            name="physics-expert",
            version="1.0.0",
            description="Physics knowledge",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        kg_config_path = Path("/test/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # Physics packs should get physics-related triggers
        assert '"physics"' in skill_content
        assert '"quantum"' in skill_content
        assert '"relativity"' in skill_content

    def test_biology_triggers(self):
        """Test that biology packs get appropriate triggers."""
        manifest = PackManifest(
            name="biology-expert",
            version="1.0.0",
            description="Biology knowledge",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        kg_config_path = Path("/test/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # Biology packs should get biology-related triggers
        assert '"biology"' in skill_content
        assert '"evolution"' in skill_content
        assert '"genetics"' in skill_content

    def test_history_triggers(self):
        """Test that history packs get appropriate triggers."""
        manifest = PackManifest(
            name="history-expert",
            version="1.0.0",
            description="History knowledge",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        kg_config_path = Path("/test/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # History packs should get history-related triggers
        assert '"history"' in skill_content
        assert '"historical"' in skill_content
        assert '"timeline"' in skill_content

    def test_multiple_sources(self):
        """Test that multiple source URLs are included."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=[
                "https://en.wikipedia.org/wiki/Portal:Physics",
                "https://arxiv.org/archive/physics",
                "https://example.com/data",
            ],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        kg_config_path = Path("/test/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # All source URLs should be present
        assert "https://en.wikipedia.org/wiki/Portal:Physics" in skill_content
        assert "https://arxiv.org/archive/physics" in skill_content
        assert "https://example.com/data" in skill_content

    def test_config_path_included(self):
        """Test that kg_config.json path is included."""
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

        kg_config_path = Path("/home/user/.wikigr/packs/test-pack/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # Config path should be in technical details
        assert str(kg_config_path) in skill_content

    def test_timestamp_included(self):
        """Test that creation timestamp is included."""
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

        kg_config_path = Path("/test/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # Creation timestamp should be included
        assert "2026-02-24T10:30:00Z" in skill_content

    def test_usage_examples_included(self):
        """Test that usage examples are included."""
        manifest = PackManifest(
            name="physics-expert",
            version="1.0.0",
            description="Physics knowledge",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:30:00Z",
            license="MIT",
        )

        kg_config_path = Path("/test/kg_config.json")
        skill_content = generate_skill_md(manifest, kg_config_path)

        # Usage section should exist with examples
        assert "## Usage" in skill_content
        assert "Example queries:" in skill_content
        assert "physics" in skill_content.lower()
