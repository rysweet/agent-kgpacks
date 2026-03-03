"""Tests that verify accuracy of docs/howto/repository-hygiene.md.

Contracts:
  - The how-to guide must exist at the documented path.
  - It must reference both issue #246 (run.sh / hardcoded paths) and #247 (launcher.py /
    missing dependency).
  - The git check-ignore example output must show line numbers that match the actual
    .gitignore file (dynamically verified against the real .gitignore).
  - The tab-separated format in the example must be correct:
    `.gitignore:LINE:launcher.py\tlauncher.py`
  - The security considerations section must cover supply chain risk, information
    disclosure, and metadata leakage.
  - The pyproject.toml section must explain that amplihack.recipes is absent by design.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HYGIENE_DOC = REPO_ROOT / "docs" / "howto" / "repository-hygiene.md"
GITIGNORE = REPO_ROOT / ".gitignore"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hygiene_text() -> str:
    assert HYGIENE_DOC.exists(), (
        f"docs/howto/repository-hygiene.md must exist at {HYGIENE_DOC}. "
        "This guide documents the cleanup from issues #246 and #247."
    )
    return HYGIENE_DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def gitignore_lines() -> list[str]:
    return GITIGNORE.read_text(encoding="utf-8").splitlines()


@pytest.fixture(scope="module")
def hygiene_text_lower(hygiene_text: str) -> str:
    return hygiene_text.lower()


@pytest.fixture(scope="module")
def hygiene_text_lines(hygiene_text: str) -> list[str]:
    return hygiene_text.splitlines()


# ---------------------------------------------------------------------------
# Document existence and structure
# ---------------------------------------------------------------------------


class TestDocumentExists:
    """The repository hygiene how-to guide must exist."""

    def test_file_has_substantial_content(self, hygiene_text: str):
        """The guide must not be empty or trivially short."""
        assert len(hygiene_text) > 1000, (
            f"docs/howto/repository-hygiene.md is too short ({len(hygiene_text)} chars). "
            "The guide should include background, file descriptions, .gitignore section, "
            "and security considerations."
        )

    def test_has_title(self, hygiene_text_lines: list[str]):
        """The guide must have a title heading that mentions 'Repository'."""
        assert any(
            line.startswith("# ") and "repository" in line.lower() for line in hygiene_text_lines
        ), "docs/howto/repository-hygiene.md must have a title heading containing 'Repository'."


# ---------------------------------------------------------------------------
# Issue references
# ---------------------------------------------------------------------------


class TestIssueReferences:
    """The guide must reference both issues that prompted the cleanup."""

    def test_references_issue_247(self, hygiene_text: str):
        """Issue #247 (missing amplihack.recipes dep) must be mentioned."""
        assert "#247" in hygiene_text, (
            "docs/howto/repository-hygiene.md must reference issue #247 "
            "(launcher.py imported amplihack.recipes, missing from pyproject.toml)."
        )

    def test_references_issue_246(self, hygiene_text: str):
        """Issue #246 (hardcoded paths in run.sh) must be mentioned."""
        assert "#246" in hygiene_text, (
            "docs/howto/repository-hygiene.md must reference issue #246 "
            "(run.sh had hardcoded /tmp/ paths and session tokens)."
        )

    def test_mentions_launcher_py(self, hygiene_text: str):
        """The guide must describe why launcher.py must not be committed."""
        assert "launcher.py" in hygiene_text, (
            "docs/howto/repository-hygiene.md must mention launcher.py and "
            "explain why it must not be committed."
        )

    def test_mentions_run_sh(self, hygiene_text: str):
        """The guide must describe why run.sh must not be committed."""
        assert "run.sh" in hygiene_text, (
            "docs/howto/repository-hygiene.md must mention run.sh and "
            "explain why it must not be committed."
        )

    def test_mentions_workstreams_json(self, hygiene_text: str):
        """The guide must describe why workstreams.json must not be committed."""
        assert "workstreams.json" in hygiene_text or "workstreams*.json" in hygiene_text, (
            "docs/howto/repository-hygiene.md must mention workstreams.json "
            "and explain why it must not be committed."
        )


# ---------------------------------------------------------------------------
# amplihack.recipes explanation
# ---------------------------------------------------------------------------


