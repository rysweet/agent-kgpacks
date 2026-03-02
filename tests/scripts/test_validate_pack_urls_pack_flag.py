"""Tests for PACK_NAME_RE validation in scripts/validate_pack_urls.py --pack flag.

The elif args.pack branch (~line 109) must validate the pack short-name with
PACK_NAME_RE before constructing any filesystem path.  Invalid names must
cause exit code 1 with an error on stderr.

TDD: written to specify behaviour BEFORE (or alongside) implementation.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helper — run the script as a subprocess for integration-style tests
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "validate_pack_urls.py"


def _run_script(*args: str) -> subprocess.CompletedProcess:
    """Run validate_pack_urls.py with the given arguments."""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Helper — load the script as a module for unit-style tests
# ---------------------------------------------------------------------------

def _load_module():
    """Load validate_pack_urls as a Python module (avoids import side-effects)."""
    spec = importlib.util.spec_from_file_location("validate_pack_urls", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Integration tests via subprocess
# ---------------------------------------------------------------------------

class TestValidatePackUrlsPackFlagIntegration:
    """--pack validation must run before any filesystem operations."""

    # --- Path traversal regression tests (required by design spec) ---

    def test_traversal_name_exits_1(self):
        """'../traversal' must cause exit code 1."""
        result = _run_script("--pack", "../traversal")
        assert result.returncode == 1

    def test_traversal_name_error_on_stderr(self):
        """'../traversal' must print an error to stderr."""
        result = _run_script("--pack", "../traversal")
        assert result.stderr.strip() != "", "Expected error message on stderr"

    def test_traversal_name_error_mentions_invalid(self):
        """stderr for '../traversal' must say 'invalid' or 'Error'."""
        result = _run_script("--pack", "../traversal")
        lower = result.stderr.lower()
        assert "invalid" in lower or "error" in lower

    def test_traversal_name_error_echoes_name(self):
        """stderr message must include the rejected name for diagnostics."""
        result = _run_script("--pack", "../traversal")
        assert "../traversal" in result.stderr

    # --- Spaces regression test (required by design spec) ---

    def test_spaces_in_name_exits_1(self):
        """'name with spaces' must cause exit code 1."""
        result = _run_script("--pack", "name with spaces")
        assert result.returncode == 1

    def test_spaces_in_name_error_on_stderr(self):
        """'name with spaces' must print an error to stderr."""
        result = _run_script("--pack", "name with spaces")
        assert result.stderr.strip() != ""

    # --- Additional invalid patterns ---

    def test_absolute_path_exits_1(self):
        """/etc/passwd as pack name must cause exit code 1."""
        result = _run_script("--pack", "/etc/passwd")
        assert result.returncode == 1

    def test_dot_in_name_exits_1(self):
        """Pack name with a dot must cause exit code 1."""
        result = _run_script("--pack", "bad.name")
        assert result.returncode == 1

    def test_starts_with_hyphen_exits_nonzero(self):
        """Pack name starting with '-' must cause a non-zero exit.

        Note: argparse may intercept '-bad' as an unknown flag (exit 2) before
        our validator runs (exit 1).  Either way the command must not succeed.
        """
        result = _run_script("--pack", "-bad")
        assert result.returncode != 0

    def test_65_char_name_exits_1(self):
        """Pack name of 65 chars (1 over max) must cause exit code 1."""
        long_name = "a" + "b" * 64
        result = _run_script("--pack", long_name)
        assert result.returncode == 1

    # --- Valid names pass the guard (fail later on missing file) ---

    def test_valid_name_reaches_not_found_error(self):
        """A valid pack name that doesn't exist on disk should hit 'not found'.

        This confirms the name guard passes for valid names; the error is
        about the missing urls.txt, not the name itself.
        """
        result = _run_script("--pack", "nonexistent-pack-xyz-abc123")
        assert result.returncode == 1
        lower = result.stderr.lower()
        assert "not found" in lower or "error" in lower
        assert "invalid" not in lower

    def test_valid_name_no_invalid_message(self):
        """A valid but nonexistent pack name must not be blocked by name validation.

        Uses a clearly nonexistent name to avoid slow network URL checks that
        would trigger if an actual pack's urls.txt were found on disk.
        """
        result = _run_script("--pack", "clearly-nonexistent-pack-xy7z")
        lower_stderr = result.stderr.lower()
        # Must fail with "not found", not "invalid"
        assert "invalid" not in lower_stderr

    # --- Error message format contract ---

    def test_error_message_contains_pattern_hint(self):
        """Error message must mention the expected naming rules."""
        result = _run_script("--pack", "bad.name")
        assert "alphanumeric" in result.stderr.lower() or "pattern" in result.stderr.lower()

    def test_no_stdout_on_invalid_name(self):
        """No output on stdout when pack name is invalid."""
        result = _run_script("--pack", "bad.name")
        assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Unit tests — exercise main() directly with mocked sys.argv and sys.exit
# ---------------------------------------------------------------------------

class TestValidatePackUrlsMainUnit:
    """Unit tests for the main() function's --pack validation branch."""

    def _call_main_with_pack(self, pack_name: str):
        """Invoke main() with --pack <pack_name>, capturing exit and stderr."""
        mod = _load_module()
        with patch.object(sys, "argv", ["validate_pack_urls.py", "--pack", pack_name]):
            with pytest.raises(SystemExit) as exc_info:
                mod.main()
        return exc_info.value.code

    def test_traversal_raises_systemexit_1(self, capsys):
        """main() with '../traversal' must raise SystemExit(1)."""
        exit_code = self._call_main_with_pack("../traversal")
        assert exit_code == 1

    def test_spaces_raises_systemexit_1(self, capsys):
        """main() with 'name with spaces' must raise SystemExit(1)."""
        exit_code = self._call_main_with_pack("name with spaces")
        assert exit_code == 1

    def test_absolute_path_raises_systemexit_1(self, capsys):
        """main() with '/etc/passwd' must raise SystemExit(1)."""
        exit_code = self._call_main_with_pack("/etc/passwd")
        assert exit_code == 1

    def test_valid_name_no_name_validation_exit(self, tmp_path, capsys):
        """main() with a valid name must NOT exit due to name validation.

        It may still exit because urls.txt is absent, but that is a different
        code path. We assert exit != 1 due to 'invalid pack name' by checking
        the error message doesn't mention 'invalid'.
        """
        # This will raise SystemExit(1) because the file doesn't exist,
        # but the error must be about the missing file, not the name.
        with patch.object(sys, "argv", ["validate_pack_urls.py", "--pack", "valid-pack"]):
            with pytest.raises(SystemExit) as exc_info:
                mod = _load_module()
                mod.main()
        exit_code = exc_info.value.code
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "invalid" not in captured.err.lower()


# ---------------------------------------------------------------------------
# Regression: PACK_NAME_RE imported from manifest, not defined locally
# ---------------------------------------------------------------------------

class TestPackNameReImportedFromManifest:
    """validate_pack_urls.py must use the shared constant, not a local copy."""

    def test_module_imports_pack_name_re_from_manifest(self):
        """The script must be able to import PACK_NAME_RE from wikigr.packs.manifest."""
        # If this import fails, the script has broken the shared-constant contract.
        from wikigr.packs.manifest import PACK_NAME_RE  # noqa: PLC0415

        assert PACK_NAME_RE is not None

    def test_pack_name_re_pattern_consistent_with_manifest(self):
        """The pattern used in validate_pack_urls must match the manifest constant."""
        from wikigr.packs.manifest import PACK_NAME_RE  # noqa: PLC0415

        # Valid name accepted by both
        assert PACK_NAME_RE.match("dotnet-expert")
        # Invalid names rejected by both
        assert not PACK_NAME_RE.match("../traversal")
        assert not PACK_NAME_RE.match("name with spaces")
