"""TDD tests for wikigr/packs/utils.py — load_urls contract.

Written to specify expected behaviour.  All tests must pass once
wikigr/packs/utils.py contains the canonical load_urls implementation.

Contract summary
----------------
load_urls(urls_file, limit=None) -> list[str]

- Reads a text file line-by-line
- Strips leading/trailing whitespace from each line (walrus-operator style)
- Skips blank lines (empty after strip)
- Skips comment lines (stripped line starts with '#')
- Skips lines that do NOT start with 'https://' (case-sensitive, HTTPS-only per SEC-01)
  — accepts only 'https://'
  — rejects 'http://', 'ftp://', 'file://', plain text, etc.
- When limit is a positive int, truncates result to that many URLs
  and logs "Limited to N URLs for testing" at INFO
- limit=0 is falsy and treated as no limit (loads all URLs)
- limit=None (default) loads all URLs
- Always logs "Loaded N URLs from <path>" at INFO after any truncation
  (N reflects the truncated count)
- Propagates FileNotFoundError / OSError for missing or unreadable files
- Returns a plain list[str]; each element is a stripped URL string
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import under test
# ---------------------------------------------------------------------------
from wikigr.packs.utils import load_urls  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, content: str, name: str = "urls.txt") -> Path:
    """Write *content* to a temp file and return its Path."""
    p = tmp_path / name
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# 1. Basic URL loading
# ---------------------------------------------------------------------------


class TestBasicUrlLoading:
    """load_urls returns URLs from a well-formed file."""

    def test_returns_list(self, tmp_path):
        f = _write(tmp_path, "https://example.com\n")
        result = load_urls(f)
        assert isinstance(result, list)

    def test_single_https_url(self, tmp_path):
        f = _write(tmp_path, "https://example.com\n")
        assert load_urls(f) == ["https://example.com"]

    def test_single_http_url(self, tmp_path):
        """SEC-01: plain http:// URLs must be rejected (HTTPS-only)."""
        f = _write(tmp_path, "http://example.com\n")
        assert load_urls(f) == []

    def test_multiple_urls_preserves_order(self, tmp_path):
        content = "https://first.com\nhttps://second.com\nhttps://third.com\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://first.com", "https://second.com", "https://third.com"]

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = _write(tmp_path, "")
        assert load_urls(f) == []

    def test_returns_strings_not_bytes(self, tmp_path):
        f = _write(tmp_path, "https://example.com\n")
        result = load_urls(f)
        assert all(isinstance(u, str) for u in result)


# ---------------------------------------------------------------------------
# 2. Whitespace stripping
# ---------------------------------------------------------------------------


class TestWhitespaceStripping:
    """Lines are stripped before inclusion or filtering."""

    def test_leading_whitespace_stripped(self, tmp_path):
        f = _write(tmp_path, "  https://example.com\n")
        assert load_urls(f) == ["https://example.com"]

    def test_trailing_whitespace_stripped(self, tmp_path):
        f = _write(tmp_path, "https://example.com   \n")
        assert load_urls(f) == ["https://example.com"]

    def test_both_sides_stripped(self, tmp_path):
        f = _write(tmp_path, "   https://example.com   \n")
        assert load_urls(f) == ["https://example.com"]

    def test_url_with_embedded_spaces_not_split(self, tmp_path):
        """A URL containing no leading/trailing spaces should come through whole."""
        f = _write(tmp_path, "https://example.com/path?q=hello+world\n")
        assert load_urls(f) == ["https://example.com/path?q=hello+world"]

    def test_file_without_trailing_newline(self, tmp_path):
        """File not ending in newline should still return the last URL."""
        f = _write(tmp_path, "https://example.com")
        assert load_urls(f) == ["https://example.com"]


# ---------------------------------------------------------------------------
# 3. Blank line filtering
# ---------------------------------------------------------------------------