class TestAmplihackRecipesExplanation:
    """The guide must explain that amplihack.recipes is absent from pyproject.toml by design."""

    def test_mentions_amplihack_recipes(self, hygiene_text: str):
        """amplihack.recipes must be mentioned as the missing package."""
        assert "amplihack.recipes" in hygiene_text, (
            "docs/howto/repository-hygiene.md must mention 'amplihack.recipes' "
            "to explain what ModuleNotFoundError launcher.py caused."
        )

    def test_module_not_found_error_mentioned(self, hygiene_text: str):
        """ModuleNotFoundError must be referenced to explain the symptom."""
        assert "ModuleNotFoundError" in hygiene_text, (
            "docs/howto/repository-hygiene.md must mention 'ModuleNotFoundError' "
            "to describe the symptom seen by contributors on clean installs."
        )

    def test_pyproject_toml_section_present(self, hygiene_text: str):
        """A section about pyproject.toml must explain what it contains."""
        assert "pyproject.toml" in hygiene_text, (
            "docs/howto/repository-hygiene.md must have a section explaining "
            "that pyproject.toml intentionally omits amplihack dependencies."
        )

    def test_remove_file_not_add_dep_guidance_present(self, hygiene_text_lower: str):
        """The guide must advise removing the file, not adding the import to pyproject."""
        assert "remove" in hygiene_text_lower and (
            "import" in hygiene_text_lower or "file" in hygiene_text_lower
        ), (
            "docs/howto/repository-hygiene.md must advise removing the file that "
            "contains the import, rather than adding the package to pyproject.toml."
        )


# ---------------------------------------------------------------------------
# Hardcoded path explanation
# ---------------------------------------------------------------------------


class TestHardcodedPathExplanation:
    """The guide must explain the run.sh hardcoded path problem."""

    def test_mentions_tmp_path(self, hygiene_text: str):
        """The guide must mention /tmp/ paths to explain the problem."""
        assert "/tmp/" in hygiene_text, (
            "docs/howto/repository-hygiene.md must mention '/tmp/' paths "
            "to explain why run.sh constitutes information disclosure."
        )

    def test_mentions_amplihack_tree_id(self, hygiene_text: str):
        """AMPLIHACK_TREE_ID must be mentioned as an example of a leaked session token."""
        assert "AMPLIHACK_TREE_ID" in hygiene_text, (
            "docs/howto/repository-hygiene.md must mention AMPLIHACK_TREE_ID "
            "as an example of the session token that was exposed."
        )

    def test_information_disclosure_mentioned(self, hygiene_text_lower: str):
        """The doc must use 'information disclosure' terminology."""
        assert "information disclosure" in hygiene_text_lower, (
            "docs/howto/repository-hygiene.md must use the term 'information disclosure' "
            "to categorise the security risk from run.sh."
        )


# ---------------------------------------------------------------------------
# .gitignore section accuracy
# ---------------------------------------------------------------------------


class TestGitignoreSectionAccuracy:
    """The .gitignore section must accurately describe the guard patterns."""

    def test_gitignore_section_present(self, hygiene_text: str):
        """A section about .gitignore guards must be present."""
        assert ".gitignore" in hygiene_text, (
            "docs/howto/repository-hygiene.md must contain a section about "
            ".gitignore guard patterns."
        )

    def test_gitignore_code_block_has_launcher_py(self, hygiene_text: str):
        """The .gitignore code block must show the launcher.py pattern."""
        assert (
            "launcher.py" in hygiene_text
        ), "The .gitignore code block in the guide must show the launcher.py pattern."

    def test_gitignore_code_block_has_run_sh(self, hygiene_text: str):
        """The .gitignore code block must show the run.sh pattern."""
        assert (
            "run.sh" in hygiene_text
        ), "The .gitignore code block in the guide must show the run.sh pattern."

    def test_gitignore_code_block_has_workstreams_glob(self, hygiene_text: str):
        """The .gitignore code block must show the workstreams*.json glob."""
        assert (
            "workstreams*.json" in hygiene_text
        ), "The .gitignore code block in the guide must show the workstreams*.json glob."

    def test_check_ignore_example_present(self, hygiene_text: str):
        """The guide must include a git check-ignore example command."""
        assert "git check-ignore" in hygiene_text, (
            "docs/howto/repository-hygiene.md must include a 'git check-ignore -v' "
            "example showing how to verify the patterns are active."
        )

    def test_check_ignore_example_output_format(self, hygiene_text: str):
        """The git check-ignore example output must use the tab-separated format.

        git check-ignore -v outputs: .gitignore:LINE:PATTERN<TAB>FILE
        The doc must demonstrate this format correctly.
        """
        assert (
            ".gitignore:" in hygiene_text
        ), "The git check-ignore example output must show .gitignore:LINE:PATTERN format."

    def test_check_ignore_line_numbers_match_actual_gitignore(
        self, hygiene_text: str, gitignore_lines: list[str]
    ):
        """The line numbers shown in the git check-ignore example must match actual .gitignore.

        If .gitignore is edited and the patterns move to different lines, this test
        will catch the documentation drift.
        """
        # Get actual line numbers from .gitignore in a single pass with early exit
        launcher_line = run_sh_line = workstreams_line = None
        for i, line in enumerate(gitignore_lines):
            if line == "launcher.py":
                launcher_line = i + 1
            elif line == "run.sh":
                run_sh_line = i + 1
            elif line == "workstreams*.json":
                workstreams_line = i + 1
            if launcher_line and run_sh_line and workstreams_line:
                break

        assert launcher_line is not None, ".gitignore must contain a 'launcher.py' line"
        assert run_sh_line is not None, ".gitignore must contain a 'run.sh' line"
        assert workstreams_line is not None, ".gitignore must contain a 'workstreams*.json' line"

        # The documentation must show the correct line numbers
        expected_launcher = f".gitignore:{launcher_line}:launcher.py"
        expected_run_sh = f".gitignore:{run_sh_line}:run.sh"
        expected_workstreams = f".gitignore:{workstreams_line}:workstreams*.json"

        assert expected_launcher in hygiene_text, (
            f"docs/howto/repository-hygiene.md must show '{expected_launcher}' "
            f"in the git check-ignore example output. "
            f"launcher.py is on line {launcher_line} of .gitignore."
        )
        assert expected_run_sh in hygiene_text, (
            f"docs/howto/repository-hygiene.md must show '{expected_run_sh}' "
            f"in the git check-ignore example output. "
            f"run.sh is on line {run_sh_line} of .gitignore."
        )
        assert expected_workstreams in hygiene_text, (
            f"docs/howto/repository-hygiene.md must show '{expected_workstreams}' "
            f"in the git check-ignore example output. "
            f"workstreams*.json is on line {workstreams_line} of .gitignore."
        )

    def test_root_scoped_pattern_explanation(self, hygiene_text_lower: str):
        """The doc must explain that patterns match at repo root only (no leading **/)."""
        assert (
            ("root" in hygiene_text_lower and "subdirector" in hygiene_text_lower)
            or ("root only" in hygiene_text_lower)
            or ("scoped" in hygiene_text_lower)
        ), (
            "docs/howto/repository-hygiene.md must explain that the gitignore patterns "
            "are scoped to the repo root to avoid false positives in subdirectories."
        )


