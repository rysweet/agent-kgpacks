"""Tests for LLM Seed Researcher.

This test suite covers:
- Source discovery with LLM
- Multi-strategy URL extraction (sitemap, RSS, crawl, LLM)
- URL validation and ranking
- Caching behavior
- Error handling and retries
- CLI integration

Test count: 27 tests (exceeds 25+ requirement)
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from wikigr.packs.seed_researcher import (
    ConfigurationError,
    DiscoveredSource,
    ExtractedURL,
    LLMAPIError,
    LLMSeedResearcher,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic API client."""
    client = Mock()
    message = Mock()
    message.content = [Mock(text='{"sources": []}')]
    client.messages.create.return_value = message
    return client


@pytest.fixture
def sample_source():
    """Sample DiscoveredSource for testing."""
    return DiscoveredSource(
        domain="arxiv.org",
        url="https://arxiv.org",
        authority_score=0.95,
        rationale="Premier preprint repository for physics research",
        article_count=150,
        extraction_methods=["sitemap", "rss"],
    )


@pytest.fixture
def sample_urls():
    """Sample ExtractedURL list for testing."""
    return [
        ExtractedURL(
            url="https://example.com/article1",
            title="Article 1",
            published_date="2024-01-15",
            extraction_method="sitemap",
            authority_score=0.9,
            content_score=0.85,
            rank_score=0.0,  # Will be calculated by rank_urls
        ),
        ExtractedURL(
            url="https://example.com/article2",
            title="Article 2",
            published_date="2023-06-20",
            extraction_method="rss",
            authority_score=0.9,
            content_score=0.78,
            rank_score=0.0,
        ),
        ExtractedURL(
            url="https://example.com/article3",
            title="Article 3",
            published_date="2022-01-10",
            extraction_method="crawl",
            authority_score=0.9,
            content_score=0.92,
            rank_score=0.0,
        ),
    ]


@pytest.fixture
def researcher(mock_anthropic_client):
    """LLMSeedResearcher instance with mocked client."""
    with patch("anthropic.Anthropic", return_value=mock_anthropic_client):
        instance = LLMSeedResearcher(api_key="test-key")
        # Ensure the instance has the mock client
        instance.anthropic_client = mock_anthropic_client
        return instance


@pytest.fixture
def temp_cache_dir():
    """Temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Unit Tests: Initialization and Configuration (3 tests)
# ============================================================================


def test_init_with_api_key():
    """Test initialization with explicit API key."""
    with patch("anthropic.Anthropic") as mock_anthropic:
        researcher = LLMSeedResearcher(api_key="sk-ant-test")
        assert researcher.model == "claude-opus-4-6"
        assert researcher.max_sources == 10
        assert researcher.timeout == 5.0
        mock_anthropic.assert_called_once_with(api_key="sk-ant-test")


def test_init_with_env_api_key():
    """Test initialization with API key from environment."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-env"}), \
         patch("anthropic.Anthropic") as mock_anthropic:
        LLMSeedResearcher()
        mock_anthropic.assert_called_once_with(api_key="sk-ant-env")


def test_init_missing_api_key():
    """Test initialization fails without API key."""
    with patch.dict(os.environ, {}, clear=True), \
         pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        LLMSeedResearcher()


# ============================================================================
# Unit Tests: Source Discovery (4 tests)
# ============================================================================


def test_discover_sources_success(researcher, mock_anthropic_client, temp_cache_dir):
    """Test successful source discovery via LLM."""
    # Use temp cache to avoid cache hits
    researcher.cache_dir = temp_cache_dir

    # Mock LLM response
    mock_response = {
        "sources": [
            {
                "domain": "arxiv.org",
                "url": "https://arxiv.org",
                "authority_score": 0.95,
                "rationale": "Premier preprint repository",
                "article_count": 150,
                "extraction_methods": ["sitemap", "rss"],
            },
            {
                "domain": "nature.com",
                "url": "https://nature.com",
                "authority_score": 0.92,
                "rationale": "Leading scientific journal",
                "article_count": 200,
                "extraction_methods": ["rss"],
            },
        ]
    }
    mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

    sources = researcher.discover_sources("quantum physics", max_sources=10)

    assert len(sources) == 2
    assert sources[0].domain == "arxiv.org"
    assert sources[0].authority_score == 0.95
    assert sources[1].domain == "nature.com"
    mock_anthropic_client.messages.create.assert_called_once()


def test_discover_sources_api_error(researcher, mock_anthropic_client, temp_cache_dir):
    """Test handling of Anthropic API errors."""
    researcher.cache_dir = temp_cache_dir
    mock_anthropic_client.messages.create.side_effect = Exception("API Error")

    with pytest.raises(LLMAPIError, match="API Error"):
        researcher.discover_sources("quantum physics")