class TestBlankLineFiltering:
    """Blank lines (including whitespace-only) are skipped."""

    def test_blank_line_skipped(self, tmp_path):
        content = "https://first.com\n\nhttps://second.com\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://first.com", "https://second.com"]

    def test_whitespace_only_line_skipped(self, tmp_path):
        content = "https://first.com\n   \nhttps://second.com\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://first.com", "https://second.com"]

    def test_tab_only_line_skipped(self, tmp_path):
        content = "https://first.com\n\t\nhttps://second.com\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://first.com", "https://second.com"]

    def test_multiple_consecutive_blanks_skipped(self, tmp_path):
        content = "\n\n\nhttps://example.com\n\n\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://example.com"]

    def test_all_blank_lines_returns_empty(self, tmp_path):
        f = _write(tmp_path, "\n\n   \n\t\n")
        assert load_urls(f) == []


# ---------------------------------------------------------------------------
# 4. Comment line filtering
# ---------------------------------------------------------------------------


class TestCommentLineFiltering:
    """Lines starting with '#' (after strip) are treated as comments and skipped."""

    def test_hash_line_skipped(self, tmp_path):
        content = "# This is a comment\nhttps://example.com\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://example.com"]

    def test_indented_hash_line_skipped(self, tmp_path):
        content = "  # Indented comment\nhttps://example.com\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://example.com"]

    def test_hash_at_start_only_skips(self, tmp_path):
        """A URL with '#' in fragment is NOT a comment line."""
        content = "https://example.com/page#section\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://example.com/page#section"]

    def test_all_comment_lines_returns_empty(self, tmp_path):
        content = "# comment 1\n# comment 2\n# comment 3\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == []

    def test_comment_before_url_block(self, tmp_path):
        content = "# Section header\nhttps://a.com\nhttps://b.com\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://a.com", "https://b.com"]

    def test_inline_comment_not_stripped(self, tmp_path):
        """A URL with a trailing inline comment is NOT supported.

        The entire stripped line must start with 'https://' — if a URL has
        trailing text after a space it will fail the startswith('https://') check
        only if the stripped line does NOT start with https:// (it does here).
        This test confirms the URL-with-trailing-text still begins 'https://' so
        it is included as-is (no inline comment stripping).
        """
        url = "https://example.com/page  # inline comment"
        f = _write(tmp_path, url + "\n")
        # Stripped line is 'https://example.com/page  # inline comment'
        # Still starts with 'https://' → included verbatim
        assert load_urls(f) == [url.strip()]


# ---------------------------------------------------------------------------
# 5. Protocol filtering — only 'https://' prefix passes
# ---------------------------------------------------------------------------


class TestProtocolFiltering:
    """Only lines whose stripped form starts with 'https://' are included (SEC-01)."""

    def test_https_included(self, tmp_path):
        f = _write(tmp_path, "https://example.com\n")
        assert load_urls(f) == ["https://example.com"]

    def test_http_excluded(self, tmp_path):
        """SEC-01: plain http:// URLs must be rejected (HTTPS-only)."""
        f = _write(tmp_path, "http://example.com\n")
        assert load_urls(f) == []

    def test_ftp_excluded(self, tmp_path):
        f = _write(tmp_path, "ftp://example.com\n")
        assert load_urls(f) == []

    def test_file_protocol_excluded(self, tmp_path):
        f = _write(tmp_path, "file:///etc/passwd\n")
        assert load_urls(f) == []

    def test_plain_text_excluded(self, tmp_path):
        f = _write(tmp_path, "just some plain text\n")
        assert load_urls(f) == []

    def test_relative_path_excluded(self, tmp_path):
        f = _write(tmp_path, "/relative/path\n")
        assert load_urls(f) == []

    def test_mixed_protocols_only_https_returned(self, tmp_path):
        """SEC-01: only https:// URLs are accepted; http:// is also rejected."""
        content = (
            "https://good.com\n"
            "ftp://bad.com\n"
            "http://also-good.com\n"
            "file:///etc/shadow\n"
            "# comment\n"
            "\n"
        )
        f = _write(tmp_path, content)
        assert load_urls(f) == ["https://good.com"]

    def test_http_prefix_case_sensitive(self, tmp_path):
        """Filter is case-sensitive: 'HTTP://' (uppercase) does not match."""
        f = _write(tmp_path, "HTTP://EXAMPLE.COM\n")
        assert load_urls(f) == []

    def test_partial_http_prefix_excluded(self, tmp_path):
        """SEC-01: 'httpx://' does not start with 'https://' and must be rejected."""
        f = _write(tmp_path, "httpx://custom.com\n")
        # does not start with 'https://' → excluded
        assert load_urls(f) == []


