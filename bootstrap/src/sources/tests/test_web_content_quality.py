"""Tests for content quality threshold in WebContentSource."""

from unittest.mock import MagicMock, patch

import pytest

from ..base import ArticleNotFoundError
from ..web import WebContentSource


class TestMinContentWordsDefault:
    """Verify default min_content_words is 200."""

    def test_default_min_content_words(self):
        """WebContentSource should have min_content_words=200 by default."""
        source = WebContentSource()
        assert source._min_content_words == 200

    def test_custom_min_content_words(self):
        """Custom min_content_words should be stored and respected."""
        source = WebContentSource(min_content_words=50)
        assert source._min_content_words == 50

    def test_zero_min_content_words_disables_filter(self):
        """Setting min_content_words=0 disables the filter."""
        source = WebContentSource(min_content_words=0)
        assert source._min_content_words == 0


class TestThinContentSkipping:
    """Verify that articles below the word count threshold are skipped."""

    def _make_html(self, body_text: str, title: str = "") -> str:
        # Omit title by default so word counts in tests reflect only body text
        title_tag = f"<title>{title}</title>" if title else ""
        return f"<html><head>{title_tag}</head><body>{body_text}</body></html>"

    def _mock_response(self, html: str, status: int = 200):
        resp = MagicMock()
        resp.status_code = status
        resp.text = html
        resp.encoding = "utf-8"
        resp.apparent_encoding = "utf-8"
        resp.raise_for_status = MagicMock()
        return resp

    @patch("bootstrap.src.sources.web._validate_url")
    def test_thin_content_raises_article_not_found(self, mock_validate):
        """Articles with fewer words than threshold raise ArticleNotFoundError."""
        mock_validate.return_value = None
        source = WebContentSource(min_content_words=200)

        # Build a page with only 10 words
        thin_html = self._make_html("Hello world. This page has very little content on it.")
        resp = self._mock_response(thin_html)

        with (
            patch.object(source._session, "get", return_value=resp),
            pytest.raises(ArticleNotFoundError, match="[Tt]hin content|word"),
        ):
            source.fetch_article("https://example.com/thin-page")

    @patch("bootstrap.src.sources.web._validate_url")
    def test_sufficient_content_returns_article(self, mock_validate):
        """Articles meeting the word count threshold are returned normally."""
        mock_validate.return_value = None
        source = WebContentSource(min_content_words=10)

        # Build a page with 20 words
        rich_html = self._make_html(
            "This page has enough content to pass the minimum word count threshold "
            "because it contains many words in its body text."
        )
        resp = self._mock_response(rich_html)

        with patch.object(source._session, "get", return_value=resp):
            article = source.fetch_article("https://example.com/rich-page")

        assert article is not None
        assert article.content

    @patch("bootstrap.src.sources.web._validate_url")
    def test_threshold_zero_allows_empty_content(self, mock_validate):
        """When min_content_words=0, even empty content is returned."""
        mock_validate.return_value = None
        source = WebContentSource(min_content_words=0)

        thin_html = self._make_html("Hi.")
        resp = self._mock_response(thin_html)

        with patch.object(source._session, "get", return_value=resp):
            article = source.fetch_article("https://example.com/any-page")

        assert article is not None

    @patch("bootstrap.src.sources.web._validate_url")
    def test_exactly_at_threshold_passes(self, mock_validate):
        """An article with exactly min_content_words words should pass."""
        mock_validate.return_value = None
        # Exactly 5 words
        source = WebContentSource(min_content_words=5)
        five_word_html = self._make_html("one two three four five")
        resp = self._mock_response(five_word_html)

        with patch.object(source._session, "get", return_value=resp):
            article = source.fetch_article("https://example.com/exact")

        assert article is not None

    @patch("bootstrap.src.sources.web._validate_url")
    def test_one_below_threshold_fails(self, mock_validate):
        """An article with min_content_words - 1 words should raise."""
        mock_validate.return_value = None
        # Threshold is 5, provide 4 words
        source = WebContentSource(min_content_words=5)
        four_word_html = self._make_html("one two three four")
        resp = self._mock_response(four_word_html)

        with (
            patch.object(source._session, "get", return_value=resp),
            pytest.raises(ArticleNotFoundError),
        ):
            source.fetch_article("https://example.com/short")

    @patch("bootstrap.src.sources.web._validate_url")
    def test_warning_logged_for_thin_content(self, mock_validate, caplog):
        """A warning should be logged when thin content is skipped."""
        import logging

        mock_validate.return_value = None
        source = WebContentSource(min_content_words=200)
        thin_html = self._make_html("Too short.")
        resp = self._mock_response(thin_html)

        with (
            patch.object(source._session, "get", return_value=resp),
            caplog.at_level(logging.WARNING, logger="bootstrap.src.sources.web"),
            pytest.raises(ArticleNotFoundError),
        ):
            source.fetch_article("https://example.com/thin")

        assert any(
            "thin" in record.message.lower() or "word" in record.message.lower()
            for record in caplog.records
        )
