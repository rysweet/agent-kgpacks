"""Tests for WebContentSource retry logic, jitter, and redirect capping.

Covers SEC-07 (max_redirects=5) and SEC-11 (jitter in rate limiting),
plus exponential-backoff retry on transient HTTP errors.
"""

import time
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from ..base import ArticleNotFoundError
from ..web import WebContentSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status: int, text: str = "", headers: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.text = text
    resp.encoding = "utf-8"
    resp.apparent_encoding = "utf-8"
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def _make_html(body: str = "", title: str = "Test Page") -> str:
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body>{'word ' * 250}{body}</body></html>"
    )


# ---------------------------------------------------------------------------
# SEC-07: redirect cap
# ---------------------------------------------------------------------------


class TestMaxRedirects:
    """WebContentSource must cap HTTP redirects at 5."""

    def test_session_max_redirects_default(self):
        source = WebContentSource()
        assert source._session.max_redirects == 5

    def test_session_max_redirects_preserved_on_custom_init(self):
        source = WebContentSource(timeout=60, rate_limit_delay=1.0)
        assert source._session.max_redirects == 5


# ---------------------------------------------------------------------------
# SEC-02: SSL verification must never be disabled
# ---------------------------------------------------------------------------


class TestSSLVerification:
    """WebContentSource must never disable SSL certificate verification (SEC-02)."""

    def test_ssl_verify_enabled_by_default(self):
        """session.verify must be True (the requests default) after init."""
        source = WebContentSource()
        assert source._session.verify is not False, (
            "SSL verification must not be disabled. "
            "session.verify must remain True (or a CA bundle path)."
        )

    def test_ssl_verify_raises_if_disabled(self):
        """WebContentSource.__init__ must raise RuntimeError if verify is patched to False."""
        import requests as req

        session = req.Session()
        session.verify = False  # simulate a misconfigured session

        with pytest.raises(RuntimeError, match="SSL verification must not be disabled"):
            with patch("bootstrap.src.sources.web.requests.Session", return_value=session):
                WebContentSource()


# ---------------------------------------------------------------------------
# SEC-11: rate-limit jitter
# ---------------------------------------------------------------------------


