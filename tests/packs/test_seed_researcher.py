"""
Comprehensive test suite for LLMSeedResearcher.

Tests all methods with mocking for LLM calls and HTTP requests.
"""

import json
from unittest.mock import Mock, patch

import pytest
import requests

from wikigr.packs.seed_researcher import DiscoveredSource, LLMSeedResearcher


class TestDiscoveredSource:
    """Tests for DiscoveredSource dataclass."""

    def test_discovered_source_creation(self):
        """Test creating a DiscoveredSource object."""
        source = DiscoveredSource(
            url="https://docs.python.org",
            authority_score=0.95,
            content_type="official_docs",
            estimated_articles=500,
            description="Official Python documentation",
        )

        assert source.url == "https://docs.python.org"
        assert source.authority_score == 0.95
        assert source.content_type == "official_docs"
        assert source.estimated_articles == 500
        assert source.description == "Official Python documentation"

    def test_discovered_source_all_content_types(self):
        """Test all valid content_type values."""
        valid_types = ["official_docs", "blog", "tutorial", "reference", "news"]

        for content_type in valid_types:
            source = DiscoveredSource(
                url="https://example.com",
                authority_score=0.5,
                content_type=content_type,
                estimated_articles=100,
                description="Test source",
            )
            assert source.content_type == content_type


