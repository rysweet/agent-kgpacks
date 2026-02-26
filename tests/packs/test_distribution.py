"""Tests for pack distribution (packaging and unpackaging)."""

import json
import tarfile
from pathlib import Path

import pytest

from wikigr.agent.distribution import package_pack, unpackage_pack
from wikigr.agent.manifest import EvalScores, GraphStats, PackManifest, save_manifest


class TestPackagePack:
    """Test pack packaging into .tar.gz archives."""

    def create_test_pack(self, pack_dir: Path) -> None:
        """Create a complete test pack structure."""
        # Create manifest
        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test knowledge pack for packaging",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com/wiki"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)

        # Create pack.db (Kuzu database directory with some files)
        pack_db = pack_dir / "pack.db"
        pack_db.mkdir()
        (pack_db / "schema.kuzu").write_text("schema content")
        (pack_db / "data.kuzu").write_text("data content")

        # Create skill.md
        (pack_dir / "skill.md").write_text("# Test Skill\n\nSkill content here")

        # Create kg_config.json
        kg_config = {"pack_name": "test-pack", "embedding_model": "all-MiniLM-L6-v2"}
        (pack_dir / "kg_config.json").write_text(json.dumps(kg_config, indent=2))

        # Create README.md
        (pack_dir / "README.md").write_text("# Test Pack\n\nDocumentation here")

        # Create eval directory with files
        eval_dir = pack_dir / "eval"
        eval_dir.mkdir()
        (eval_dir / "questions.jsonl").write_text('{"question": "What is test?"}\n')
        (eval_dir / "answers.jsonl").write_text('{"answer": "Test is a test"}\n')

    def test_package_minimal_pack(self, tmp_path: Path):
        """Test packaging minimal pack structure."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        # Create minimal pack
        manifest = PackManifest(
            name="minimal-pack",
            version="1.0.0",
            description="Minimal pack",
            graph_stats=GraphStats(articles=10, entities=20, relationships=30, size_mb=1),
            eval_scores=EvalScores(accuracy=0.8, hallucination_rate=0.1, citation_quality=0.9),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "minimal-pack"}))

        # Package it
        output_path = tmp_path / "minimal-pack-1.0.0.tar.gz"
        result = package_pack(pack_dir, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.is_file()

        # Verify it's a valid tar.gz
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getnames()
            assert "manifest.json" in members
            assert "pack.db" in members
            assert "skill.md" in members
            assert "kg_config.json" in members

    def test_package_complete_pack(self, tmp_path: Path):
        """Test packaging complete pack with all optional files."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()
        self.create_test_pack(pack_dir)

        output_path = tmp_path / "test-pack-1.0.0.tar.gz"
        result = package_pack(pack_dir, output_path)

        assert result == output_path
        assert output_path.exists()

        # Verify all files are included
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getnames()
            assert "manifest.json" in members
            assert "pack.db" in members
            assert "pack.db/schema.kuzu" in members
            assert "pack.db/data.kuzu" in members
            assert "skill.md" in members
            assert "kg_config.json" in members
            assert "README.md" in members
            assert "eval" in members
            assert "eval/questions.jsonl" in members
            assert "eval/answers.jsonl" in members

    def test_package_excludes_cache_files(self, tmp_path: Path):
        """Test packaging excludes cache and temp files."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()
        self.create_test_pack(pack_dir)

        # Add files that should be excluded
        (pack_dir / "__pycache__").mkdir()
        (pack_dir / "__pycache__" / "test.pyc").write_text("bytecode")
        (pack_dir / ".temp").write_text("temp file")
        (pack_dir / "cache").mkdir()
        (pack_dir / "cache" / "data.cache").write_text("cache data")

        output_path = tmp_path / "test-pack-1.0.0.tar.gz"
        package_pack(pack_dir, output_path)

        # Verify cache files are excluded
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getnames()
            assert not any("__pycache__" in m for m in members)
            assert not any(".temp" in m for m in members)
            assert not any("cache" in m for m in members)

    def test_package_preserves_file_permissions(self, tmp_path: Path):
        """Test packaging preserves file permissions."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()
        self.create_test_pack(pack_dir)

        # Make skill.md executable (unusual but tests permission preservation)
        skill_path = pack_dir / "skill.md"
        skill_path.chmod(0o755)

        output_path = tmp_path / "test-pack-1.0.0.tar.gz"
        package_pack(pack_dir, output_path)

        # Verify permissions are preserved
        with tarfile.open(output_path, "r:gz") as tar:
            skill_info = tar.getmember("skill.md")
            # tarfile preserves mode
            assert skill_info.mode & 0o111  # Has execute bit

    def test_package_nonexistent_directory(self, tmp_path: Path):
        """Test packaging nonexistent directory raises error."""
        pack_dir = tmp_path / "nonexistent"
        output_path = tmp_path / "output.tar.gz"

        with pytest.raises(FileNotFoundError):
            package_pack(pack_dir, output_path)

    def test_package_creates_output_directory(self, tmp_path: Path):
        """Test packaging creates output directory if needed."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()
        self.create_test_pack(pack_dir)

        # Output to subdirectory that doesn't exist
        output_path = tmp_path / "archives" / "test-pack-1.0.0.tar.gz"
        result = package_pack(pack_dir, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.parent.is_dir()


class TestUnpackagePack:
    """Test pack unpackaging from .tar.gz archives."""

    def create_test_archive(self, archive_path: Path, pack_name: str = "test-pack") -> None:
        """Create a test pack archive."""
        # Create temporary pack directory
        pack_dir = archive_path.parent / "temp_pack"
        pack_dir.mkdir()

        # Create pack structure
        manifest = PackManifest(
            name=pack_name,
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
        (pack_dir / "pack.db" / "data.kuzu").write_text("data")
        (pack_dir / "skill.md").write_text("# Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": pack_name}))

        # Create archive
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(pack_dir / "manifest.json", arcname="manifest.json")
            tar.add(pack_dir / "pack.db", arcname="pack.db")
            tar.add(pack_dir / "skill.md", arcname="skill.md")
            tar.add(pack_dir / "kg_config.json", arcname="kg_config.json")

        # Cleanup temp directory
        import shutil

        shutil.rmtree(pack_dir)

    def test_unpackage_valid_archive(self, tmp_path: Path):
        """Test unpackaging valid pack archive."""
        archive_path = tmp_path / "test-pack-1.0.0.tar.gz"
        self.create_test_archive(archive_path)

        install_dir = tmp_path / "installed"
        result = unpackage_pack(archive_path, install_dir)

        assert result.exists()
        assert result.is_dir()
        assert (result / "manifest.json").exists()
        assert (result / "pack.db").is_dir()
        assert (result / "pack.db" / "data.kuzu").exists()
        assert (result / "skill.md").exists()
        assert (result / "kg_config.json").exists()

    def test_unpackage_creates_install_directory(self, tmp_path: Path):
        """Test unpackaging creates installation directory."""
        archive_path = tmp_path / "test-pack-1.0.0.tar.gz"
        self.create_test_archive(archive_path)

        install_dir = tmp_path / "new_dir" / "installed"
        result = unpackage_pack(archive_path, install_dir)

        assert install_dir.exists()
        assert install_dir.is_dir()
        assert result.exists()

    def test_unpackage_validates_before_installing(self, tmp_path: Path):
        """Test unpackaging validates pack structure before installing."""
        archive_path = tmp_path / "invalid-pack.tar.gz"

        # Create invalid archive (missing required files)
        with tarfile.open(archive_path, "w:gz") as tar:
            # Only add manifest, missing other required files
            manifest = PackManifest(
                name="invalid-pack",
                version="1.0.0",
                description="Invalid",
                graph_stats=GraphStats(articles=0, entities=0, relationships=0, size_mb=0),
                eval_scores=EvalScores(accuracy=0.5, hallucination_rate=0.5, citation_quality=0.5),
                source_urls=["https://example.com"],
                created="2026-02-24T10:00:00Z",
                license="CC-BY-SA-4.0",
            )
            manifest_file = tmp_path / "manifest.json"
            with open(manifest_file, "w") as f:
                json.dump(manifest.to_dict(), f)
            tar.add(manifest_file, arcname="manifest.json")
            manifest_file.unlink()

        install_dir = tmp_path / "installed"

        with pytest.raises(ValueError, match="validation"):
            unpackage_pack(archive_path, install_dir)

    def test_unpackage_nonexistent_archive(self, tmp_path: Path):
        """Test unpackaging nonexistent archive raises error."""
        archive_path = tmp_path / "nonexistent.tar.gz"
        install_dir = tmp_path / "installed"

        with pytest.raises(FileNotFoundError):
            unpackage_pack(archive_path, install_dir)

    def test_unpackage_invalid_tarfile(self, tmp_path: Path):
        """Test unpackaging invalid tar file raises error."""
        archive_path = tmp_path / "invalid.tar.gz"
        archive_path.write_text("not a tarfile")

        install_dir = tmp_path / "installed"

        with pytest.raises(tarfile.TarError):
            unpackage_pack(archive_path, install_dir)

    def test_unpackage_extracts_to_pack_name_directory(self, tmp_path: Path):
        """Test unpackaging extracts to directory named after pack."""
        archive_path = tmp_path / "my-pack-1.0.0.tar.gz"
        self.create_test_archive(archive_path, pack_name="my-pack")

        install_dir = tmp_path / "installed"
        result = unpackage_pack(archive_path, install_dir)

        # Should extract to install_dir/my-pack/
        assert result.name == "my-pack"
        assert result.parent == install_dir

    def test_unpackage_preserves_directory_structure(self, tmp_path: Path):
        """Test unpackaging preserves directory structure."""
        archive_path = tmp_path / "test-pack-1.0.0.tar.gz"

        # Create archive with subdirectories
        pack_dir = tmp_path / "temp_pack"
        pack_dir.mkdir()

        manifest = PackManifest(
            name="test-pack",
            version="1.0.0",
            description="Test",
            graph_stats=GraphStats(articles=1, entities=1, relationships=1, size_mb=1),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.1, citation_quality=0.9),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Skill")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "test-pack"}))

        # Create nested eval structure
        eval_dir = pack_dir / "eval"
        eval_dir.mkdir()
        results_dir = eval_dir / "results"
        results_dir.mkdir()
        (results_dir / "test.json").write_text('{"score": 0.9}')

        # Create archive
        with tarfile.open(archive_path, "w:gz") as tar:
            for item in pack_dir.rglob("*"):
                if item.is_file():
                    arcname = str(item.relative_to(pack_dir))
                    tar.add(item, arcname=arcname)
                elif item.is_dir() and item != pack_dir:
                    tar.add(item, arcname=str(item.relative_to(pack_dir)), recursive=False)

        # Cleanup
        import shutil

        shutil.rmtree(pack_dir)

        # Unpackage
        install_dir = tmp_path / "installed"
        result = unpackage_pack(archive_path, install_dir)

        # Verify structure preserved
        assert (result / "eval" / "results" / "test.json").exists()
        content = (result / "eval" / "results" / "test.json").read_text()
        assert "score" in content
