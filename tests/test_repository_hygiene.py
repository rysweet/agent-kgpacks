"""Repository hygiene tests for issues #246 and #247.

Contracts:
  - launcher.py must NOT exist at the repo root (issue #247: imported amplihack.recipes,
    a package absent from pyproject.toml, causing ModuleNotFoundError on clean installs).
  - run.sh must NOT exist at the repo root (issue #246: contained hardcoded
    /tmp/amplihack-workstreams/ws-NNN paths and AMPLIHACK_TREE_ID session tokens).
  - workstreams*.json must NOT exist at the repo root (exposed internal workflow IDs
    and agent session metadata).
  - .gitignore must contain all three guard patterns to prevent future accidental commits.
  - pyproject.toml must NOT declare amplihack or amplihack.recipes as a dependency.
  - git check-ignore must confirm the three patterns are active.
"""

import itertools
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
GITIGNORE = REPO_ROOT / ".gitignore"


def _amplihack_only_in_comment(text: str) -> bool:
    """Return True if 'amplihack' only appears in comment lines (lines starting with #)."""
    for line in text.splitlines():
        stripped = line.strip()
        if "amplihack" in stripped.lower() and not stripped.startswith("#"):
            return False
    return True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gitignore_text() -> str:
    assert GITIGNORE.exists(), ".gitignore must exist at the repo root"
    return GITIGNORE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def gitignore_lines(gitignore_text: str) -> list[str]:
    return gitignore_text.splitlines()


@pytest.fixture(scope="module")
def pyproject_text() -> str:
    assert PYPROJECT.exists(), "pyproject.toml must exist at the repo root"
    return PYPROJECT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Artifact absence — files must not exist in the repo
# ---------------------------------------------------------------------------


class TestArtifactAbsence:
    """Orchestration artifacts must not be present in the working tree."""

    def test_launcher_py_absent(self):
        """launcher.py must not exist at the repo root (issue #247).

        launcher.py imported amplihack.recipes which is not in pyproject.toml.
        Its presence causes ModuleNotFoundError on clean installs.
        """
        assert not (REPO_ROOT / "launcher.py").exists(), (
            "launcher.py must not exist at the repo root. "
            "This file is an amplihack orchestration artifact that imports "
            "amplihack.recipes — a package absent from pyproject.toml."
        )

    def test_run_sh_absent(self):
        """run.sh must not exist at the repo root (issue #246).

        run.sh contained hardcoded /tmp/amplihack-workstreams/ws-NNN paths and
        AMPLIHACK_TREE_ID session tokens that constitute information disclosure.
        """
        assert not (REPO_ROOT / "run.sh").exists(), (
            "run.sh must not exist at the repo root. "
            "This file is an amplihack session runner with hardcoded absolute paths "
            "and session tokens that are not portable and disclose environment details."
        )

    def test_workstreams_json_absent(self):
        """workstreams.json must not exist at the repo root.

        workstreams.json is the amplihack task list for an orchestration session.
        It exposes internal workflow IDs and agent session metadata.
        """
        assert not (REPO_ROOT / "workstreams.json").exists(), (
            "workstreams.json must not exist at the repo root. "
            "This is an amplihack orchestration task list, not a wikigr artifact."
        )

    def test_no_workstreams_variant_json_at_root(self):
        """No workstreams*.json variants must exist at the repo root.

        Amplihack may generate timestamped variants like workstreams-2026-01-01.json.
        None of these belong in the repository.
        """
        stale_files = list(REPO_ROOT.glob("workstreams*.json"))
        assert stale_files == [], (
            f"Found workstreams*.json file(s) at repo root that must be removed: "
            f"{[str(f) for f in stale_files]}"
        )

    def test_no_round_workstreams_json(self):
        """No round*-workstreams.json files must exist at the repo root.

        These are round-trip orchestration tracking files from earlier amplihack sessions.
        """
        stale_files = list(
            itertools.chain(
                REPO_ROOT.glob("round*-workstreams.json"),
                REPO_ROOT.glob("round*.json"),
            )
        )
        assert stale_files == [], (
            f"Found round*-workstreams.json file(s) at repo root that must be removed: "
            f"{[str(f) for f in stale_files]}"
        )


# ---------------------------------------------------------------------------
# .gitignore guard patterns
# ---------------------------------------------------------------------------