class TestRateLimitJitter:
    """Rate limiting delay must include ±10% jitter (SEC-11)."""

    @patch("bootstrap.src.sources.web._validate_url")
    @patch("bootstrap.src.sources.web.random.uniform")
    def test_uniform_called_for_rate_limit_jitter(self, mock_uniform, mock_validate):
        """random.uniform is called once to compute the rate-limit jitter."""
        mock_validate.return_value = None
        mock_uniform.return_value = 0.0  # zero jitter for predictability

        source = WebContentSource(rate_limit_delay=0.5, max_retries=1)
        # Set last_request_time far in the past so sleep is skipped
        source._last_request_time = 0.0

        resp = _make_response(200, _make_html())
        with patch.object(source._session, "get", return_value=resp):
            source.fetch_article("https://example.com/page")

        # The first uniform call must be for rate-limit jitter: uniform(-0.1, 0.1)
        assert mock_uniform.call_count >= 1
        first_call = mock_uniform.call_args_list[0][0]
        assert first_call == (-0.1, 0.1)

    @patch("bootstrap.src.sources.web._validate_url")
    @patch("bootstrap.src.sources.web.time.sleep")
    def test_no_sleep_when_elapsed_exceeds_delay(self, mock_sleep, mock_validate):
        """time.sleep is not invoked when enough time has already passed."""
        mock_validate.return_value = None
        source = WebContentSource(rate_limit_delay=0.5, max_retries=1)
        # Simulate that a request happened a long time ago
        source._last_request_time = 0.0  # epoch — many seconds in the past

        resp = _make_response(200, _make_html())
        with (
            patch("bootstrap.src.sources.web.random.uniform", return_value=0.0),
            patch.object(source._session, "get", return_value=resp),
        ):
            source.fetch_article("https://example.com/page")

        # With elapsed >> rate_limit_delay, sleep should NOT be called for rate limiting.
        # (It may still be called by retry logic for non-200, but status=200 here.)
        mock_sleep.assert_not_called()

    @patch("bootstrap.src.sources.web._validate_url")
    @patch("bootstrap.src.sources.web.time.sleep")
    def test_sleep_called_when_delay_positive(self, mock_sleep, mock_validate):
        """time.sleep is called when elapsed time is less than rate_limit_delay."""
        mock_validate.return_value = None
        source = WebContentSource(rate_limit_delay=10.0, max_retries=1)
        # Set last_request_time to now so elapsed ≈ 0 → definitely need to sleep
        source._last_request_time = time.time()

        resp = _make_response(200, _make_html())
        with (
            patch("bootstrap.src.sources.web.random.uniform", return_value=0.0),
            patch.object(source._session, "get", return_value=resp),
        ):
            source.fetch_article("https://example.com/page")

        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        # Should sleep for close to rate_limit_delay (elapsed ≈ 0, jitter = 0)
        assert sleep_duration == pytest.approx(10.0, abs=0.2)


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """_fetch_with_retry retries on transient errors and gives up after max_retries."""

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_succeeds_on_first_attempt(self, mock_sleep):
        source = WebContentSource(max_retries=3)
        ok = _make_response(200, "ok")
        with patch.object(source._session, "get", return_value=ok) as mock_get:
            resp = source._fetch_with_retry("https://example.com/")
        assert resp.status_code == 200
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_retries_on_503(self, mock_sleep):
        """503 should trigger a retry; success on second attempt is returned."""
        source = WebContentSource(max_retries=3)
        fail = _make_response(503)
        ok = _make_response(200, "ok")
        with patch.object(source._session, "get", side_effect=[fail, ok]) as mock_get:
            resp = source._fetch_with_retry("https://example.com/")
        assert resp.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_retries_on_429_honors_retry_after(self, mock_sleep):
        """429 with Retry-After header should sleep for that many seconds."""
        source = WebContentSource(max_retries=2)
        fail = _make_response(429, headers={"Retry-After": "3"})
        ok = _make_response(200, "ok")
        with (
            patch.object(source._session, "get", side_effect=[fail, ok]),
            patch("bootstrap.src.sources.web.random.uniform", return_value=0.0),
        ):
            resp = source._fetch_with_retry("https://example.com/")
        assert resp.status_code == 200
        # Sleep should be called with ~3.0 (base_wait from Retry-After + 0.0 jitter)
        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert sleep_duration == pytest.approx(3.0, abs=0.01)

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_retries_on_429_without_retry_after(self, mock_sleep):
        """429 without Retry-After header uses exponential backoff (2^attempt)."""
        source = WebContentSource(max_retries=2)
        fail = _make_response(429, headers={})
        ok = _make_response(200, "ok")
        with (
            patch.object(source._session, "get", side_effect=[fail, ok]),
            patch("bootstrap.src.sources.web.random.uniform", return_value=0.0),
        ):
            resp = source._fetch_with_retry("https://example.com/")
        assert resp.status_code == 200
        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert sleep_duration == pytest.approx(2.0, abs=0.01)  # 2^1

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_gives_up_after_max_retries(self, mock_sleep):
        """After max_retries attempts, the last (failed) response is returned."""
        source = WebContentSource(max_retries=3)
        fail = _make_response(503)
        with patch.object(source._session, "get", return_value=fail) as mock_get:
            resp = source._fetch_with_retry("https://example.com/")
        assert resp.status_code == 503
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2  # sleeps between attempts, not after last

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_no_retry_on_404(self, mock_sleep):
        """404 is a client error and should NOT be retried."""
        source = WebContentSource(max_retries=3)
        not_found = _make_response(404)
        with patch.object(source._session, "get", return_value=not_found) as mock_get:
            resp = source._fetch_with_retry("https://example.com/missing")
        assert resp.status_code == 404
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_no_retry_on_403(self, mock_sleep):
        """403 is a client error and should NOT be retried."""
        source = WebContentSource(max_retries=3)
        forbidden = _make_response(403)
        with patch.object(source._session, "get", return_value=forbidden) as mock_get:
            resp = source._fetch_with_retry("https://example.com/private")
        assert resp.status_code == 403
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_exponential_backoff_grows(self, mock_sleep):
        """Each retry should sleep longer (2^attempt) before giving up."""
        source = WebContentSource(max_retries=3)
        fail = _make_response(500)
        with (
            patch.object(source._session, "get", return_value=fail),
            patch("bootstrap.src.sources.web.random.uniform", return_value=0.0),
        ):
            source._fetch_with_retry("https://example.com/")
        # Attempt 1→2: sleep 2^1=2, attempt 2→3: sleep 2^2=4
        sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == pytest.approx(2.0, abs=0.01)
        assert sleep_calls[1] == pytest.approx(4.0, abs=0.01)

    @patch("bootstrap.src.sources.web.time.sleep")
    def test_retry_jitter_is_non_negative(self, mock_sleep):
        """Retry jitter must not reduce sleep below the base backoff."""
        source = WebContentSource(max_retries=2)
        fail = _make_response(503)
        ok = _make_response(200, "ok")
        with (
            patch.object(source._session, "get", side_effect=[fail, ok]),
            patch("bootstrap.src.sources.web.random.uniform", return_value=0.0) as mock_rand,
        ):
            source._fetch_with_retry("https://example.com/")
        # uniform is called with (0.0, base_wait * 0.25) — lower bound 0.0 ensures no negative jitter
        jitter_call_args = mock_rand.call_args[0]
        assert jitter_call_args[0] == 0.0
        assert jitter_call_args[1] > 0.0

    def test_network_error_propagates(self):
        """requests.RequestException (network failure) should propagate to caller."""
        source = WebContentSource(max_retries=1)
        with patch.object(
            source._session, "get", side_effect=requests.ConnectionError("timeout")
        ):
            with pytest.raises(requests.ConnectionError):
                source._fetch_with_retry("https://example.com/")


# ---------------------------------------------------------------------------
# Integration: fetch_article wraps _fetch_with_retry
# ---------------------------------------------------------------------------


class TestFetchArticleRetryIntegration:
    """fetch_article should surface retry behaviour transparently."""

    @patch("bootstrap.src.sources.web._validate_url")
    @patch("bootstrap.src.sources.web.time.sleep")
    def test_fetch_article_retries_503(self, mock_sleep, mock_validate):
        """fetch_article succeeds after a 503 when _fetch_with_retry retries."""
        mock_validate.return_value = None
        source = WebContentSource(max_retries=2, min_content_words=10)

        fail = _make_response(503)
        ok = _make_response(200, _make_html("enough content here"))
        with patch.object(source._session, "get", side_effect=[fail, ok]):
            article = source.fetch_article("https://example.com/page")

        assert article is not None
        assert article.source_url == "https://example.com/page"

    @patch("bootstrap.src.sources.web._validate_url")
    @patch("bootstrap.src.sources.web.time.sleep")
    def test_fetch_article_raises_on_exhausted_retries(self, mock_sleep, mock_validate):
        """fetch_article raises ArticleNotFoundError when all retries are exhausted."""
        mock_validate.return_value = None
        source = WebContentSource(max_retries=2, min_content_words=10)

        fail = _make_response(503)
        with patch.object(source._session, "get", return_value=fail):
            with pytest.raises(ArticleNotFoundError):
                source.fetch_article("https://example.com/page")