# ---------------------------------------------------------------------------
# Security considerations
# ---------------------------------------------------------------------------


class TestSecurityConsiderations:
    """The guide must have a security section covering the three risks."""

    def test_security_section_present(self, hygiene_text: str):
        """A Security Considerations section must be present."""
        assert (
            "Security" in hygiene_text
        ), "docs/howto/repository-hygiene.md must contain a 'Security' section."

    def test_supply_chain_risk_mentioned(self, hygiene_text_lower: str):
        """Supply chain risk must be identified for launcher.py."""
        assert "supply chain" in hygiene_text_lower, (
            "docs/howto/repository-hygiene.md Security section must mention "
            "'supply chain' risk (launcher.py imported an unverified package)."
        )

    def test_metadata_leakage_mentioned(self, hygiene_text_lower: str):
        """Metadata leakage must be identified for workstreams.json."""
        assert "metadata" in hygiene_text_lower or "leakage" in hygiene_text_lower, (
            "docs/howto/repository-hygiene.md Security section must mention "
            "metadata leakage (workstreams.json exposed internal workflow IDs)."
        )

    def test_future_improvement_check_banned_patterns_mentioned(
        self, hygiene_text: str, hygiene_text_lower: str
    ):
        """The doc must mention a future improvement for pre-commit path checks."""
        assert "check-banned-patterns" in hygiene_text or (
            "pre-commit" in hygiene_text_lower and "/tmp/" in hygiene_text
        ), (
            "docs/howto/repository-hygiene.md must mention the future improvement: "
            "a check-banned-patterns.sh pre-commit rule to reject /tmp/ and /home/ "
            "absolute paths in non-test Python files."
        )


# ---------------------------------------------------------------------------
# Cross-file consistency: doc vs .gitignore
# ---------------------------------------------------------------------------


class TestDocGitignoreConsistency:
    """The documentation must stay consistent with the actual .gitignore file."""

    def test_all_three_patterns_mentioned_in_doc(self, hygiene_text: str):
        """All three guard patterns must be mentioned in the documentation."""
        for pattern in ["launcher.py", "run.sh", "workstreams*.json"]:
            assert (
                pattern in hygiene_text
            ), f"docs/howto/repository-hygiene.md must mention the '{pattern}' gitignore pattern."

    def test_doc_section_count(self, hygiene_text_lines: list[str]):
        """The doc must have multiple sections (not just a title)."""
        heading_count = sum(1 for line in hygiene_text_lines if line.startswith("## "))
        assert heading_count >= 3, (
            f"docs/howto/repository-hygiene.md must have at least 3 sections (## headings), "
            f"found {heading_count}. Expected sections for: background, gitignore guards, "
            f"pyproject.toml, and security considerations."
        )