# ---------------------------------------------------------------------------
# 6. limit parameter
# ---------------------------------------------------------------------------


class TestLimitParameter:
    """limit truncates the returned list to N items."""

    def _five_url_file(self, tmp_path: Path) -> Path:
        content = "\n".join(f"https://example.com/{i}" for i in range(1, 6)) + "\n"
        return _write(tmp_path, content)

    def test_limit_1_returns_first_url(self, tmp_path):
        f = self._five_url_file(tmp_path)
        assert load_urls(f, limit=1) == ["https://example.com/1"]

    def test_limit_3_returns_first_three(self, tmp_path):
        f = self._five_url_file(tmp_path)
        assert load_urls(f, limit=3) == [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]

    def test_limit_equal_to_total_returns_all(self, tmp_path):
        f = self._five_url_file(tmp_path)
        assert len(load_urls(f, limit=5)) == 5

    def test_limit_greater_than_total_returns_all(self, tmp_path):
        f = self._five_url_file(tmp_path)
        assert len(load_urls(f, limit=100)) == 5

    def test_limit_none_returns_all(self, tmp_path):
        f = self._five_url_file(tmp_path)
        assert len(load_urls(f, limit=None)) == 5

    def test_limit_zero_treated_as_no_limit(self, tmp_path):
        """limit=0 is falsy; must return all URLs, not an empty list."""
        f = self._five_url_file(tmp_path)
        assert len(load_urls(f, limit=0)) == 5

    def test_limit_default_is_no_limit(self, tmp_path):
        f = self._five_url_file(tmp_path)
        assert len(load_urls(f)) == 5


# ---------------------------------------------------------------------------
# 7. Logging behaviour
# ---------------------------------------------------------------------------


class TestLoggingBehaviour:
    """load_urls emits INFO log records at the expected points."""

    def test_loaded_message_always_emitted(self, tmp_path, caplog):
        f = _write(tmp_path, "https://example.com\n")
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f)
        messages = [r.message for r in caplog.records]
        assert any("Loaded" in m for m in messages)

    def test_loaded_message_contains_count(self, tmp_path, caplog):
        content = "https://a.com\nhttps://b.com\n"
        f = _write(tmp_path, content)
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f)
        messages = " ".join(r.message for r in caplog.records)
        assert "2" in messages

    def test_loaded_message_contains_path(self, tmp_path, caplog):
        f = _write(tmp_path, "https://example.com\n")
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f)
        messages = " ".join(r.message for r in caplog.records)
        assert str(f) in messages or f.name in messages

    def test_limit_message_emitted_when_limit_set(self, tmp_path, caplog):
        content = "\n".join(f"https://example.com/{i}" for i in range(10)) + "\n"
        f = _write(tmp_path, content)
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f, limit=3)
        messages = [r.message for r in caplog.records]
        assert any("Limited" in m for m in messages)

    def test_limit_message_contains_limit_value(self, tmp_path, caplog):
        content = "\n".join(f"https://example.com/{i}" for i in range(10)) + "\n"
        f = _write(tmp_path, content)
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f, limit=3)
        messages = " ".join(r.message for r in caplog.records)
        assert "3" in messages

    def test_no_limit_message_when_limit_is_none(self, tmp_path, caplog):
        f = _write(tmp_path, "https://example.com\n")
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f, limit=None)
        messages = [r.message for r in caplog.records]
        assert not any("Limited" in m for m in messages)

    def test_no_limit_message_when_limit_is_zero(self, tmp_path, caplog):
        """limit=0 is falsy; must NOT emit the 'Limited' message."""
        f = _write(tmp_path, "https://example.com\n")
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f, limit=0)
        messages = [r.message for r in caplog.records]
        assert not any("Limited" in m for m in messages)

    def test_loaded_count_reflects_truncated_count(self, tmp_path, caplog):
        """When limit is set, 'Loaded N' must report the truncated count (N),
        not the original line count.
        """
        content = "\n".join(f"https://example.com/{i}" for i in range(10)) + "\n"
        f = _write(tmp_path, content)
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f, limit=2)
        loaded_msgs = [r.message for r in caplog.records if "Loaded" in r.message]
        assert loaded_msgs, "Expected at least one 'Loaded' log message"
        # The count in the message must be '2', not '10'
        assert "2" in loaded_msgs[0]
        assert "10" not in loaded_msgs[0]

    def test_limit_log_emitted_before_loaded_log(self, tmp_path, caplog):
        """'Limited to N' must appear before 'Loaded N' in the log stream."""
        content = "\n".join(f"https://example.com/{i}" for i in range(5)) + "\n"
        f = _write(tmp_path, content)
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f, limit=2)
        messages = [r.message for r in caplog.records]
        limited_idx = next(i for i, m in enumerate(messages) if "Limited" in m)
        loaded_idx = next(i for i, m in enumerate(messages) if "Loaded" in m)
        assert limited_idx < loaded_idx

    def test_logger_name_is_module_path(self, tmp_path, caplog):
        """Logger must be named 'wikigr.packs.utils' (getLogger(__name__))."""
        f = _write(tmp_path, "https://example.com\n")
        with caplog.at_level(logging.INFO, logger="wikigr.packs.utils"):
            load_urls(f)
        assert any(r.name == "wikigr.packs.utils" for r in caplog.records)


