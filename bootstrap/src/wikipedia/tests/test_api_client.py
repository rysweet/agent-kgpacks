"""Tests for WikipediaAPIClient — retry logic, rate limiting, and error handling.

Covers the external service integration contract:
- ArticleNotFoundError on 404 / missingtitle API error
- Retry with exponential backoff on 429 (rate limited by Wikipedia)
- Retry with exponential backoff on 5xx server errors
- Retry on request timeout
- Successful article parse (links, categories, wikitext)
- Cache behaviour (hit, capacity eviction)
- Batch fetching and title validation
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from ..api_client import (
    ArticleNotFoundError,
    RateLimitError,
    WikipediaAPIClient,
    WikipediaAPIError,
    WikipediaArticle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _response(status: int = 200, json_body: dict | None = None) -> MagicMock:
    """Build a minimal requests.Response mock."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def _parse_response(
    title: str = "Python", wikitext: str = "text", links=None, categories=None
) -> dict:
    """Wrap a Wikipedia Parse API response body."""
    return {
        "parse": {
            "title": title,
            "pageid": 1234,
            "wikitext": {"*": wikitext},
            "links": [{"ns": 0, "*": lnk} for lnk in (links or ["Link A"])],
            "categories": [{"*": cat} for cat in (categories or ["Cat 1"])],
        }
    }


def _error_response(code: str, info: str = "error") -> dict:
    return {"error": {"code": code, "info": info}}


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------


class TestFetchArticleSuccess:
    """Happy-path: correct parsing of a successful API response."""

    @patch("time.sleep")
    def test_returns_wikipedia_article(self, mock_sleep):
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(
            return_value=_response(
                200, _parse_response("Python", "wikitext body", ["AI"], ["Tech"])
            )
        )
        article = client.fetch_article("Python")

        assert isinstance(article, WikipediaArticle)
        assert article.title == "Python"
        assert article.wikitext == "wikitext body"
        assert "AI" in article.links
        assert "Tech" in article.categories
        assert article.pageid == 1234

    @patch("time.sleep")
    def test_only_main_namespace_links_included(self, mock_sleep):
        """Links with ns != 0 (Talk, Category, User, …) must be excluded."""
        body = {
            "parse": {
                "title": "T",
                "pageid": 1,
                "wikitext": {"*": "x"},
                "links": [
                    {"ns": 0, "*": "Main Link"},
                    {"ns": 1, "*": "Talk:Foo"},
                    {"ns": 14, "*": "Category:Bar"},
                ],
                "categories": [],
            }
        }
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(200, body))
        article = client.fetch_article("T")

        assert article.links == ["Main Link"]


# ---------------------------------------------------------------------------
# ArticleNotFoundError
# ---------------------------------------------------------------------------


class TestArticleNotFound:
    """404 and API-level missingtitle both raise ArticleNotFoundError."""

    @patch("time.sleep")
    def test_raises_on_http_404(self, mock_sleep):
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=0)
        client.session.get = MagicMock(return_value=_response(404))
        with pytest.raises(ArticleNotFoundError):
            client.fetch_article("Nonexistent")

    @patch("time.sleep")
    def test_raises_on_missingtitle_error(self, mock_sleep):
        """Wikipedia returns 200 but with error.code == 'missingtitle' for missing articles."""
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(
            return_value=_response(
                200, _error_response("missingtitle", "The page you specified doesn't exist")
            )
        )
        with pytest.raises(ArticleNotFoundError, match="not found"):
            client.fetch_article("Missing Article")

    @patch("time.sleep")
    def test_raises_api_error_on_other_error_codes(self, mock_sleep):
        """Non-missingtitle error codes should raise WikipediaAPIError."""
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(
            return_value=_response(200, _error_response("invalidtitle", "Bad title"))
        )
        with pytest.raises(WikipediaAPIError, match="API error"):
            client.fetch_article("Bad|Title")

    @patch("time.sleep")
    def test_raises_api_error_on_missing_parse_key(self, mock_sleep):
        """Response without 'parse' key raises WikipediaAPIError."""
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(200, {"query": {}}))
        with pytest.raises(WikipediaAPIError, match="Unexpected API response"):
            client.fetch_article("Python")


# ---------------------------------------------------------------------------
# Retry on 429 rate limiting
# ---------------------------------------------------------------------------