class TestLLMSeedResearcher:
    """Tests for LLMSeedResearcher class."""

    @pytest.fixture
    def researcher(self):
        """Create a researcher instance with mocked Anthropic client."""
        with patch("wikigr.packs.seed_researcher.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client
            return LLMSeedResearcher(anthropic_api_key="test-key")

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        with patch("wikigr.packs.seed_researcher.Anthropic") as mock_anthropic:
            researcher = LLMSeedResearcher(anthropic_api_key="my-key")
            mock_anthropic.assert_called_once_with(api_key="my-key")
            assert researcher.model == "claude-opus-4-6-20250826"
            assert researcher.timeout == 30
            assert researcher.max_retries == 3

    def test_init_with_custom_model(self):
        """Test initialization with custom model."""
        with patch("wikigr.packs.seed_researcher.Anthropic"):
            researcher = LLMSeedResearcher(model="claude-haiku-4-5-20251001")
            assert researcher.model == "claude-haiku-4-5-20251001"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        with patch("wikigr.packs.seed_researcher.Anthropic"):
            researcher = LLMSeedResearcher(timeout=60, max_retries=5)
            assert researcher.timeout == 60
            assert researcher.max_retries == 5


class TestDiscoverSources:
    """Tests for discover_sources() method."""

    @pytest.fixture
    def researcher(self):
        """Create a researcher instance with mocked Anthropic client."""
        with patch("wikigr.packs.seed_researcher.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client
            yield LLMSeedResearcher(anthropic_api_key="test-key")

    def test_discover_sources_basic(self, researcher):
        """Test basic source discovery."""
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text=json.dumps(
                    [
                        {
                            "url": "https://docs.microsoft.com/dotnet",
                            "authority_score": 0.95,
                            "content_type": "official_docs",
                            "estimated_articles": 1000,
                            "description": "Official .NET docs",
                        },
                        {
                            "url": "https://devblogs.microsoft.com/dotnet",
                            "authority_score": 0.85,
                            "content_type": "blog",
                            "estimated_articles": 500,
                            "description": ".NET team blog",
                        },
                    ]
                )
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        sources = researcher.discover_sources(".NET programming")

        assert len(sources) == 2
        assert sources[0].url == "https://docs.microsoft.com/dotnet"
        assert sources[0].authority_score == 0.95
        assert sources[1].url == "https://devblogs.microsoft.com/dotnet"
        assert sources[1].authority_score == 0.85

    def test_discover_sources_sorting(self, researcher):
        """Test that sources are sorted by authority_score descending."""
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text=json.dumps(
                    [
                        {
                            "url": "https://example.com/blog",
                            "authority_score": 0.5,
                            "content_type": "blog",
                        },
                        {
                            "url": "https://example.com/docs",
                            "authority_score": 0.9,
                            "content_type": "official_docs",
                        },
                        {
                            "url": "https://example.com/tutorial",
                            "authority_score": 0.7,
                            "content_type": "tutorial",
                        },
                    ]
                )
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        sources = researcher.discover_sources("test domain")

        assert len(sources) == 3
        assert sources[0].authority_score == 0.9
        assert sources[1].authority_score == 0.7
        assert sources[2].authority_score == 0.5

    def test_discover_sources_with_markdown_wrapper(self, researcher):
        """Test handling of markdown-wrapped JSON response."""
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text='```json\n[{"url": "https://example.com", "authority_score": 0.8, "content_type": "blog"}]\n```'
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        sources = researcher.discover_sources("test domain")

        assert len(sources) == 1
        assert sources[0].url == "https://example.com"

    def test_discover_sources_empty_domain(self, researcher):
        """Test error handling for empty domain."""
        with pytest.raises(ValueError, match="Domain cannot be empty"):
            researcher.discover_sources("")

        with pytest.raises(ValueError, match="Domain cannot be empty"):
            researcher.discover_sources("   ")

    def test_discover_sources_invalid_json(self, researcher):
        """Test error handling for invalid JSON response."""
        mock_response = Mock()
        mock_response.content = [Mock(text="This is not valid JSON")]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        with pytest.raises(ValueError, match="Invalid JSON response"):
            researcher.discover_sources("test domain")

    def test_discover_sources_invalid_content_type(self, researcher):
        """Test filtering of sources with invalid content_type."""
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text=json.dumps(
                    [
                        {
                            "url": "https://valid.com",
                            "authority_score": 0.9,
                            "content_type": "official_docs",
                        },
                        {
                            "url": "https://invalid.com",
                            "authority_score": 0.8,
                            "content_type": "invalid_type",
                        },
                    ]
                )
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        sources = researcher.discover_sources("test domain")

        assert len(sources) == 1
        assert sources[0].url == "https://valid.com"

    def test_discover_sources_missing_fields(self, researcher):
        """Test filtering of sources with missing required fields."""
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text=json.dumps(
                    [
                        {
                            "url": "https://complete.com",
                            "authority_score": 0.9,
                            "content_type": "official_docs",
                        },
                        {"url": "https://incomplete.com"},  # Missing required fields
                    ]
                )
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        sources = researcher.discover_sources("test domain")

        assert len(sources) == 1
        assert sources[0].url == "https://complete.com"

    def test_discover_sources_max_sources_limit(self, researcher):
        """Test that max_sources limit is respected."""
        mock_response = Mock()
        sources_data = [
            {
                "url": f"https://example{i}.com",
                "authority_score": 0.9 - i * 0.05,
                "content_type": "blog",
            }
            for i in range(20)
        ]
        mock_response.content = [Mock(text=json.dumps(sources_data))]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        sources = researcher.discover_sources("test domain", max_sources=5)

        assert len(sources) == 5

    def test_discover_sources_with_optional_fields(self, researcher):
        """Test handling of optional fields (estimated_articles, description)."""
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text=json.dumps(
                    [
                        {
                            "url": "https://example.com",
                            "authority_score": 0.9,
                            "content_type": "blog",
                            # Optional fields missing
                        }
                    ]
                )
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        sources = researcher.discover_sources("test domain")

        assert len(sources) == 1
        assert sources[0].estimated_articles == 100  # Default value
        assert sources[0].description == ""  # Default value


class TestExtractArticleUrls:
    """Tests for extract_article_urls() method."""

    @pytest.fixture
    def researcher(self):
        """Create a researcher instance."""
        with patch("wikigr.packs.seed_researcher.Anthropic"):
            return LLMSeedResearcher(anthropic_api_key="test-key")

    def test_extract_article_urls_empty_base_url(self, researcher):
        """Test error handling for empty base URL."""
        with pytest.raises(ValueError, match="Base URL cannot be empty"):
            researcher.extract_article_urls("")

    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_extract_from_sitemap(self, mock_get, researcher):
        """Test URL extraction from sitemap.xml."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/article1</loc></url>
  <url><loc>https://example.com/article2</loc></url>
  <url><loc>https://example.com/article3</loc></url>
</urlset>"""
        mock_get.return_value = mock_response

        urls = researcher._extract_from_sitemap("https://example.com")

        assert len(urls) == 3
        assert "https://example.com/article1" in urls
        assert "https://example.com/article2" in urls

    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_extract_from_rss(self, mock_get, researcher):
        """Test URL extraction from RSS feed."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item><link>https://example.com/post1</link></item>
    <item><link>https://example.com/post2</link></item>
  </channel>
</rss>"""
        mock_get.return_value = mock_response

        urls = researcher._extract_from_rss("https://example.com")

        assert len(urls) == 2
        assert "https://example.com/post1" in urls
        assert "https://example.com/post2" in urls

    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_extract_from_index(self, mock_get, researcher):
        """Test URL extraction from index page crawl."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<html>
<a href="https://example.com/page1">Page 1</a>
<a href="https://example.com/page2">Page 2</a>
<a href="https://other.com/page3">Other</a>
</html>"""
        mock_get.return_value = mock_response

        urls = researcher._extract_from_index("https://example.com")

        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://other.com/page3" not in urls  # Different domain filtered

    def test_extract_with_llm(self, researcher):
        """Test LLM-based URL generation."""
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text="""https://example.com/docs/getting-started
https://example.com/docs/tutorial
https://example.com/docs/api-reference
Some other text that should be ignored
https://example.com/blog/post1"""
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        urls = researcher._extract_with_llm("https://example.com", max_urls=10)

        assert len(urls) == 4
        assert "https://example.com/docs/getting-started" in urls
        assert "https://example.com/blog/post1" in urls

    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_extract_article_urls_multi_strategy(self, mock_get, researcher):
        """Test using multiple extraction strategies."""
        # Mock sitemap response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<urlset><url><loc>https://example.com/article1</loc></url></urlset>"
        mock_get.return_value = mock_response

        urls = researcher.extract_article_urls(
            "https://example.com", max_urls=10, strategies=["sitemap"]
        )

        assert len(urls) >= 1
        assert "https://example.com/article1" in urls

    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_extract_article_urls_max_urls_limit(self, mock_get, researcher):
        """Test that max_urls limit is respected."""
        mock_response = Mock()
        mock_response.status_code = 200
        # Generate 100 URLs in sitemap
        urls_xml = "".join(
            [f"<url><loc>https://example.com/article{i}</loc></url>" for i in range(100)]
        )
        mock_response.text = f"<urlset>{urls_xml}</urlset>"
        mock_get.return_value = mock_response

        urls = researcher.extract_article_urls("https://example.com", max_urls=10)

        assert len(urls) <= 10

    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_extract_article_urls_deduplication(self, mock_get, researcher):
        """Test that duplicate URLs are removed."""
        mock_response = Mock()
        mock_response.status_code = 200
        # Same URL appears multiple times
        mock_response.text = """<urlset>
<url><loc>https://example.com/article1</loc></url>
<url><loc>https://example.com/article1</loc></url>
<url><loc>https://example.com/article2</loc></url>
</urlset>"""
        mock_get.return_value = mock_response

        urls = researcher.extract_article_urls("https://example.com")

        assert len(urls) == 2  # Deduplicated


class TestValidateUrl:
    """Tests for validate_url() method."""

    @pytest.fixture
    def researcher(self):
        """Create a researcher instance."""
        with patch("wikigr.packs.seed_researcher.Anthropic"):
            return LLMSeedResearcher(anthropic_api_key="test-key")

    def test_validate_url_empty(self, researcher):
        """Test validation of empty URL."""
        is_valid, metadata = researcher.validate_url("")

        assert not is_valid
        assert metadata["error"] == "Empty URL"

    @patch("wikigr.packs.seed_researcher.requests.head")
    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_validate_url_success(self, mock_get, mock_head, researcher):
        """Test successful URL validation."""
        # Mock HEAD request
        mock_head_response = Mock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_head.return_value = mock_head_response

        # Mock GET request
        mock_get_response = Mock()
        mock_get_response.text = "<html><body>" + " word" * 200 + "</body></html>"
        mock_get.return_value = mock_get_response

        is_valid, metadata = researcher.validate_url("https://example.com/article")

        assert is_valid
        assert metadata["status_code"] == 200
        assert metadata["is_html"]
        assert metadata["word_count"] >= 200
        assert metadata["error"] is None

    @patch("wikigr.packs.seed_researcher.requests.head")
    def test_validate_url_http_error(self, mock_head, researcher):
        """Test validation of URL with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response

        is_valid, metadata = researcher.validate_url("https://example.com/notfound")

        assert not is_valid
        assert metadata["status_code"] == 404
        assert "HTTP 404" in metadata["error"]

    @patch("wikigr.packs.seed_researcher.requests.head")
    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_validate_url_not_html(self, mock_get, mock_head, researcher):
        """Test validation of non-HTML content."""
        mock_head_response = Mock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {"content-type": "application/pdf"}
        mock_head.return_value = mock_head_response

        # Mock GET response (even though it won't be called for non-HTML)
        mock_get_response = Mock()
        mock_get_response.text = "PDF content"
        mock_get.return_value = mock_get_response

        is_valid, metadata = researcher.validate_url("https://example.com/doc.pdf")

        assert not is_valid
        assert not metadata["is_html"]
        assert "Not HTML content" in metadata["error"]

    @patch("wikigr.packs.seed_researcher.requests.head")
    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_validate_url_too_short(self, mock_get, mock_head, researcher):
        """Test validation of content that's too short."""
        mock_head_response = Mock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {"content-type": "text/html"}
        mock_head.return_value = mock_head_response

        mock_get_response = Mock()
        mock_get_response.text = "<html><body>Short</body></html>"
        mock_get.return_value = mock_get_response

        is_valid, metadata = researcher.validate_url("https://example.com/short")

        assert not is_valid
        assert metadata["word_count"] < 100
        assert "Content too short" in metadata["error"]

    @patch("wikigr.packs.seed_researcher.requests.head")
    def test_validate_url_timeout(self, mock_head, researcher):
        """Test handling of request timeout."""
        mock_head.side_effect = requests.exceptions.Timeout()

        is_valid, metadata = researcher.validate_url("https://slow.example.com")

        assert not is_valid
        assert "timeout" in metadata["error"].lower()

    @patch("wikigr.packs.seed_researcher.requests.head")
    def test_validate_url_connection_error(self, mock_head, researcher):
        """Test handling of connection errors."""
        mock_head.side_effect = requests.exceptions.ConnectionError("Connection refused")

        is_valid, metadata = researcher.validate_url("https://unreachable.example.com")

        assert not is_valid
        assert metadata["error"] is not None


class TestRankUrls:
    """Tests for rank_urls() method."""

    @pytest.fixture
    def researcher(self):
        """Create a researcher instance."""
        with patch("wikigr.packs.seed_researcher.Anthropic"):
            return LLMSeedResearcher(anthropic_api_key="test-key")

    def test_rank_urls_empty_list(self, researcher):
        """Test ranking empty URL list."""
        ranked = researcher.rank_urls([])

        assert ranked == []

    def test_rank_urls_basic(self, researcher):
        """Test basic URL ranking."""
        urls = [
            "https://example.com/blog/post",
            "https://example.com/docs/guide",
            "https://example.com/random",
        ]

        ranked = researcher.rank_urls(urls, authority_score=0.5)

        assert len(ranked) == 3
        # /docs/ should rank higher than /blog/
        docs_score = next(score for url, score in ranked if "/docs/" in url)
        blog_score = next(score for url, score in ranked if "/blog/" in url)
        assert docs_score > blog_score

    def test_rank_urls_with_metadata(self, researcher):
        """Test ranking with metadata from validate_url."""
        urls = ["https://example.com/short", "https://example.com/long"]

        metadata_list = [
            {"word_count": 100},
            {"word_count": 5000},
        ]

        ranked = researcher.rank_urls(urls, authority_score=0.5, metadata_list=metadata_list)

        assert len(ranked) == 2
        # Longer content should rank higher
        assert ranked[0][0] == "https://example.com/long"
        assert ranked[0][1] > ranked[1][1]

    def test_rank_urls_recency_boost(self, researcher):
        """Test that recent years in URL get boosted."""
        from datetime import datetime

        current_year = datetime.now().year

        urls = [
            f"https://example.com/blog/{current_year}/post",
            "https://example.com/blog/2020/old-post",
        ]

        ranked = researcher.rank_urls(urls, authority_score=0.5)

        # Current year should rank higher
        assert ranked[0][0] == f"https://example.com/blog/{current_year}/post"

    def test_rank_urls_long_url_penalty(self, researcher):
        """Test penalty for very long URLs."""
        urls = [
            "https://example.com/short",
            "https://example.com/" + "x" * 250,  # Very long URL
        ]

        ranked = researcher.rank_urls(urls, authority_score=0.5)

        # Short URL should rank higher due to long URL penalty
        assert ranked[0][0] == "https://example.com/short"

    def test_rank_urls_sorted_descending(self, researcher):
        """Test that results are sorted by score descending."""
        urls = [
            "https://example.com/blog/post",
            "https://example.com/docs/guide",
            "https://example.com/tutorial/start",
        ]

        ranked = researcher.rank_urls(urls, authority_score=0.5)

        # Verify scores are in descending order
        scores = [score for _, score in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rank_urls_score_clamping(self, researcher):
        """Test that scores are clamped to [0, 1] range."""
        urls = ["https://example.com/docs/guide"]

        ranked = researcher.rank_urls(urls, authority_score=1.0)

        for _, score in ranked:
            assert 0.0 <= score <= 1.0


class TestIntegration:
    """Integration tests for full workflows."""

    @pytest.fixture
    def researcher(self):
        """Create a researcher instance."""
        with patch("wikigr.packs.seed_researcher.Anthropic") as mock_anthropic:
            mock_client = Mock()
            mock_anthropic.return_value = mock_client
            return LLMSeedResearcher(anthropic_api_key="test-key")

    def test_discover_and_extract_workflow(self, researcher):
        """Test full workflow: discover sources, extract URLs, validate, rank."""
        # Mock discover_sources
        mock_response = Mock()
        mock_response.content = [
            Mock(
                text=json.dumps(
                    [
                        {
                            "url": "https://docs.example.com",
                            "authority_score": 0.9,
                            "content_type": "official_docs",
                            "estimated_articles": 100,
                            "description": "Official docs",
                        }
                    ]
                )
            )
        ]
        researcher.claude.messages.create = Mock(return_value=mock_response)

        # Discover sources
        sources = researcher.discover_sources("test domain", max_sources=1)
        assert len(sources) == 1

        # Mock extract_article_urls
        with patch.object(researcher, "_extract_from_sitemap") as mock_sitemap:
            mock_sitemap.return_value = [
                "https://docs.example.com/article1",
                "https://docs.example.com/article2",
            ]

            urls = researcher.extract_article_urls(sources[0].url, max_urls=10)
            assert len(urls) >= 2

        # Rank URLs
        ranked = researcher.rank_urls(urls, authority_score=sources[0].authority_score)
        assert len(ranked) >= 2
        assert all(0.0 <= score <= 1.0 for _, score in ranked)

    @patch("wikigr.packs.seed_researcher.requests.head")
    @patch("wikigr.packs.seed_researcher.requests.get")
    def test_validate_multiple_urls(self, mock_get, mock_head, researcher):
        """Test validating multiple URLs."""
        # Mock successful response
        mock_head_response = Mock()
        mock_head_response.status_code = 200
        mock_head_response.headers = {"content-type": "text/html"}
        mock_head.return_value = mock_head_response

        mock_get_response = Mock()
        mock_get_response.text = "<html>" + " word" * 200 + "</html>"
        mock_get.return_value = mock_get_response

        urls = [
            "https://example.com/article1",
            "https://example.com/article2",
            "https://example.com/article3",
        ]

        results = []
        for url in urls:
            is_valid, metadata = researcher.validate_url(url)
            results.append((is_valid, metadata))

        valid_count = sum(1 for is_valid, _ in results if is_valid)
        assert valid_count == 3
