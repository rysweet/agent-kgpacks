"""Tests for pack manifest parsing and validation."""

import json
from pathlib import Path

import pytest

from wikigr.agent.manifest import (
    EvalScores,
    GraphStats,
    PackManifest,
    load_manifest,
    save_manifest,
    validate_manifest,
)


class TestGraphStats:
    """Test GraphStats dataclass."""

    def test_creation(self):
        """Test GraphStats creation with valid data."""
        stats = GraphStats(
            articles=5240,
            entities=18500,
            relationships=42300,
            size_mb=420,
        )
        assert stats.articles == 5240
        assert stats.entities == 18500
        assert stats.relationships == 42300
        assert stats.size_mb == 420


class TestEvalScores:
    """Test EvalScores dataclass."""

    def test_creation(self):
        """Test EvalScores creation with valid data."""
        scores = EvalScores(
            accuracy=0.94,
            hallucination_rate=0.04,
            citation_quality=0.98,
        )
        assert scores.accuracy == 0.94
        assert scores.hallucination_rate == 0.04
        assert scores.citation_quality == 0.98


class TestPackManifest:
    """Test PackManifest dataclass."""

    def test_creation_minimal(self):
        """Test PackManifest creation with minimal data."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        assert manifest.name == "test-pack"
        assert manifest.version == "1.0.0"
        assert manifest.description == "Test pack"
        assert isinstance(manifest.graph_stats, GraphStats)
        assert isinstance(manifest.eval_scores, EvalScores)
        assert manifest.source_urls == ["https://example.com"]
        assert manifest.license == "CC-BY-SA-4.0"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        data = manifest.to_dict()
        assert data["name"] == "test-pack"
        assert data["version"] == "1.0.0"
        assert data["graph_stats"]["articles"] == 100
        assert data["eval_scores"]["accuracy"] == 0.9

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "name": "test-pack",
            "version": "1.0.0",
            "description": "Test pack",
            "graph_stats": {
                "articles": 100,
                "entities": 200,
                "relationships": 300,
                "size_mb": 10,
            },
            "eval_scores": {
                "accuracy": 0.9,
                "hallucination_rate": 0.05,
                "citation_quality": 0.95,
            },
            "source_urls": ["https://example.com"],
            "created": "2026-02-24T10:00:00Z",
            "license": "CC-BY-SA-4.0",
        }
        manifest = PackManifest.from_dict(data)
        assert manifest.name == "test-pack"
        assert manifest.version == "1.0.0"
        assert manifest.graph_stats.articles == 100
        assert manifest.eval_scores.accuracy == 0.9


class TestLoadManifest:
    """Test load_manifest function."""

    def test_load_valid_manifest(self, tmp_path: Path):
        """Test loading valid manifest.json."""
        manifest_data = {
            "name": "test-pack",
            "version": "1.0.0",
            "description": "Test pack",
            "graph_stats": {
                "articles": 100,
                "entities": 200,
                "relationships": 300,
                "size_mb": 10,
            },
            "eval_scores": {
                "accuracy": 0.9,
                "hallucination_rate": 0.05,
                "citation_quality": 0.95,
            },
            "source_urls": ["https://example.com"],
            "created": "2026-02-24T10:00:00Z",
            "license": "CC-BY-SA-4.0",
        }

        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()
        manifest_file = pack_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest_data, indent=2))

        manifest = load_manifest(pack_dir)
        assert manifest.name == "test-pack"
        assert manifest.version == "1.0.0"
        assert manifest.graph_stats.articles == 100

    def test_load_missing_manifest(self, tmp_path: Path):
        """Test loading from directory with no manifest.json."""
        pack_dir = tmp_path / "no-manifest"
        pack_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="manifest.json not found"):
            load_manifest(pack_dir)

    def test_load_invalid_json(self, tmp_path: Path):
        """Test loading manifest with invalid JSON."""
        pack_dir = tmp_path / "invalid-json"
        pack_dir.mkdir()
        manifest_file = pack_dir / "manifest.json"
        manifest_file.write_text("not valid json {")

        with pytest.raises(json.JSONDecodeError):
            load_manifest(pack_dir)


class TestSaveManifest:
    """Test save_manifest function."""

    def test_save_manifest(self, tmp_path: Path):
        """Test saving manifest to file."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )

        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        save_manifest(manifest, pack_dir)

        manifest_file = pack_dir / "manifest.json"
        assert manifest_file.exists()

        # Verify we can load it back
        loaded = load_manifest(pack_dir)
        assert loaded.name == manifest.name
        assert loaded.version == manifest.version

    def test_save_creates_directory(self, tmp_path: Path):
        """Test that save_manifest creates directory if needed."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )

        pack_dir = tmp_path / "new-pack"

        save_manifest(manifest, pack_dir)

        assert pack_dir.exists()
        assert (pack_dir / "manifest.json").exists()


class TestValidateManifest:
    """Test validate_manifest function."""

    def test_valid_manifest(self):
        """Test validation of valid manifest."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        errors = validate_manifest(manifest)
        assert len(errors) == 0

    def test_empty_name(self):
        """Test validation catches empty name."""
        manifest = PackManifest(
            name="",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        errors = validate_manifest(manifest)
        assert any("name cannot be empty" in e for e in errors)

    def test_invalid_version(self):
        """Test validation catches invalid version."""
        manifest = PackManifest(
            name="test-pack",
            version="not-semver",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        errors = validate_manifest(manifest)
        assert any("invalid semantic version" in e.lower() for e in errors)

    def test_negative_stats(self):
        """Test validation catches negative statistics."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=-100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        errors = validate_manifest(manifest)
        assert any("articles" in e and "negative" in e.lower() for e in errors)

    def test_invalid_eval_scores(self):
        """Test validation catches invalid eval scores (not in 0-1 range)."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=1.5, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        errors = validate_manifest(manifest)
        assert any("accuracy" in e.lower() and ("0" in e and "1" in e) for e in errors)

    def test_invalid_timestamp(self):
        """Test validation catches invalid ISO timestamp."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="not-a-timestamp",
            license="CC-BY-SA-4.0",
        )
        errors = validate_manifest(manifest)
        assert any("created" in e.lower() and "iso" in e.lower() for e in errors)

    def test_empty_source_urls(self):
        """Test validation catches empty source_urls."""
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=[],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        errors = validate_manifest(manifest)
        assert any("source_urls" in e.lower() and "empty" in e.lower() for e in errors)