class TestRateLimitRetry:
    """429 responses trigger exponential-backoff retry up to max_retries."""

    @patch("time.sleep")
    def test_retries_on_429_and_eventually_succeeds(self, mock_sleep):
        """Two 429 responses then a 200 should succeed after two retries."""
        client = WikipediaAPIClient(rate_limit_delay=0.01, max_retries=3)
        client.session.get = MagicMock(
            side_effect=[
                _response(429),
                _response(429),
                _response(200, _parse_response("Python")),
            ]
        )
        article = client.fetch_article("Python")
        assert article.title == "Python"
        assert client.session.get.call_count == 3

    @patch("time.sleep")
    def test_raises_rate_limit_error_after_max_retries(self, mock_sleep):
        """Persistent 429 must raise RateLimitError after max_retries exhausted."""
        client = WikipediaAPIClient(rate_limit_delay=0.01, max_retries=2)
        client.session.get = MagicMock(return_value=_response(429))
        with pytest.raises(RateLimitError):
            client.fetch_article("Python")
        # Initial request + max_retries retries = max_retries + 1 calls
        assert client.session.get.call_count == 3

    @patch("time.sleep")
    def test_retry_uses_exponential_backoff(self, mock_sleep):
        """Backoff delays should grow exponentially: delay * 2^0, delay * 2^1, …"""
        delay = 0.1
        client = WikipediaAPIClient(rate_limit_delay=delay, max_retries=3)
        client.session.get = MagicMock(
            side_effect=[
                _response(429),
                _response(429),
                _response(200, _parse_response()),
            ]
        )
        client.fetch_article("Python")

        sleep_calls = [c.args[0] for c in mock_sleep.call_args_list]
        # Should see backoff calls for 2^0 * delay and 2^1 * delay
        backoff_calls = [s for s in sleep_calls if s >= delay]
        assert backoff_calls[0] == pytest.approx(delay * 1, rel=0.1)  # 2^0 * delay
        assert backoff_calls[1] == pytest.approx(delay * 2, rel=0.1)  # 2^1 * delay


# ---------------------------------------------------------------------------
# Retry on 5xx server errors
# ---------------------------------------------------------------------------


class TestServerErrorRetry:
    """5xx server errors trigger retry with exponential backoff."""

    @patch("time.sleep")
    def test_retries_on_500_and_succeeds(self, mock_sleep):
        """A single 500 followed by a 200 should succeed after one retry."""
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=3)
        client.session.get = MagicMock(
            side_effect=[
                _response(500),
                _response(200, _parse_response("AI")),
            ]
        )
        article = client.fetch_article("AI")
        assert article.title == "AI"
        assert client.session.get.call_count == 2

    @patch("time.sleep")
    def test_raises_api_error_after_max_retries_on_500(self, mock_sleep):
        """Persistent 500 raises WikipediaAPIError after max_retries."""
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=2)
        client.session.get = MagicMock(return_value=_response(500))
        with pytest.raises(WikipediaAPIError, match="Server error"):
            client.fetch_article("Python")
        assert client.session.get.call_count == 3  # initial + 2 retries

    @patch("time.sleep")
    def test_retries_on_503(self, mock_sleep):
        """503 service unavailable should also be retried."""
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=1)
        client.session.get = MagicMock(
            side_effect=[
                _response(503),
                _response(200, _parse_response()),
            ]
        )
        article = client.fetch_article("Python")
        assert article.title == "Python"


# ---------------------------------------------------------------------------
# Retry on timeout
# ---------------------------------------------------------------------------


class TestTimeoutRetry:
    """Request timeouts trigger retry with exponential backoff."""

    @patch("time.sleep")
    def test_retries_on_timeout_and_succeeds(self, mock_sleep):
        """A single timeout followed by success should return the article."""
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=2)
        client.session.get = MagicMock(
            side_effect=[
                requests.Timeout("timed out"),
                _response(200, _parse_response("Graph")),
            ]
        )
        article = client.fetch_article("Graph")
        assert article.title == "Graph"
        assert client.session.get.call_count == 2

    @patch("time.sleep")
    def test_raises_api_error_after_max_timeout_retries(self, mock_sleep):
        """Persistent timeouts raise WikipediaAPIError after max_retries."""
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=2)
        client.session.get = MagicMock(side_effect=requests.Timeout("timed out"))
        with pytest.raises(WikipediaAPIError, match="timeout"):
            client.fetch_article("Python")
        assert client.session.get.call_count == 3


# ---------------------------------------------------------------------------
# Generic request exception
# ---------------------------------------------------------------------------


class TestRequestExceptionHandling:
    """Non-retryable request exceptions bubble up immediately."""

    @patch("time.sleep")
    def test_raises_api_error_on_connection_error(self, mock_sleep):
        """ConnectionError should raise WikipediaAPIError immediately."""
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(side_effect=requests.ConnectionError("connection refused"))
        with pytest.raises(WikipediaAPIError, match="Request failed"):
            client.fetch_article("Python")


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------