class TestGitignoreGuards:
    """The three orchestration-artifact guard patterns must be in .gitignore."""

    def test_launcher_py_pattern_present(self, gitignore_lines: list[str]):
        """launcher.py must be listed as a gitignore pattern at the repo root.

        Without this guard, amplihack will recreate the file in future sessions and
        it can be accidentally staged again.
        """
        assert "launcher.py" in gitignore_lines, (
            ".gitignore must contain 'launcher.py' as an exact-match pattern "
            "(not inside a comment) to block future accidental commits."
        )

    def test_run_sh_pattern_present(self, gitignore_lines: list[str]):
        """run.sh must be listed as a gitignore pattern at the repo root."""
        assert "run.sh" in gitignore_lines, (
            ".gitignore must contain 'run.sh' as an exact-match pattern "
            "to block future accidental commits of amplihack session runners."
        )

    def test_workstreams_glob_pattern_present(self, gitignore_lines: list[str]):
        """workstreams*.json must be listed as a gitignore glob pattern."""
        assert "workstreams*.json" in gitignore_lines, (
            ".gitignore must contain 'workstreams*.json' as a glob pattern "
            "to block current and future timestamped variant files."
        )

    def test_amplihack_section_comment_present(self, gitignore_text: str):
        """A comment must label the amplihack orchestration section for clarity."""
        assert "Amplihack workstream orchestration files" in gitignore_text, (
            ".gitignore must contain an 'Amplihack workstream orchestration files' "
            "comment to document why these patterns exist."
        )

    def test_guard_patterns_are_contiguous(self, gitignore_lines: list[str]):
        """The three guard patterns should be grouped together under the comment."""
        try:
            comment_idx = next(
                i
                for i, line in enumerate(gitignore_lines)
                if "Amplihack workstream orchestration files" in line
            )
        except StopIteration:
            pytest.fail(
                "Could not find 'Amplihack workstream orchestration files' comment in .gitignore"
            )

        # The three patterns must appear within 5 lines of the comment
        guard_block = "\n".join(gitignore_lines[comment_idx : comment_idx + 6])
        assert (
            "launcher.py" in guard_block
        ), "launcher.py pattern must appear near the amplihack comment in .gitignore"
        assert (
            "run.sh" in guard_block
        ), "run.sh pattern must appear near the amplihack comment in .gitignore"
        assert (
            "workstreams*.json" in guard_block
        ), "workstreams*.json pattern must appear near the amplihack comment in .gitignore"


# ---------------------------------------------------------------------------
# git check-ignore verification (requires git)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestGitCheckIgnore:
    """Verify the patterns are active by asking git itself."""

    def _run_check_ignore(self, filename: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "check-ignore", "-v", filename],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

    def test_launcher_py_is_ignored(self):
        """git check-ignore must confirm launcher.py is ignored."""
        result = self._run_check_ignore("launcher.py")
        assert result.returncode == 0, (
            "git check-ignore returned non-zero for launcher.py — "
            "the pattern may be missing or inactive. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert (
            "launcher.py" in result.stdout
        ), f"Expected '.gitignore' and 'launcher.py' in git check-ignore output, got: {result.stdout!r}"

    def test_run_sh_is_ignored(self):
        """git check-ignore must confirm run.sh is ignored."""
        result = self._run_check_ignore("run.sh")
        assert result.returncode == 0, (
            "git check-ignore returned non-zero for run.sh — "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert (
            "run.sh" in result.stdout
        ), f"Expected 'run.sh' in git check-ignore output, got: {result.stdout!r}"

    def test_workstreams_json_is_ignored(self):
        """git check-ignore must confirm workstreams.json matches the glob."""
        result = self._run_check_ignore("workstreams.json")
        assert result.returncode == 0, (
            "git check-ignore returned non-zero for workstreams.json — "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert (
            "workstreams" in result.stdout
        ), f"Expected 'workstreams' in git check-ignore output, got: {result.stdout!r}"


# ---------------------------------------------------------------------------
# pyproject.toml — no amplihack dependencies
# ---------------------------------------------------------------------------


class TestPyprojectNoDeps:
    """pyproject.toml must not declare amplihack or amplihack.recipes as a dependency.

    Issue #247: launcher.py imported amplihack.recipes. The fix was to remove launcher.py,
    not to add amplihack.recipes to pyproject.toml. These tests guard against regression
    where someone tries to 'fix' the ModuleNotFoundError by adding amplihack as a dependency.
    """

    def test_amplihack_not_in_dependencies(self, pyproject_text: str):
        """amplihack must not appear in the [project.dependencies] section."""
        assert "amplihack" not in pyproject_text.lower() or _amplihack_only_in_comment(
            pyproject_text
        ), (
            "pyproject.toml must NOT list 'amplihack' as a dependency. "
            "amplihack is an orchestration tool, not a wikigr runtime dependency. "
            "Remove the orchestration artifact that imports it instead."
        )

    def test_amplihack_recipes_not_in_dependencies(self, pyproject_text: str):
        """amplihack.recipes must not appear anywhere in pyproject.toml."""
        assert "amplihack.recipes" not in pyproject_text, (
            "pyproject.toml must NOT reference 'amplihack.recipes'. "
            "This package is an amplihack internal, not a wikigr dependency. "
            "The file that imports it (launcher.py) should be removed, not added to deps."
        )

    def test_wikigr_in_project_name(self, pyproject_text: str):
        """pyproject.toml must still be the wikigr project definition (sanity check)."""
        assert 'name = "wikigr"' in pyproject_text, (
            "pyproject.toml must still declare name = 'wikigr'. "
            "This test guards against reading the wrong pyproject.toml."
        )

    def test_no_hardcoded_tmp_paths_in_pyproject(self, pyproject_text: str):
        """pyproject.toml must not contain hardcoded /tmp/ paths (issue #246-class check)."""
        assert "/tmp/" not in pyproject_text, (
            "pyproject.toml must not contain '/tmp/' paths. "
            "Absolute /tmp paths are developer-machine-specific and indicate "
            "an orchestration artifact was accidentally included."
        )

    def test_no_hardcoded_amplihack_workstreams_path(self, pyproject_text: str):
        """pyproject.toml must not contain amplihack-workstreams paths."""
        assert "amplihack-workstreams" not in pyproject_text, (
            "pyproject.toml must not contain 'amplihack-workstreams' path segments. "
            "These are orchestration session paths that belong in run.sh, not pyproject.toml."
        )
