"""Tests for scripts/rebuild_all_packs.py — find_build_scripts, rebuild_pack."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test by file path to avoid package resolution issues.
# ---------------------------------------------------------------------------
_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "rebuild_all_packs.py"
_spec = importlib.util.spec_from_file_location("rebuild_all_packs", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["rebuild_all_packs"] = _mod
_spec.loader.exec_module(_mod)

find_build_scripts = _mod.find_build_scripts
rebuild_pack = _mod.rebuild_pack


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_process(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["python", "dummy.py"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# find_build_scripts
# ---------------------------------------------------------------------------


class TestFindBuildScripts:
    def test_finds_build_scripts(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build_rust_pack.py").write_text("")
        (scripts_dir / "build_python_pack.py").write_text("")
        (scripts_dir / "not_a_build.py").write_text("")

        with patch.object(_mod, "SCRIPTS_DIR", scripts_dir):
            result = find_build_scripts()

        names = [s.name for s in result]
        assert "build_rust_pack.py" in names
        assert "build_python_pack.py" in names
        assert "not_a_build.py" not in names

    def test_excludes_pack_from_issue(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build_pack_from_issue.py").write_text("")
        (scripts_dir / "build_rust_pack.py").write_text("")

        with patch.object(_mod, "SCRIPTS_DIR", scripts_dir):
            result = find_build_scripts()

        names = [s.name for s in result]
        assert "build_pack_from_issue.py" not in names
        assert "build_rust_pack.py" in names

    def test_excludes_ladybugdb_expert(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "build_ladybugdb_expert_pack.py").write_text("")
        (scripts_dir / "build_rust_pack.py").write_text("")

        with patch.object(_mod, "SCRIPTS_DIR", scripts_dir):
            result = find_build_scripts()

        names = [s.name for s in result]
        assert "build_ladybugdb_expert_pack.py" not in names

    def test_returns_sorted(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        for name in ("build_z_pack.py", "build_a_pack.py", "build_m_pack.py"):
            (scripts_dir / name).write_text("")

        with patch.object(_mod, "SCRIPTS_DIR", scripts_dir):
            result = find_build_scripts()

        names = [s.name for s in result]
        assert names == sorted(names)

    def test_empty_scripts_dir(self, tmp_path: Path) -> None:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        with patch.object(_mod, "SCRIPTS_DIR", scripts_dir):
            result = find_build_scripts()

        assert result == []


# ---------------------------------------------------------------------------
# rebuild_pack
# ---------------------------------------------------------------------------


class TestRebuildPack:
    def test_successful_build(self, tmp_path: Path) -> None:
        script = tmp_path / "build_rust_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.return_value = _make_completed_process(returncode=0)
            result = rebuild_pack(script)

        assert result["status"] == "success"
        assert result["pack"] == "rust"
        assert "elapsed" in result

    def test_failed_build(self, tmp_path: Path) -> None:
        script = tmp_path / "build_python_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.return_value = _make_completed_process(
                returncode=1, stderr="SomeError: something broke"
            )
            result = rebuild_pack(script)

        assert result["status"] == "failed"
        assert "error" in result

    def test_timeout_build(self, tmp_path: Path) -> None:
        script = tmp_path / "build_slow_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=1800)
            result = rebuild_pack(script)

        assert result["status"] == "timeout"

    def test_generic_exception(self, tmp_path: Path) -> None:
        script = tmp_path / "build_broken_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.side_effect = OSError("No such file or directory")
            result = rebuild_pack(script)

        assert result["status"] == "error"
        assert "No such file or directory" in result["error"]

    def test_cleans_old_db_directory(self, tmp_path: Path) -> None:
        """If the pack dir exists with a pack.db directory, it gets deleted."""
        pack_dir = tmp_path / "rust"
        pack_dir.mkdir()
        db_dir = pack_dir / "pack.db"
        db_dir.mkdir()
        (db_dir / "some_data").write_text("data")

        script = tmp_path / "build_rust_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.return_value = _make_completed_process(returncode=0)
            rebuild_pack(script)

        # The old db directory should have been removed
        assert not db_dir.exists()

    def test_cleans_old_db_file(self, tmp_path: Path) -> None:
        """If pack.db is a file (LadybugDB), it gets unlinked."""
        pack_dir = tmp_path / "rust"
        pack_dir.mkdir()
        db_file = pack_dir / "pack.db"
        db_file.write_text("ladybug data")

        script = tmp_path / "build_rust_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.return_value = _make_completed_process(returncode=0)
            rebuild_pack(script)

        assert not db_file.exists()

    def test_test_mode_flag(self, tmp_path: Path) -> None:
        script = tmp_path / "build_rust_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.return_value = _make_completed_process(returncode=0)
            rebuild_pack(script, test_mode=True)

        call_args = mock_run.call_args[0][0]
        assert "--test-mode" in call_args

    def test_subprocess_called_with_correct_command(self, tmp_path: Path) -> None:
        script = tmp_path / "build_rust_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.return_value = _make_completed_process(returncode=0)
            rebuild_pack(script, test_mode=False)

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == sys.executable
        assert call_args[1] == str(script)
        assert "--test-mode" not in call_args

    def test_multi_word_pack_name_extracts_correctly(self, tmp_path: Path) -> None:
        """Pack name extraction converts underscores to dashes for multi-word names."""
        script = tmp_path / "build_azure_functions_pack.py"
        script.write_text("")

        with (
            patch.object(_mod.subprocess, "run") as mock_run,
            patch.object(_mod, "PACKS_DIR", tmp_path),
        ):
            mock_run.return_value = _make_completed_process(returncode=0)
            result = rebuild_pack(script)

        assert result["pack"] == "azure-functions"