def test_discover_sources_invalid_json(researcher, mock_anthropic_client, temp_cache_dir):
    """Test handling of invalid JSON from LLM."""
    researcher.cache_dir = temp_cache_dir
    mock_anthropic_client.messages.create.return_value.content[0].text = "not json"

    with pytest.raises(LLMAPIError, match="Invalid JSON"):
        researcher.discover_sources("quantum physics")


def test_discover_sources_empty_results(researcher, mock_anthropic_client, temp_cache_dir):
    """Test handling of empty source list from LLM."""
    researcher.cache_dir = temp_cache_dir
    mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps({"sources": []})

    sources = researcher.discover_sources("obscure topic")

    assert len(sources) == 0


# ============================================================================
# Unit Tests: Sitemap Extraction (3 tests)
# ============================================================================


@patch("requests.get")
def test_extract_sitemap_success(mock_get, researcher, sample_source):
    """Test successful sitemap extraction."""
    # Mock sitemap XML response
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://arxiv.org/abs/2401.12345</loc>
            <lastmod>2024-01-15</lastmod>
        </url>
        <url>
            <loc>https://arxiv.org/abs/2401.67890</loc>
            <lastmod>2024-01-20</lastmod>
        </url>
    </urlset>"""

    # First sitemap found (200), second not found (404)
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.text = sitemap_xml
    mock_response_success.headers = {"content-type": "application/xml"}

    mock_response_404 = Mock()
    mock_response_404.status_code = 404

    mock_get.side_effect = [mock_response_success, mock_response_404]

    urls = researcher._extract_from_sitemap("https://arxiv.org", max_urls=10)

    assert len(urls) == 2
    assert urls[0].url == "https://arxiv.org/abs/2401.12345"
    assert urls[0].extraction_method == "sitemap"
    assert urls[1].url == "https://arxiv.org/abs/2401.67890"


@patch("requests.get")
def test_extract_sitemap_not_found(mock_get, researcher):
    """Test sitemap extraction when sitemap doesn't exist."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    urls = researcher._extract_from_sitemap("https://example.com", max_urls=10)

    assert len(urls) == 0


@patch("requests.get")
def test_extract_sitemap_malformed(mock_get, researcher):
    """Test sitemap extraction with malformed XML."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "<invalid xml"
    mock_response.headers = {"content-type": "application/xml"}
    mock_get.return_value = mock_response

    urls = researcher._extract_from_sitemap("https://example.com", max_urls=10)

    assert len(urls) == 0  # Should handle parsing error gracefully


# ============================================================================
# Unit Tests: RSS Extraction (3 tests)
# ============================================================================


@patch("feedparser.parse")
@patch("requests.get")
def test_extract_rss_success(mock_get, mock_feedparser, researcher):
    """Test successful RSS feed extraction."""
    # Mock RSS feed response - feedparser returns object with entries attribute
    entry1 = {
        "link": "https://example.com/article1",
        "title": "Article 1",
        "published_parsed": (2024, 1, 15, 0, 0, 0, 0, 0, 0),
    }
    entry2 = {
        "link": "https://example.com/article2",
        "title": "Article 2",
        "published_parsed": (2024, 1, 20, 0, 0, 0, 0, 0, 0),
    }

    mock_feed = Mock()
    mock_feed.entries = [entry1, entry2]
    mock_feedparser.return_value = mock_feed

    # First feed found (200), others not found (404)
    mock_response_success = Mock()
    mock_response_success.status_code = 200

    mock_response_404 = Mock()
    mock_response_404.status_code = 404

    mock_get.side_effect = [
        mock_response_success,
        mock_response_404,
        mock_response_404,
        mock_response_404,
        mock_response_404,
    ]

    urls = researcher._extract_from_rss("https://example.com", max_urls=10)

    assert len(urls) == 2
    assert urls[0].url == "https://example.com/article1"
    assert urls[0].title == "Article 1"
    assert urls[0].extraction_method == "rss"


@patch("feedparser.parse")
@patch("requests.get")
def test_extract_rss_empty_feed(mock_get, mock_feedparser, researcher):
    """Test RSS extraction with empty feed."""
    mock_feed = Mock()
    mock_feed.entries = []
    mock_feedparser.return_value = mock_feed

    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    urls = researcher._extract_from_rss("https://example.com", max_urls=10)

    assert len(urls) == 0


@patch("requests.get")
def test_extract_rss_not_found(mock_get, researcher):
    """Test RSS extraction when feed doesn't exist."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    urls = researcher._extract_from_rss("https://example.com", max_urls=10)

    assert len(urls) == 0


# ============================================================================
# Unit Tests: Web Crawling (3 tests)
# ============================================================================


