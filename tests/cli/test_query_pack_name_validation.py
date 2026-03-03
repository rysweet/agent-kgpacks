"""Tests for PACK_NAME_RE validation in wikigr query command (short-name branch).

The else-branch of cmd_query (cli.py ~line 679) must validate the pack
short-name with PACK_NAME_RE before constructing any filesystem path.
Invalid names must cause exit code 1 with an error on stderr.

TDD: written to specify behaviour BEFORE (or alongside) implementation.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run_query(*args: str) -> subprocess.CompletedProcess:
    """Run `python -m wikigr.cli query …` and capture output."""
    return subprocess.run(
        [sys.executable, "-m", "wikigr.cli", "query", *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.fixture(scope="class")
def result_traversal():
    """Subprocess result for '../traversal' — cached once per class."""
    return _run_query("What is X?", "--pack", "../traversal")


@pytest.fixture(scope="class")
def result_spaces():
    """Subprocess result for 'name with spaces' — cached once per class."""
    return _run_query("What is X?", "--pack", "name with spaces")


class TestQueryPackNameValidation:
    """cmd_query must reject invalid short-names before any filesystem access."""

    # --- Path traversal regression tests (required by design spec) ---

    def test_traversal_name_exits_1(self, result_traversal):
        """'../traversal' must cause exit code 1."""
        assert result_traversal.returncode == 1

    def test_traversal_name_error_on_stderr(self, result_traversal):
        """'../traversal' must print an error to stderr."""
        assert result_traversal.stderr.strip() != "", "Expected error message on stderr"

    def test_traversal_name_error_mentions_invalid(self, result_traversal):
        """stderr message for '../traversal' must say 'invalid' or 'Error'."""
        lower = result_traversal.stderr.lower()
        assert "invalid" in lower or "error" in lower

    def test_traversal_name_error_echoes_name(self, result_traversal):
        """stderr message must include the rejected name for diagnostics."""
        assert "../traversal" in result_traversal.stderr

    # --- Spaces regression test (required by design spec) ---

    def test_spaces_in_name_exits_1(self, result_spaces):
        """'name with spaces' must cause exit code 1."""
        # argparse may split on spaces; pass as a single positional string
        assert result_spaces.returncode == 1

    def test_spaces_in_name_error_on_stderr(self, result_spaces):
        """'name with spaces' must print an error to stderr."""
        assert result_spaces.stderr.strip() != ""

    # --- Additional invalid patterns ---

    def test_absolute_path_exits_1(self):
        """/etc/passwd as pack name must cause exit code 1 (absolute path)."""
        result = _run_query("What is X?", "--pack", "/etc/passwd")
        assert result.returncode == 1

    def test_dot_in_name_exits_1(self):
        """Pack name with a dot must cause exit code 1."""
        result = _run_query("What is X?", "--pack", "bad.name")
        assert result.returncode == 1

    def test_starts_with_hyphen_exits_nonzero(self):
        """Pack name starting with '-' must cause a non-zero exit.

        Note: argparse may intercept '-bad' as an unknown flag (exit 2) before
        our validator runs (exit 1).  Either way the command must not succeed.
        """
        result = _run_query("What is X?", "--pack", "-bad")
        assert result.returncode != 0

    def test_65_char_name_exits_1(self):
        """Pack name with 65 chars (1 over max) must cause exit code 1."""
        long_name = "a" + "b" * 64  # 65 chars total
        result = _run_query("What is X?", "--pack", long_name)
        assert result.returncode == 1

    # --- Valid names must NOT be rejected by the name validator ---

    def test_valid_name_reaches_db_not_found_error(self):
        """A valid pack name that doesn't exist on disk must reach 'not found' error.

        This confirms that valid names pass the PACK_NAME_RE guard and only
        fail when the DB file is absent — not due to name validation.
        """
        result = _run_query("What is X?", "--pack", "nonexistent-pack-xyz-abc123")
        # Must exit 1, but the error must be about the database, not the name
        assert result.returncode == 1
        lower = result.stderr.lower()
        assert "not found" in lower or "pack database" in lower

    def test_valid_hyphenated_name_not_blocked(self):
        """'nonexistent-pack-abc123' (valid name) must not be blocked by name validation."""
        result = _run_query("What is X?", "--pack", "nonexistent-pack-abc123")
        # Will fail with "not found" (no DB present) but NOT "invalid pack name"
        lower_stderr = result.stderr.lower()
        assert "invalid" not in lower_stderr

    def test_valid_name_with_digits_not_blocked(self):
        """'pack2024' (valid name) must not be blocked by name validation."""
        result = _run_query("What is X?", "--pack", "pack2024")
        lower_stderr = result.stderr.lower()
        assert "invalid" not in lower_stderr

    # --- Error message format contract ---

    def test_error_message_contains_pattern_hint(self, result_traversal):
        """Error message must mention the expected pattern for user guidance."""
        # The error should help the user understand valid naming rules
        assert (
            "alphanumeric" in result_traversal.stderr.lower()
            or "pattern" in result_traversal.stderr.lower()
        )

    def test_no_stdout_on_invalid_name(self, result_traversal):
        """No output on stdout when pack name is invalid (errors go to stderr only)."""
        assert result_traversal.stdout.strip() == ""
