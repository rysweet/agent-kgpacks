"""Contract tests for seed_researcher.py crawl exception narrowing (design/exception-handling.md §B1).

Written TDD-first: these tests specify the exception-handling contract for
_extract_by_crawl() in LLMSeedResearcher.

OLD behaviour (line ~607, before refactoring):
  except (requests.RequestException, Exception):
      continue

  This caught ALL exceptions inside the per-URL processing loop, including:
  - AttributeError from BeautifulSoup attribute access
  - TypeError from malformed responses
  - KeyError from unexpected data shapes
  All programming bugs were silently swallowed; bad URLs were just skipped
  instead of exposing the underlying defect.

NEW contract (design/exception-handling.md §B1):
  except requests.RequestException:
      continue

  - requests.RequestException (network errors) → caught, continue to next URL.
  - AttributeError / TypeError / KeyError (programming bugs) → propagate.

Each test would FAIL against the old code because the old handler caught
AttributeError/TypeError and silently continued.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from wikigr.packs.seed_researcher import DiscoveredSource, LLMSeedResearcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEED_RESEARCHER_PATH = (
    Path(__file__).parent.parent.parent / "wikigr" / "packs" / "seed_researcher.py"
)


def _make_researcher() -> LLMSeedResearcher:
    """Build LLMSeedResearcher bypassing __init__ to avoid Anthropic key requirement."""
    with patch("anthropic.Anthropic"):
        researcher = LLMSeedResearcher(api_key="test-key-x")
    researcher.timeout = 5.0
    researcher.user_agent = "test-bot/1.0"
    return researcher


def _make_source(base_url: str = "https://example.com") -> DiscoveredSource:
    return DiscoveredSource(
        domain="example.com",
        url=base_url,
        authority_score=0.9,
        rationale="test source",
        article_count=10,
        extraction_methods=["crawl"],
    )


def _make_200_html_response(html: str = "") -> MagicMock:
    """Return a mock requests.Response with status 200 and HTML content."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "text/html; charset=utf-8"}
    resp.text = html or "<html><body><a href='/article1'>Article 1</a></body></html>"
    return resp


# ===========================================================================
# B1 — Structural: verify except clause at source level
# ===========================================================================


class TestCrawlExceptClauseStructure:
    """AST-level check: _extract_by_crawl must not use bare Exception.

    These tests examine the source directly, so they would FAIL against the
    old code (which had 'except (requests.RequestException, Exception)') and
    PASS against the new code (which has 'except requests.RequestException').
    """

    def _get_extract_by_crawl_handlers(self) -> list[ast.ExceptHandler]:
        source = _SEED_RESEARCHER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_extract_by_crawl":
                return [child for child in ast.walk(node) if isinstance(child, ast.ExceptHandler)]
        return []

    def test_no_bare_exception_in_crawl_loop(self) -> None:
        """_extract_by_crawl must NOT catch bare Exception.

        OLD code: except (requests.RequestException, Exception): continue
        NEW code: except requests.RequestException: continue
        """
        handlers = self._get_extract_by_crawl_handlers()
        assert handlers, "_extract_by_crawl has no except handler"

        for handler in handlers:
            if handler.type is None:
                pytest.fail(
                    "_extract_by_crawl uses bare 'except' with no type — must use "
                    "'except requests.RequestException'"
                )
            if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                pytest.fail(
                    "_extract_by_crawl still uses 'except Exception'. "
                    "The contract requires 'except requests.RequestException' only."
                )
            if isinstance(handler.type, ast.Tuple):
                for elt in handler.type.elts:
                    if isinstance(elt, ast.Name) and elt.id == "Exception":
                        pytest.fail(
                            "_extract_by_crawl has 'Exception' in except tuple. "
                            "Remove it — only requests.RequestException should be caught."
                        )

    def test_crawl_catches_requests_exception(self) -> None:
        """_extract_by_crawl must catch requests.RequestException."""
        handlers = self._get_extract_by_crawl_handlers()
        found = False
        for handler in handlers:
            if handler.type is None:
                continue
            if (
                isinstance(handler.type, ast.Attribute)
                and handler.type.attr == "RequestException"
                or isinstance(handler.type, ast.Name)
                and handler.type.id == "RequestException"
            ):
                found = True
            elif isinstance(handler.type, ast.Tuple):
                for elt in handler.type.elts:
                    if (
                        isinstance(elt, ast.Attribute)
                        and elt.attr == "RequestException"
                        or isinstance(elt, ast.Name)
                        and elt.id == "RequestException"
                    ):
                        found = True
        assert found, "_extract_by_crawl must catch requests.RequestException for network failures."


# ===========================================================================
# B1 — Runtime: network errors are caught; programming bugs propagate
# ===========================================================================