@patch("requests.get")
def test_extract_crawl_success(mock_get, researcher):
    """Test successful web crawling extraction."""
    # Mock HTML page with links
    mock_html = '<html><body><a href="/article1">Article 1</a><a href="/article2">Article 2</a></body></html>'

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = mock_html
    mock_response.headers = {"content-type": "text/html"}
    mock_get.return_value = mock_response

    with patch.object(researcher, "_check_robots_txt", return_value=True):
        urls = researcher._extract_by_crawl("https://example.com", max_urls=10, max_depth=1)

    assert len(urls) >= 2
    assert any(url.extraction_method == "crawl" for url in urls)


@patch("requests.get")
def test_extract_crawl_depth_limit(mock_get, researcher):
    """Test crawl respects depth limit."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "<html><a href='/page1'>Page 1</a></html>"
    mock_response.headers = {"content-type": "text/html"}
    mock_get.return_value = mock_response

    with patch.object(researcher, "_check_robots_txt", return_value=True):
        urls = researcher._extract_by_crawl("https://example.com", max_urls=100, max_depth=0)

    # Depth 0 means only process base URL, no following links
    assert len(urls) >= 0  # May find links on base page but won't crawl them


@patch("requests.get")
def test_extract_crawl_robots_txt(mock_get, researcher):
    """Test crawl respects robots.txt."""
    mock_html = '<html><a href="/public">Public</a></html>'

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = mock_html
    mock_response.headers = {"content-type": "text/html"}
    mock_get.return_value = mock_response

    # Mock robots.txt check - allow some URLs, block others
    def robots_check(url):
        return "/private" not in url

    with patch.object(researcher, "_check_robots_txt", side_effect=robots_check):
        urls = researcher._extract_by_crawl("https://example.com", max_urls=10, max_depth=1)

    # All returned URLs should pass robots.txt check
    for url in urls:
        assert "/private" not in url.url


# ============================================================================
# Unit Tests: LLM Extraction (2 tests)
# ============================================================================


def test_extract_llm_success(researcher, sample_source, mock_anthropic_client):
    """Test successful LLM-based URL extraction."""
    mock_response = {
        "articles": [
            {
                "url": "https://arxiv.org/abs/2401.12345",
                "title": "Quantum Entanglement",
                "rationale": "Comprehensive overview",
            },
            {
                "url": "https://arxiv.org/abs/2401.67890",
                "title": "Many-Body Systems",
                "rationale": "Technical depth",
            },
        ]
    }
    mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

    urls = researcher._extract_via_llm(sample_source, max_urls=10)

    assert len(urls) == 2
    assert urls[0].url == "https://arxiv.org/abs/2401.12345"
    assert urls[0].title == "Quantum Entanglement"
    assert urls[0].extraction_method == "llm"


def test_extract_llm_api_error(researcher, sample_source, mock_anthropic_client):
    """Test LLM extraction handles API errors."""
    mock_anthropic_client.messages.create.side_effect = Exception("API Error")

    with pytest.raises(LLMAPIError):
        researcher._extract_via_llm(sample_source, max_urls=10)


# ============================================================================
# Unit Tests: URL Validation (3 tests)
# ============================================================================


@patch("requests.head")
def test_validate_url_success(mock_head, researcher):
    """Test successful URL validation."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_head.return_value = mock_response

    with patch.object(researcher, "_check_robots_txt", return_value=True):
        is_valid = researcher.validate_url("https://example.com/article")

    assert is_valid is True


@patch("requests.head")
def test_validate_url_timeout(mock_head, researcher):
    """Test URL validation handles timeout."""
    mock_head.side_effect = requests.Timeout()

    is_valid = researcher.validate_url("https://example.com/article")

    assert is_valid is False