# ---------------------------------------------------------------------------
# 8. Error handling — missing / unreadable file
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """load_urls propagates filesystem errors; it does NOT swallow them."""

    def test_missing_file_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "nonexistent.txt"
        with pytest.raises(FileNotFoundError):
            load_urls(missing)

    def test_directory_as_path_raises_os_error(self, tmp_path):
        """Passing a directory instead of a file must raise an OSError."""
        with pytest.raises((IsADirectoryError, OSError)):
            load_urls(tmp_path)

    def test_no_silent_empty_list_on_missing_file(self, tmp_path):
        """load_urls must NOT return [] for a missing file."""
        missing = tmp_path / "missing_urls.txt"
        with pytest.raises((FileNotFoundError, OSError)):
            load_urls(missing)


# ---------------------------------------------------------------------------
# 9. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases around file content and parameter values."""

    def test_only_comments_and_blanks_returns_empty(self, tmp_path):
        content = "# comment\n\n   \n# another comment\n"
        f = _write(tmp_path, content)
        assert load_urls(f) == []

    def test_very_long_url(self, tmp_path):
        long_url = "https://example.com/" + "a" * 2000
        f = _write(tmp_path, long_url + "\n")
        assert load_urls(f) == [long_url]

    def test_unicode_in_url(self, tmp_path):
        url = "https://example.com/path/\u00e9l\u00e8ve"
        f = _write(tmp_path, url + "\n")
        assert load_urls(f) == [url]

    def test_url_with_query_string(self, tmp_path):
        url = "https://example.com/search?q=foo&bar=baz"
        f = _write(tmp_path, url + "\n")
        assert load_urls(f) == [url]

    def test_url_with_fragment(self, tmp_path):
        url = "https://example.com/docs#section-1"
        f = _write(tmp_path, url + "\n")
        assert load_urls(f) == [url]

    def test_windows_line_endings(self, tmp_path):
        """CRLF line endings must be handled correctly after stripping."""
        f = _write(tmp_path, "https://a.com\r\nhttps://b.com\r\n")
        result = load_urls(f)
        assert result == ["https://a.com", "https://b.com"]

    def test_limit_1_on_empty_file_returns_empty(self, tmp_path):
        f = _write(tmp_path, "")
        assert load_urls(f, limit=1) == []

    def test_path_as_string_not_accepted_type_hint(self, tmp_path):
        """The function signature accepts Path; a str path also works
        because open() accepts str too — document the actual behaviour.
        """
        p = _write(tmp_path, "https://example.com\n")
        # Passing as str should work since open() accepts both
        result = load_urls(str(p))  # type: ignore[arg-type]
        assert result == ["https://example.com"]