class TestCrawlNetworkErrorHandling:
    """Network failures in _extract_by_crawl are caught and the URL is skipped.

    These tests verify the positive side of the contract: requests.RequestException
    is properly handled and does not abort the crawl.
    """

    def test_connection_error_skips_url_and_continues(self) -> None:
        """requests.ConnectionError is caught; remaining URLs are still processed."""
        researcher = _make_researcher()

        with (
            patch("requests.get", side_effect=requests.ConnectionError("refused")),
            patch.object(researcher, "_check_robots_txt", return_value=True),
        ):
            urls = researcher._extract_by_crawl("https://example.com", max_urls=5)

        # Should return empty (all requests failed) without raising
        assert isinstance(urls, list)
        assert urls == []

    def test_timeout_error_skips_url_and_continues(self) -> None:
        """requests.Timeout is caught; remaining URLs are still processed."""
        researcher = _make_researcher()

        with (
            patch("requests.get", side_effect=requests.Timeout("timed out")),
            patch.object(researcher, "_check_robots_txt", return_value=True),
        ):
            urls = researcher._extract_by_crawl("https://example.com", max_urls=5)

        assert isinstance(urls, list)
        assert urls == []

    def test_http_error_skips_url_and_continues(self) -> None:
        """requests.HTTPError is caught; remaining URLs are still processed."""
        researcher = _make_researcher()

        with (
            patch("requests.get", side_effect=requests.HTTPError("404")),
            patch.object(researcher, "_check_robots_txt", return_value=True),
        ):
            urls = researcher._extract_by_crawl("https://example.com", max_urls=5)

        assert isinstance(urls, list)
        assert urls == []

    def test_successful_crawl_returns_links(self) -> None:
        """When requests.get succeeds, links are extracted and returned."""
        researcher = _make_researcher()

        html = """<html><body>
            <a href="/article1">Article One</a>
            <a href="/article2">Article Two</a>
        </body></html>"""
        mock_resp = _make_200_html_response(html)
        # Subsequent requests for crawled links return 404 to stop recursion
        error_resp = MagicMock()
        error_resp.status_code = 404

        with (
            patch("requests.get", side_effect=[mock_resp, error_resp, error_resp]),
            patch.object(researcher, "_check_robots_txt", return_value=True),
        ):
            urls = researcher._extract_by_crawl("https://example.com", max_urls=10)

        assert len(urls) >= 1
        extracted = [u.url for u in urls]
        assert any("article" in u for u in extracted)


class TestCrawlProgrammingBugsPropagation:
    """Programming bugs in _extract_by_crawl propagate — they are NOT swallowed.

    OLD behaviour: except (requests.RequestException, Exception) caught
    AttributeError/TypeError, hiding real defects.

    NEW contract: only requests.RequestException is caught; other exceptions
    (which indicate bugs in code, not expected network failures) propagate.

    These tests would FAIL against the old code because the old handler
    swallowed AttributeError/TypeError inside the try block.
    """

    def test_attribute_error_in_beautifulsoup_propagates(self) -> None:
        """AttributeError from BeautifulSoup parsing propagates from _extract_by_crawl.

        OLD code: caught by 'except Exception' → URL silently skipped.
        NEW code: propagates → bug is visible.
        """
        researcher = _make_researcher()
        mock_resp = _make_200_html_response()

        with (
            patch("requests.get", return_value=mock_resp),
            patch.object(researcher, "_check_robots_txt", return_value=True),
            # Make BeautifulSoup.find_all raise AttributeError to simulate a code bug
            patch("wikigr.packs.seed_researcher.BeautifulSoup") as mock_bs_cls,
        ):
            mock_soup = MagicMock()
            mock_soup.find_all.side_effect = AttributeError(
                "'NoneType' object has no attribute 'find_all'"
            )
            mock_bs_cls.return_value = mock_soup

            with pytest.raises(AttributeError, match="has no attribute 'find_all'"):
                researcher._extract_by_crawl("https://example.com", max_urls=5)

    def test_type_error_in_url_parsing_propagates(self) -> None:
        """TypeError from URL processing propagates from _extract_by_crawl.

        OLD code: caught by 'except Exception' → silently ignored.
        NEW code: propagates → programming defect surfaces immediately.
        """
        researcher = _make_researcher()
        mock_resp = _make_200_html_response()

        with (
            patch("requests.get", return_value=mock_resp),
            patch.object(researcher, "_check_robots_txt", return_value=True),
            # Patch urljoin to raise TypeError — simulates a bug in URL construction
            patch("wikigr.packs.seed_researcher.urljoin", side_effect=TypeError("bad args")),
            pytest.raises(TypeError, match="bad args"),
        ):
            researcher._extract_by_crawl("https://example.com", max_urls=5)


# ===========================================================================
# B2 — Sitemap extraction: already specific (regression guard)
# ===========================================================================


class TestSitemapExceptClauseRegression:
    """Regression guard: _extract_from_sitemap already uses specific exception types.

    Design spec §B2: 'Lines 434, 461, 525 were already correctly specific —
    no change needed.'  These tests confirm the handlers remain specific.
    """

    def _get_sitemap_handlers(self) -> list[ast.ExceptHandler]:
        source = _SEED_RESEARCHER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_extract_from_sitemap":
                return [child for child in ast.walk(node) if isinstance(child, ast.ExceptHandler)]
        return []

    def _get_rss_handlers(self) -> list[ast.ExceptHandler]:
        source = _SEED_RESEARCHER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_extract_from_rss":
                return [child for child in ast.walk(node) if isinstance(child, ast.ExceptHandler)]
        return []

    def test_sitemap_no_bare_exception(self) -> None:
        """_extract_from_sitemap does not use bare except Exception."""
        handlers = self._get_sitemap_handlers()
        for handler in handlers:
            if handler.type is None:
                pytest.fail("_extract_from_sitemap uses bare except")
            if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                pytest.fail("_extract_from_sitemap still uses bare 'except Exception'")

    def test_rss_no_bare_exception(self) -> None:
        """_extract_from_rss does not use bare except Exception."""
        handlers = self._get_rss_handlers()
        for handler in handlers:
            if handler.type is None:
                pytest.fail("_extract_from_rss uses bare except")
            if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
                pytest.fail("_extract_from_rss still uses bare 'except Exception'")
