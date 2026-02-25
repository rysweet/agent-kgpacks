"""Tests for pack structure validation."""

import json
from pathlib import Path

from wikigr.packs.manifest import EvalScores, GraphStats, PackManifest, save_manifest
from wikigr.packs.validator import validate_pack_structure


class TestValidatePackStructure:
    """Test validate_pack_structure function."""

    def create_minimal_pack(self, pack_dir: Path) -> PackManifest:
        """Create minimal valid pack structure."""
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
        save_manifest(manifest, pack_dir)
        return manifest

    def test_valid_pack_minimal(self, tmp_path: Path):
        """Test validation of minimal valid pack structure."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        # Create required files
        self.create_minimal_pack(pack_dir)
        (pack_dir / "pack.db").mkdir()  # Kuzu database directory
        (pack_dir / "skill.md").write_text("# Test Skill\n\nSkill content")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        errors = validate_pack_structure(pack_dir)
        assert len(errors) == 0

    def test_valid_pack_complete(self, tmp_path: Path):
        """Test validation of complete pack structure."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        # Create all files
        self.create_minimal_pack(pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))
        (pack_dir / "README.md").write_text("# README")

        # Create eval directory with files
        eval_dir = pack_dir / "eval"
        eval_dir.mkdir()
        (eval_dir / "questions.jsonl").write_text('{"question": "test"}\n')

        errors = validate_pack_structure(pack_dir)
        assert len(errors) == 0

    def test_missing_manifest(self, tmp_path: Path):
        """Test validation catches missing manifest.json."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        errors = validate_pack_structure(pack_dir)
        assert any("manifest.json" in e for e in errors)

    def test_missing_pack_db(self, tmp_path: Path):
        """Test validation catches missing pack.db."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        self.create_minimal_pack(pack_dir)
        (pack_dir / "skill.md").write_text("# Test Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        errors = validate_pack_structure(pack_dir)
        assert any("pack.db" in e for e in errors)

    def test_missing_skill_md(self, tmp_path: Path):
        """Test validation catches missing skill.md."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        self.create_minimal_pack(pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        errors = validate_pack_structure(pack_dir)
        assert any("skill.md" in e for e in errors)

    def test_missing_kg_config(self, tmp_path: Path):
        """Test validation catches missing kg_config.json."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        self.create_minimal_pack(pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test Skill")

        errors = validate_pack_structure(pack_dir)
        assert any("kg_config.json" in e for e in errors)

    def test_invalid_manifest_content(self, tmp_path: Path):
        """Test validation catches invalid manifest content."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        # Create manifest with empty name (invalid)
        manifest = PackManifest(
            name="",  # Invalid
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        errors = validate_pack_structure(pack_dir)
        assert any("name cannot be empty" in e for e in errors)

    def test_invalid_kg_config_json(self, tmp_path: Path):
        """Test validation catches invalid kg_config.json."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        self.create_minimal_pack(pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test Skill")
        (pack_dir / "kg_config.json").write_text("not valid json {")

        errors = validate_pack_structure(pack_dir)
        assert any("kg_config.json" in e and "json" in e.lower() for e in errors)

    def test_pack_db_accepts_file_or_directory(self, tmp_path: Path):
        """Test validation accepts pack.db as either file or directory."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        self.create_minimal_pack(pack_dir)
        # Pack.db as file is now valid (small databases)
        (pack_dir / "pack.db").write_text("valid kuzu database")
        (pack_dir / "skill.md").write_text("# Test Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        errors = validate_pack_structure(pack_dir)
        # Should pass - files are valid for pack.db
        assert not any("pack.db" in e and "directory" in e.lower() for e in errors)

    def test_optional_eval_directory(self, tmp_path: Path):
        """Test that eval directory is optional."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        self.create_minimal_pack(pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        # No eval directory - should still be valid
        errors = validate_pack_structure(pack_dir)
        assert len(errors) == 0

    def test_optional_readme(self, tmp_path: Path):
        """Test that README.md is optional."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        self.create_minimal_pack(pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Test Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        # No README.md - should still be valid
        errors = validate_pack_structure(pack_dir)
        assert len(errors) == 0