# ---------------------------------------------------------------------------
# 10. Integration: no local def load_urls in any build script
# ---------------------------------------------------------------------------


class TestNoLocalDefLoadUrlsInScripts:
    """Regression guard: every build_*_pack.py must use the shared import.

    This is an AST-based structural test — it does NOT import the scripts
    (which require heavy dependencies like kuzu and sentence_transformers).
    """

    SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"

    def _collect_build_scripts(self) -> list[Path]:
        return sorted(self.SCRIPTS_DIR.glob("build_*_pack.py"))

    def _has_local_load_urls_def(self, path: Path) -> bool:
        import ast

        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "load_urls":
                return True
        return False

    def _has_shared_import(self, path: Path) -> bool:
        src = path.read_text()
        return "from wikigr.packs.utils import load_urls" in src

    def test_build_scripts_found(self):
        """Sanity: at least 40 build scripts must exist."""
        scripts = self._collect_build_scripts()
        assert len(scripts) >= 40, f"Expected >= 40 build scripts, found {len(scripts)}"

    def test_no_local_def_load_urls_in_any_build_script(self):
        """No build_*_pack.py may define its own load_urls function."""
        offenders = [
            p.name for p in self._collect_build_scripts() if self._has_local_load_urls_def(p)
        ]
        assert offenders == [], f"These scripts still have a local def load_urls: {offenders}"

    def _calls_load_urls(self, path: Path) -> bool:
        """Return True if the script body calls load_urls (excluding the def line)."""
        src = path.read_text()
        # Match any call to load_urls( that isn't inside a def statement
        import re

        # A call looks like 'load_urls(' anywhere in the source
        return bool(re.search(r"\bload_urls\s*\(", src))

    def test_all_build_scripts_that_call_load_urls_use_shared_import(self):
        """Every build_*_pack.py that calls load_urls() must import it from
        wikigr.packs.utils (not define it locally).
        """
        missing = [
            p.name
            for p in self._collect_build_scripts()
            if self._calls_load_urls(p) and not self._has_shared_import(p)
        ]
        assert missing == [], (
            f"These scripts call load_urls but don't import from wikigr.packs.utils: {missing}"
        )

    def test_check_pack_freshness_imports_from_shared_utils(self):
        """check_pack_freshness.py must use the shared import."""
        p = self.SCRIPTS_DIR / "check_pack_freshness.py"
        assert self._has_shared_import(p), (
            "check_pack_freshness.py is missing 'from wikigr.packs.utils import load_urls'"
        )

    def test_validate_pack_urls_imports_from_shared_utils(self):
        """validate_pack_urls.py must use the shared import."""
        p = self.SCRIPTS_DIR / "validate_pack_urls.py"
        assert self._has_shared_import(p), (
            "validate_pack_urls.py is missing 'from wikigr.packs.utils import load_urls'"
        )

    def test_no_local_def_in_check_pack_freshness(self):
        p = self.SCRIPTS_DIR / "check_pack_freshness.py"
        assert not self._has_local_load_urls_def(p), (
            "check_pack_freshness.py must not define its own load_urls"
        )

    def test_no_local_def_in_validate_pack_urls(self):
        p = self.SCRIPTS_DIR / "validate_pack_urls.py"
        assert not self._has_local_load_urls_def(p), (
            "validate_pack_urls.py must not define its own load_urls"
        )


# ---------------------------------------------------------------------------
# 11. Module-level logger name
# ---------------------------------------------------------------------------


class TestModuleLevelLogger:
    """load_urls must use a module-level logger, not a local one."""

    def test_utils_module_has_logger_attribute(self):
        """wikigr.packs.utils must expose a 'logger' at module level."""
        import wikigr.packs.utils as utils_mod

        assert hasattr(utils_mod, "logger")
        assert isinstance(utils_mod.logger, logging.Logger)

    def test_logger_name_matches_module(self):
        import wikigr.packs.utils as utils_mod

        assert utils_mod.logger.name == "wikigr.packs.utils"
