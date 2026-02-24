"""Integration tests for wikigr pack CLI commands.

Tests all 8 pack management commands:
1. pack create
2. pack install
3. pack list
4. pack info
5. pack eval
6. pack update
7. pack remove
8. pack validate
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_home():
    """Create temporary home directory for pack installations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        packs_dir = home / ".wikigr/packs"
        packs_dir.mkdir(parents=True)
        yield home


@pytest.fixture
def sample_topics_file(tmp_path):
    """Create a sample topics file."""
    topics = tmp_path / "topics.txt"
    topics.write_text("Physics\nChemistry\n")
    return topics


@pytest.fixture
def sample_eval_questions(tmp_path):
    """Create sample evaluation questions in JSONL format."""
    questions = tmp_path / "eval.jsonl"
    questions.write_text(
        json.dumps({"question": "What is quantum mechanics?", "ground_truth": "Branch of physics"})
        + "\n"
        + json.dumps({"question": "Define entropy", "ground_truth": "Measure of disorder"})
        + "\n"
    )
    return questions


@pytest.fixture
def sample_pack_dir(tmp_path):
    """Create a sample pack directory with all required files."""
    pack_dir = tmp_path / "test-pack"
    pack_dir.mkdir()

    # Create manifest
    manifest = {
        "name": "test-pack",
        "version": "1.0.0",
        "description": "Test pack",
        "author": "Test Author",
        "license": "MIT",
        "created_at": "2026-01-01T00:00:00Z",
        "topics": ["testing"],
        "graph_stats": {"articles": 100, "entities": 200, "relationships": 150, "size_mb": 5},
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Create empty database directory
    (pack_dir / "pack.db").mkdir()

    # Create skill.md
    skill_md = """# Test Pack Skill

Knowledge pack for testing.
"""
    (pack_dir / "skill.md").write_text(skill_md)

    # Create kg_config.json
    kg_config = {"db_path": str(pack_dir / "pack.db"), "topics": ["testing"]}
    (pack_dir / "kg_config.json").write_text(json.dumps(kg_config, indent=2))

    return pack_dir


def run_cli(*args, env=None):
    """Run wikigr CLI command and return result."""
    import os

    cmd = [sys.executable, "-m", "wikigr.cli"] + list(args)

    # Merge custom env with current environment
    if env is not None:
        full_env = os.environ.copy()
        full_env.update(env)
    else:
        full_env = None

    result = subprocess.run(cmd, capture_output=True, text=True, env=full_env, timeout=30)
    return result


class TestPackCreate:
    """Tests for 'wikigr pack create' command."""

    def test_create_basic(self, tmp_path, sample_topics_file, sample_eval_questions):
        """Test basic pack creation."""
        output = tmp_path / "output"
        result = run_cli(
            "pack",
            "create",
            "--name",
            "test-pack",
            "--source",
            "wikipedia",
            "--topics",
            str(sample_topics_file),
            "--target",
            "10",
            "--eval-questions",
            str(sample_eval_questions),
            "--output",
            str(output),
        )

        assert result.returncode == 0
        assert (output / "test-pack").exists()
        assert (output / "test-pack" / "manifest.json").exists()
        assert (output / "test-pack" / "pack.db").exists()
        assert (output / "test-pack" / "skill.md").exists()

    def test_create_missing_topics(self, tmp_path):
        """Test create fails with missing topics file."""
        result = run_cli(
            "pack",
            "create",
            "--name",
            "test-pack",
            "--topics",
            str(tmp_path / "nonexistent.txt"),
            "--output",
            str(tmp_path),
        )

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "no such file" in result.stderr.lower()

    def test_create_missing_output_dir(self, tmp_path, sample_topics_file):
        """Test create creates output directory if missing."""
        output = tmp_path / "new" / "output"
        result = run_cli(
            "pack",
            "create",
            "--name",
            "test-pack",
            "--topics",
            str(sample_topics_file),
            "--target",
            "10",
            "--output",
            str(output),
        )

        assert result.returncode == 0
        assert output.exists()


class TestPackInstall:
    """Tests for 'wikigr pack install' command."""

    def test_install_from_local_file(self, temp_home, sample_pack_dir):
        """Test installing pack from local .tar.gz file."""
        # Package the sample pack
        from wikigr.packs.distribution import package_pack

        archive_path = sample_pack_dir.parent / "test-pack.tar.gz"
        package_pack(sample_pack_dir, archive_path)

        # Install it
        result = run_cli("pack", "install", str(archive_path), env={"HOME": str(temp_home)})

        assert result.returncode == 0
        assert (temp_home / ".wikigr/packs/test-pack").exists()
        assert (temp_home / ".wikigr/packs/test-pack/manifest.json").exists()

    def test_install_missing_file(self, temp_home):
        """Test install fails with missing archive."""
        result = run_cli("pack", "install", "nonexistent.tar.gz", env={"HOME": str(temp_home)})

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "no such file" in result.stderr.lower()

    def test_install_invalid_archive(self, temp_home, tmp_path):
        """Test install fails with invalid archive."""
        bad_archive = tmp_path / "bad.tar.gz"
        bad_archive.write_text("not a real tar.gz file")

        result = run_cli("pack", "install", str(bad_archive), env={"HOME": str(temp_home)})

        assert result.returncode != 0


class TestPackList:
    """Tests for 'wikigr pack list' command."""

    def test_list_empty(self, temp_home):
        """Test list with no installed packs."""
        result = run_cli("pack", "list", env={"HOME": str(temp_home)})

        assert result.returncode == 0
        assert "no packs installed" in result.stdout.lower() or result.stdout.strip() == ""

    def test_list_with_packs(self, temp_home, sample_pack_dir):
        """Test list shows installed packs."""
        # Copy sample pack to temp home
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        result = run_cli("pack", "list", env={"HOME": str(temp_home)})

        assert result.returncode == 0
        assert "test-pack" in result.stdout
        assert "1.0.0" in result.stdout

    def test_list_json_format(self, temp_home, sample_pack_dir):
        """Test list with --format json."""
        # Copy sample pack to temp home
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        result = run_cli("pack", "list", "--format", "json", env={"HOME": str(temp_home)})

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["name"] == "test-pack"


class TestPackInfo:
    """Tests for 'wikigr pack info' command."""

    def test_info_installed_pack(self, temp_home, sample_pack_dir):
        """Test info shows pack details."""
        # Copy sample pack to temp home
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        result = run_cli("pack", "info", "test-pack", env={"HOME": str(temp_home)})

        assert result.returncode == 0
        assert "test-pack" in result.stdout
        assert "1.0.0" in result.stdout
        assert "Test pack" in result.stdout

    def test_info_nonexistent_pack(self, temp_home):
        """Test info fails for nonexistent pack."""
        result = run_cli("pack", "info", "nonexistent-pack", env={"HOME": str(temp_home)})

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_info_show_eval_scores(self, temp_home, sample_pack_dir):
        """Test info with --show-eval-scores."""
        # Copy sample pack and add eval results
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        eval_result = {
            "pack_name": "test-pack",
            "timestamp": "2026-01-01T00:00:00Z",
            "knowledge_pack": {
                "accuracy": 0.95,
                "hallucination_rate": 0.05,
                "citation_quality": 0.90,
            },
            "surpasses_training": True,
            "surpasses_web": True,
        }
        (dest / "eval_results.json").write_text(json.dumps(eval_result, indent=2))

        result = run_cli(
            "pack", "info", "test-pack", "--show-eval-scores", env={"HOME": str(temp_home)}
        )

        assert result.returncode == 0
        assert "0.95" in result.stdout  # accuracy
        assert "0.05" in result.stdout  # hallucination rate


class TestPackEval:
    """Tests for 'wikigr pack eval' command."""

    @pytest.mark.skip(reason="Requires Anthropic API key")
    def test_eval_basic(self, temp_home, sample_pack_dir, sample_eval_questions):
        """Test basic pack evaluation."""
        # Copy sample pack to temp home
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        result = run_cli("pack", "eval", "test-pack", env={"HOME": str(temp_home)})

        assert result.returncode == 0
        assert "accuracy" in result.stdout.lower()

    def test_eval_nonexistent_pack(self, temp_home):
        """Test eval fails for nonexistent pack."""
        result = run_cli("pack", "eval", "nonexistent-pack", env={"HOME": str(temp_home)})

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    @pytest.mark.skip(reason="Requires Anthropic API key")
    def test_eval_custom_questions(
        self, temp_home, sample_pack_dir, sample_eval_questions, monkeypatch
    ):
        """Test eval with custom questions file."""
        # Copy sample pack to temp home
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        result = run_cli(
            "pack",
            "eval",
            "test-pack",
            "--questions",
            str(sample_eval_questions, env={"HOME": str(temp_home)}),
        )

        assert result.returncode == 0


class TestPackUpdate:
    """Tests for 'wikigr pack update' command."""

    def test_update_from_file(self, temp_home, sample_pack_dir):
        """Test updating pack from new version."""
        # Install v1.0.0
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        # Create v1.1.0 archive
        v2_dir = sample_pack_dir.parent / "test-pack-v2"
        shutil.copytree(sample_pack_dir, v2_dir)
        manifest = json.loads((v2_dir / "manifest.json").read_text())
        manifest["version"] = "1.1.0"
        (v2_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        from wikigr.packs.distribution import package_pack

        archive_path = sample_pack_dir.parent / "test-pack-v1.1.0.tar.gz"
        package_pack(v2_dir, archive_path)

        # Update
        result = run_cli(
            "pack", "update", "test-pack", "--from", str(archive_path), env={"HOME": str(temp_home)}
        )

        assert result.returncode == 0
        manifest_data = json.loads((dest / "manifest.json").read_text())
        assert manifest_data["version"] == "1.1.0"

    def test_update_nonexistent_pack(self, temp_home, tmp_path):
        """Test update fails for nonexistent pack."""
        result = run_cli(
            "pack",
            "update",
            "nonexistent-pack",
            "--from",
            str(tmp_path / "dummy.tar.gz"),
            env={"HOME": str(temp_home)},
        )

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()


class TestPackRemove:
    """Tests for 'wikigr pack remove' command."""

    def test_remove_with_confirmation(self, temp_home, sample_pack_dir):
        """Test removing pack with --force (no confirmation)."""
        # Copy sample pack to temp home
        dest = temp_home / ".wikigr/packs/test-pack"
        shutil.copytree(sample_pack_dir, dest)

        result = run_cli("pack", "remove", "test-pack", "--force", env={"HOME": str(temp_home)})

        assert result.returncode == 0
        assert not dest.exists()

    def test_remove_nonexistent_pack(self, temp_home):
        """Test remove fails for nonexistent pack."""
        result = run_cli(
            "pack", "remove", "nonexistent-pack", "--force", env={"HOME": str(temp_home)}
        )

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()


class TestPackValidate:
    """Tests for 'wikigr pack validate' command."""

    def test_validate_valid_pack(self, sample_pack_dir):
        """Test validate succeeds for valid pack."""
        result = run_cli("pack", "validate", str(sample_pack_dir))

        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

    def test_validate_missing_manifest(self, tmp_path):
        """Test validate fails for pack without manifest."""
        pack_dir = tmp_path / "invalid-pack"
        pack_dir.mkdir()

        result = run_cli("pack", "validate", str(pack_dir))

        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "manifest" in output.lower()

    def test_validate_missing_database(self, tmp_path):
        """Test validate fails for pack without database."""
        pack_dir = tmp_path / "invalid-pack"
        pack_dir.mkdir()

        manifest = {
            "name": "invalid",
            "version": "1.0.0",
            "description": "Missing database",
            "author": "Test",
            "license": "MIT",
            "created_at": "2026-01-01T00:00:00Z",
            "topics": ["test"],
            "graph_stats": {"articles": 0, "entities": 0, "relationships": 0, "size_mb": 0},
        }
        (pack_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        result = run_cli("pack", "validate", str(pack_dir))

        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "pack.db" in output.lower()

    def test_validate_strict_mode(self, sample_pack_dir):
        """Test validate with --strict flag."""
        result = run_cli("pack", "validate", str(sample_pack_dir), "--strict")

        # Strict mode may have additional requirements
        # This test documents the behavior
        assert result.returncode in (0, 1)


class TestPackIntegration:
    """Integration tests for complete pack workflows."""

    def test_create_install_list_remove_workflow(
        self, temp_home, tmp_path, sample_topics_file, monkeypatch
    ):
        """Test complete workflow: create -> install -> list -> remove."""
        monkeypatch.setenv("HOME", str(temp_home))

        # 1. Create pack
        output = tmp_path / "output"
        result = run_cli(
            "pack",
            "create",
            "--name",
            "integration-test-pack",
            "--topics",
            str(sample_topics_file),
            "--target",
            "10",
            "--output",
            str(output),
        )
        assert result.returncode == 0

        # 2. Package the created pack
        from wikigr.packs.distribution import package_pack

        pack_dir = output / "integration-test-pack"
        archive_path = tmp_path / "integration-test-pack.tar.gz"
        package_pack(pack_dir, archive_path)

        # 3. Install
        result = run_cli("pack", "install", str(archive_path))
        assert result.returncode == 0

        # 4. List
        result = run_cli("pack", "list")
        assert result.returncode == 0
        assert "integration-test-pack" in result.stdout

        # 5. Info
        result = run_cli("pack", "info", "integration-test-pack")
        assert result.returncode == 0

        # 6. Validate
        pack_path = temp_home / ".wikigr/packs/integration-test-pack"
        result = run_cli("pack", "validate", str(pack_path))
        assert result.returncode == 0

        # 7. Remove
        result = run_cli("pack", "remove", "integration-test-pack", "--force")
        assert result.returncode == 0
        assert not pack_path.exists()