class TestCacheBehaviour:
    """Response caching: hits avoid HTTP calls; capacity evicts oldest entry."""

    @patch("time.sleep")
    def test_cache_hit_avoids_http_call(self, mock_sleep):
        """Second fetch of same title should use cache, not make HTTP call."""
        client = WikipediaAPIClient(rate_limit_delay=0, cache_enabled=True)
        client.session.get = MagicMock(return_value=_response(200, _parse_response("Python")))
        _ = client.fetch_article("Python")
        _ = client.fetch_article("Python")  # cache hit

        assert client.session.get.call_count == 1  # only one HTTP call

    @patch("time.sleep")
    def test_cache_evicts_oldest_when_at_capacity(self, mock_sleep):
        """When cache reaches _CACHE_MAX_SIZE, the oldest entry is evicted."""
        client = WikipediaAPIClient(rate_limit_delay=0, cache_enabled=True)
        client.session.get = MagicMock(
            side_effect=lambda *_, **kw: _response(
                200, _parse_response(kw.get("params", {}).get("page", "T"))
            )
        )
        # Fill cache to capacity
        for i in range(WikipediaAPIClient._CACHE_MAX_SIZE):
            client._cache[f"Article_{i}"] = WikipediaArticle(
                title=f"Article_{i}", wikitext="x", links=[], categories=[]
            )

        # Inserting one more should evict the first entry
        client.session.get = MagicMock(return_value=_response(200, _parse_response("New")))
        client.fetch_article("New")

        assert len(client._cache) == WikipediaAPIClient._CACHE_MAX_SIZE
        assert "Article_0" not in client._cache

    @patch("time.sleep")
    def test_clear_cache_empties_cache(self, mock_sleep):
        """clear_cache() should remove all cached entries."""
        client = WikipediaAPIClient(rate_limit_delay=0, cache_enabled=True)
        client.session.get = MagicMock(return_value=_response(200, _parse_response("Python")))
        client.fetch_article("Python")
        assert len(client._cache) > 0

        client.clear_cache()
        assert len(client._cache) == 0

    @patch("time.sleep")
    def test_cache_disabled_always_fetches(self, mock_sleep):
        """When cache is disabled, every call makes an HTTP request."""
        client = WikipediaAPIClient(rate_limit_delay=0, cache_enabled=False)
        client.session.get = MagicMock(return_value=_response(200, _parse_response("Python")))
        client.fetch_article("Python")
        client.fetch_article("Python")

        assert client.session.get.call_count == 2


# ---------------------------------------------------------------------------
# Batch fetch
# ---------------------------------------------------------------------------


class TestFetchBatch:
    """fetch_batch processes multiple titles and returns per-title results."""

    @patch("time.sleep")
    def test_successful_batch(self, mock_sleep):
        """All successful titles return (title, article, None)."""
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(
            side_effect=[
                _response(200, _parse_response("A")),
                _response(200, _parse_response("B")),
            ]
        )
        results = client.fetch_batch(["A", "B"])
        assert len(results) == 2
        assert all(err is None for _, _, err in results)

    @patch("time.sleep")
    def test_batch_continues_on_error_by_default(self, mock_sleep):
        """continue_on_error=True (default) should process all titles."""
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=0)
        client.session.get = MagicMock(
            side_effect=[
                _response(404),
                _response(200, _parse_response("B")),
            ]
        )
        results = client.fetch_batch(["Missing", "B"])
        assert len(results) == 2
        _, a_none, a_err = results[0]
        assert a_none is None
        assert isinstance(a_err, ArticleNotFoundError)
        _, b_article, b_err = results[1]
        assert b_article is not None
        assert b_err is None

    @patch("time.sleep")
    def test_batch_stops_on_error_when_configured(self, mock_sleep):
        """continue_on_error=False should stop after first failure."""
        client = WikipediaAPIClient(rate_limit_delay=0, max_retries=0)
        client.session.get = MagicMock(
            side_effect=[
                _response(404),
                _response(200, _parse_response("B")),
            ]
        )
        results = client.fetch_batch(["Missing", "B"], continue_on_error=False)
        assert len(results) == 1  # stopped after first error


# ---------------------------------------------------------------------------
# Title validation via Query API
# ---------------------------------------------------------------------------


class TestValidateTitles:
    """validate_titles uses the lightweight Query API to check existence."""

    @patch("time.sleep")
    def test_valid_title_returns_canonical(self, mock_sleep):
        """An existing title returns its canonical Wikipedia title."""
        query_resp = {
            "query": {
                "normalized": [],
                "redirects": [],
                "pages": {"1": {"title": "Python (programming language)", "pageid": 1}},
            }
        }
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(200, query_resp))
        result = client.validate_titles(["Python (programming language)"])
        assert result["Python (programming language)"] == "Python (programming language)"

    @patch("time.sleep")
    def test_missing_title_returns_none(self, mock_sleep):
        """A title not found on Wikipedia maps to None."""
        query_resp = {
            "query": {
                "normalized": [],
                "redirects": [],
                "pages": {"-1": {"title": "NonExistent XYZ", "missing": ""}},
            }
        }
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(200, query_resp))
        result = client.validate_titles(["NonExistent XYZ"])
        assert result["NonExistent XYZ"] is None

    @patch("time.sleep")
    def test_redirect_is_followed(self, mock_sleep):
        """Titles that redirect should resolve to their canonical target."""
        query_resp = {
            "query": {
                "normalized": [],
                "redirects": [{"from": "ML", "to": "Machine learning"}],
                "pages": {"1": {"title": "Machine learning", "pageid": 1}},
            }
        }
        client = WikipediaAPIClient(rate_limit_delay=0)
        client.session.get = MagicMock(return_value=_response(200, query_resp))
        result = client.validate_titles(["ML"])
        assert result["ML"] == "Machine learning"