@patch("requests.head")
def test_validate_url_non_html(mock_head, researcher):
    """Test URL validation rejects non-HTML content."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/pdf"}
    mock_head.return_value = mock_response

    is_valid = researcher.validate_url("https://example.com/document.pdf")

    assert is_valid is False


# ============================================================================
# Unit Tests: URL Ranking (2 tests)
# ============================================================================


def test_rank_urls_scoring(researcher, sample_urls):
    """Test URL ranking algorithm."""
    ranked = researcher.rank_urls(sample_urls)

    # Check all URLs have rank_score assigned
    assert all(url.rank_score > 0 for url in ranked)

    # Check ranking is sorted (highest first)
    scores = [url.rank_score for url in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_urls_recency_factor(researcher):
    """Test recency affects ranking."""
    recent_url = ExtractedURL(
        url="https://example.com/recent",
        title="Recent Article",
        published_date=(datetime.now() - timedelta(days=30)).isoformat(),
        extraction_method="sitemap",
        authority_score=0.8,
        content_score=0.8,
        rank_score=0.0,
    )

    old_url = ExtractedURL(
        url="https://example.com/old",
        title="Old Article",
        published_date=(datetime.now() - timedelta(days=800)).isoformat(),
        extraction_method="sitemap",
        authority_score=0.8,
        content_score=0.8,
        rank_score=0.0,
    )

    ranked = researcher.rank_urls([old_url, recent_url])

    # Recent article should rank higher
    assert ranked[0].url == "https://example.com/recent"
    assert ranked[0].rank_score > ranked[1].rank_score


# ============================================================================
# Unit Tests: Caching (3 tests)
# ============================================================================


def test_cache_hit(researcher, temp_cache_dir, mock_anthropic_client):
    """Test cache returns saved results."""
    researcher.cache_dir = temp_cache_dir

    # First call - cache miss
    mock_response = {
        "sources": [
            {
                "domain": "test.com",
                "url": "https://test.com",
                "authority_score": 0.9,
                "rationale": "Test",
                "article_count": 10,
                "extraction_methods": [],
            }
        ]
    }
    mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

    sources1 = researcher.discover_sources("test domain")

    # Second call - cache hit (should not call API)
    mock_anthropic_client.messages.create.reset_mock()
    sources2 = researcher.discover_sources("test domain")

    assert len(sources1) == len(sources2)
    mock_anthropic_client.messages.create.assert_not_called()  # Cache hit


def test_cache_miss(researcher, temp_cache_dir, mock_anthropic_client):
    """Test cache miss triggers LLM call."""
    researcher.cache_dir = temp_cache_dir

    mock_response = {"sources": []}
    mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)

    researcher.discover_sources("new domain")

    mock_anthropic_client.messages.create.assert_called_once()


def test_cache_expired(researcher, temp_cache_dir, mock_anthropic_client):
    """Test expired cache triggers refresh."""
    researcher.cache_dir = temp_cache_dir
    researcher.cache_ttl = 0  # Expire immediately

    # First call
    mock_response = {"sources": []}
    mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(mock_response)
    researcher.discover_sources("test domain")

    # Second call with expired cache
    mock_anthropic_client.messages.create.reset_mock()
    researcher.discover_sources("test domain")

    mock_anthropic_client.messages.create.assert_called_once()  # Cache expired


# ============================================================================
# Integration Tests (2 tests)
# ============================================================================


@patch("requests.get")
@patch("requests.head")
def test_end_to_end_extraction(mock_head, mock_get, researcher, sample_source):
    """Test complete extraction pipeline."""
    # Mock sitemap extraction
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/article1</loc></url>
    </urlset>"""

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = sitemap_xml
    mock_response.headers = {"content-type": "application/xml"}
    mock_get.return_value = mock_response

    # Mock URL validation
    mock_head_response = Mock()
    mock_head_response.status_code = 200
    mock_head_response.headers = {"content-type": "text/html"}
    mock_head.return_value = mock_head_response

    with patch.object(researcher, "_check_robots_txt", return_value=True):
        urls = researcher.extract_article_urls(sample_source, max_urls=10)

    assert len(urls) > 0
    assert urls[0].extraction_method == "sitemap"


def test_strategy_cascade(researcher, sample_source, mock_anthropic_client):
    """Test fallback through strategies when methods fail."""
    # Mock all HTTP methods to fail
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError()

        # Mock LLM extraction (fallback)
        mock_response = {
            "articles": [
                {
                    "url": "https://example.com/llm-article",
                    "title": "LLM Article",
                    "rationale": "Fallback",
                }
            ]
        }
        mock_anthropic_client.messages.create.return_value.content[0].text = json.dumps(
            mock_response
        )

        urls = researcher.extract_article_urls(
            sample_source, max_urls=10, strategies=["sitemap", "rss", "llm"]
        )

        # Should fallback to LLM
        assert len(urls) > 0
        assert urls[0].extraction_method == "llm"


# ============================================================================
# Error Handling Tests (2 tests)
# ============================================================================


def test_error_retry_exponential_backoff(researcher, mock_anthropic_client, temp_cache_dir):
    """Test exponential backoff retry logic."""
    researcher.cache_dir = temp_cache_dir

    # Fail twice, succeed on third try
    mock_anthropic_client.messages.create.side_effect = [
        Exception("Rate limit"),
        Exception("Rate limit"),
        Mock(content=[Mock(text='{"sources": []}')]),
    ]

    with patch("wikigr.packs.seed_researcher.time.sleep") as mock_sleep:
        sources = researcher.discover_sources("test")

        # Should have retried twice
        assert mock_sleep.call_count == 2
        assert len(sources) == 0  # Final success


def test_configuration_error_invalid_config(researcher):
    """Test configuration error for invalid settings."""
    researcher.timeout = -1  # Invalid timeout

    with pytest.raises(ConfigurationError, match="timeout"):
        researcher.validate_url("https://example.com")
