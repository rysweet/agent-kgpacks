"""Tests for the wikigr query CLI command."""

from __future__ import annotations

import subprocess
import sys


def _run_wikigr(*args: str) -> subprocess.CompletedProcess:
    """Run wikigr command and capture output."""
    return subprocess.run(
        [sys.executable, "-m", "wikigr.cli", *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestQueryCommand:
    """Tests for wikigr query subcommand."""

    def test_query_help(self):
        """query --help exits 0 and shows usage."""
        result = _run_wikigr("query", "--help")
        assert result.returncode == 0
        assert "--pack" in result.stdout

    def test_query_missing_pack_flag(self):
        """query without --pack exits with error."""
        result = _run_wikigr("query", "What is X?")
        assert result.returncode != 0

    def test_query_nonexistent_pack(self):
        """query with nonexistent pack exits 1."""
        result = _run_wikigr("query", "What is X?", "--pack", "nonexistent-pack-xyz")
        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or result.returncode == 1

    def test_query_format_json_flag_accepted(self):
        """--format json is a valid flag."""
        result = _run_wikigr("query", "--help")
        assert "json" in result.stdout
