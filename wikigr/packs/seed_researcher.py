"""LLM Seed Researcher for automatic source and article URL discovery.

This module provides LLM-powered research capabilities for discovering
authoritative sources and extracting article URLs for knowledge pack creation.

Uses Claude Opus 4.6 to identify domain experts and employs multi-strategy
extraction (sitemap, RSS, crawl, LLM) to find high-quality article URLs.
"""

import hashlib
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import anthropic
import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================


class SeedResearcherError(Exception):
    """Base exception for seed researcher errors."""


class LLMAPIError(SeedResearcherError):
    """Anthropic API failures."""


class ExtractionError(SeedResearcherError):
    """URL extraction failures."""


class ValidationError(SeedResearcherError):
    """URL validation failures."""


class ConfigurationError(SeedResearcherError):
    """Missing API key or invalid configuration."""


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class DiscoveredSource:
    """Represents an authoritative source discovered by LLM.

    Attributes:
        domain: Domain name (e.g., "nasa.gov")
        url: Base URL of the source
        authority_score: Authority ranking (0.0-1.0)
        rationale: Why this source is authoritative
        article_count: Number of extractable articles
        extraction_methods: List of supported extraction methods
    """

    domain: str
    url: str
    authority_score: float
    rationale: str
    article_count: int
    extraction_methods: list[str]


@dataclass
class ExtractedURL:
    """Represents a discovered article URL.

    Attributes:
        url: Full article URL
        title: Article title (if available)
        published_date: Publication date (ISO format, if available)
        extraction_method: How URL was found (sitemap/rss/crawl/llm)
        authority_score: Inherited from source
        content_score: Content quality score (0.0-1.0)
        rank_score: Final combined score for ranking
    """

    url: str
    title: str | None
    published_date: str | None
    extraction_method: str
    authority_score: float
    content_score: float
    rank_score: float


# ============================================================================
# LLM Seed Researcher
# ============================================================================


class LLMSeedResearcher:
    """LLM-powered researcher for discovering authoritative sources and article URLs.

    Uses Claude Opus 4.6 to discover domain-specific authoritative sources,
    then employs multi-strategy extraction to find article URLs.

    Attributes:
        anthropic_client: Anthropic API client
        model: Claude model name (default: claude-opus-4-6)
        max_sources: Maximum sources to discover (default: 10)
        timeout: HTTP request timeout (default: 5.0s)
        cache_dir: Cache directory for discovered sources
        cache_ttl: Cache TTL in days (default: 7)
        max_crawl_depth: Maximum crawl depth (default: 2)
        user_agent: User agent for HTTP requests
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-6"):
        """Initialize researcher with Anthropic API client.

        Args:
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            model: Claude model name (default: claude-opus-4-6)

        Raises:
            ConfigurationError: If API key not provided and not in environment
        """
        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY not set. Provide api_key parameter or set environment variable."
            )

        self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_sources = 10
        self.timeout = 5.0
        self.max_crawl_depth = 2
        self.user_agent = "WikiGR-SeedResearcher/1.0"

        # Cache configuration
        self.cache_dir = Path(
            os.environ.get("WIKIGR_CACHE_DIR", Path.home() / ".wikigr/cache/sources")
        )
        self.cache_ttl = int(os.environ.get("WIKIGR_CACHE_TTL", 7))

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def discover_sources(self, domain: str, max_sources: int = 10) -> list[DiscoveredSource]:
        """Discover authoritative sources for a domain using LLM.

        Uses Claude to identify the most authoritative sources for articles
        on a given topic/domain. Results are cached for 7 days by default.

        Args:
            domain: Topic or domain (e.g., "quantum physics", "climate science")
            max_sources: Maximum number of sources to return

        Returns:
            List of DiscoveredSource objects ranked by authority

        Raises:
            LLMAPIError: On LLM API failures
            ValidationError: If domain contains invalid characters
        """
        # Validate domain input (basic sanitization)
        if not domain or not domain.strip():
            raise ValidationError("Domain cannot be empty")

        # Remove potentially dangerous characters
        domain = domain.strip()
        if any(char in domain for char in ["\x00", "\n", "\r"]):
            raise ValidationError("Domain contains invalid characters")

        # Check cache first
        cache_key = hashlib.md5(domain.encode()).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age < timedelta(days=self.cache_ttl):
                logger.info(f"Cache hit for domain: {domain}")
                with open(cache_file) as f:
                    cached_data = json.load(f)
                    return [DiscoveredSource(**s) for s in cached_data["sources"]]

        # Cache miss - call LLM
        logger.info(f"Cache miss for domain: {domain}, calling LLM")

        prompt = f"""You are an expert researcher identifying authoritative sources for knowledge in specific domains.

For the domain "{domain}", identify the top {max_sources} most authoritative online sources for high-quality articles.

For each source, provide:
1. Domain name (e.g., "nasa.gov")
2. Base URL (e.g., "https://nasa.gov")
3. Authority score (0.0-1.0): How authoritative is this source?
4. Rationale: Why is this source authoritative?
5. Estimated article count: How many quality articles are likely available?
6. Extraction methods: List of likely extraction methods ["sitemap", "rss", "crawl"]

Focus on sources with:
- Institutional authority (universities, research labs, government agencies)
- Established reputation in the field
- Regularly updated content
- Technical depth and accuracy

Return JSON with this exact structure:
{{
  "sources": [
    {{
      "domain": "example.com",
      "url": "https://example.com",
      "authority_score": 0.95,
      "rationale": "Leading institution in the field",
      "article_count": 150,
      "extraction_methods": ["sitemap", "rss"]
    }}
  ]
}}"""

        try:
            response = self._call_llm_with_retry(prompt)
            sources_data = json.loads(response)

            sources = [DiscoveredSource(**source) for source in sources_data["sources"]]

            # Cache results
            cache_data = {"domain": domain, "sources": [asdict(s) for s in sources]}
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            return sources

        except ValidationError:
            # Re-raise validation errors (don't wrap in LLMAPIError)
            raise
        except json.JSONDecodeError as e:
            raise LLMAPIError(f"Invalid JSON response from LLM: {e}") from e
        except Exception as e:
            raise LLMAPIError(f"LLM API error: {e}") from e

    def extract_article_urls(
        self,
        source: DiscoveredSource,
        max_urls: int = 100,
        strategies: list[str] | None = None,
    ) -> list[ExtractedURL]:
        """Extract article URLs from a source using multi-strategy approach.

        Tries strategies in order until sufficient URLs found:
        1. Sitemap: Parse XML sitemaps
        2. RSS: Parse RSS/Atom feeds
        3. Crawl: Follow internal links (depth-limited)
        4. LLM: Ask Claude to suggest article URLs

        Args:
            source: DiscoveredSource to extract from
            max_urls: Maximum URLs to extract
            strategies: Extraction strategies to try (default: all in order)

        Returns:
            List of ExtractedURL objects

        Raises:
            ExtractionError: On extraction failures (with partial results)
        """
        if strategies is None:
            strategies = ["sitemap", "rss", "crawl", "llm"]

        all_urls: list[ExtractedURL] = []
        errors = []

        for strategy in strategies:
            if len(all_urls) >= max_urls:
                break

            try:
                logger.info(f"Trying {strategy} extraction for {source.domain}")

                if strategy == "sitemap":
                    urls = self._extract_from_sitemap(source.url, max_urls - len(all_urls))
                elif strategy == "rss":
                    urls = self._extract_from_rss(source.url, max_urls - len(all_urls))
                elif strategy == "crawl":
                    urls = self._extract_by_crawl(source.url, max_urls - len(all_urls))
                elif strategy == "llm":
                    urls = self._extract_via_llm(source, max_urls - len(all_urls))
                else:
                    continue

                # Set authority score from source
                for url in urls:
                    url.authority_score = source.authority_score

                all_urls.extend(urls)
                logger.info(f"{strategy} extracted {len(urls)} URLs")

            except Exception as e:
                logger.warning(f"{strategy} extraction failed: {e}")
                errors.append(f"{strategy}: {e}")
                continue

        if not all_urls and errors:
            raise ExtractionError(f"All strategies failed: {errors}")

        return all_urls[:max_urls]

    def validate_url(self, url: str) -> bool:
        """Validate URL accessibility and content type.

        Checks:
        - URL scheme is http or https (security)
        - HTTP 200 response
        - Content-Type is HTML
        - Respects robots.txt
        - Response within timeout

        Args:
            url: URL to validate

        Returns:
            True if URL is valid and accessible
        """
        if self.timeout <= 0:
            raise ConfigurationError("timeout must be positive")

        try:
            # Validate URL scheme (only http/https allowed)
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False

            # Check robots.txt first
            if not self._check_robots_txt(url):
                return False

            # Send HEAD request to check accessibility
            response = requests.head(
                url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
                allow_redirects=True,
            )

            if response.status_code != 200:
                return False

            # Check content type is HTML
            content_type = response.headers.get("content-type", "")
            return "text/html" in content_type.lower()

        except (requests.Timeout, requests.ConnectionError, requests.RequestException):
            return False

    def rank_urls(self, urls: list[ExtractedURL]) -> list[ExtractedURL]:
        """Rank URLs by authority, recency, and content quality.

        Scoring:
        - Authority (40%): From source authority_score
        - Recency (30%): Publication date (prefer <2 years)
        - Content (30%): Quality signals (word count, structure)

        Args:
            urls: List of ExtractedURL objects to rank

        Returns:
            URLs sorted by rank_score (highest first)
        """
        for url in urls:
            # Authority score (40%)
            authority = url.authority_score * 0.4

            # Recency score (30%)
            recency = self._score_recency(url.published_date) * 0.3

            # Content score (30%)
            content = url.content_score * 0.3

            url.rank_score = authority + recency + content

        # Sort by rank_score descending
        return sorted(urls, key=lambda u: u.rank_score, reverse=True)

    # ========================================================================
    # Private Methods: Extraction Strategies
    # ========================================================================

    def _extract_from_sitemap(self, base_url: str, max_urls: int) -> list[ExtractedURL]:
        """Extract URLs from XML sitemap.

        Args:
            base_url: Base URL of site
            max_urls: Maximum URLs to extract

        Returns:
            List of ExtractedURL objects from sitemap
        """
        sitemap_urls = [
            urljoin(base_url, "/sitemap.xml"),
            urljoin(base_url, "/sitemap_index.xml"),
        ]

        all_urls = []

        for sitemap_url in sitemap_urls:
            if len(all_urls) >= max_urls:
                break

            try:
                response = requests.get(
                    sitemap_url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )

                if response.status_code != 200:
                    continue

                # Parse XML sitemap
                try:
                    root = ET.fromstring(response.text)
                except ET.ParseError:
                    continue

                # Extract URLs from sitemap
                namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

                for url_elem in root.findall(".//ns:url", namespace):
                    loc = url_elem.find("ns:loc", namespace)
                    if loc is not None and loc.text:
                        lastmod = url_elem.find("ns:lastmod", namespace)
                        published = lastmod.text if lastmod is not None else None

                        all_urls.append(
                            ExtractedURL(
                                url=loc.text,
                                title=None,
                                published_date=published,
                                extraction_method="sitemap",
                                authority_score=0.0,  # Set by caller
                                content_score=0.8,  # Default for sitemap URLs
                                rank_score=0.0,
                            )
                        )

                        if len(all_urls) >= max_urls:
                            break

            except (requests.RequestException, ET.ParseError):
                continue

        return all_urls[:max_urls]

    def _extract_from_rss(self, base_url: str, max_urls: int) -> list[ExtractedURL]:
        """Extract URLs from RSS/Atom feeds.

        Args:
            base_url: Base URL of site
            max_urls: Maximum URLs to extract

        Returns:
            List of ExtractedURL objects from RSS feed
        """
        rss_paths = ["/feed", "/rss", "/atom.xml", "/feed.xml", "/rss.xml"]

        all_urls = []

        for path in rss_paths:
            if len(all_urls) >= max_urls:
                break

            feed_url = urljoin(base_url, path)

            try:
                response = requests.get(
                    feed_url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )

                if response.status_code != 200:
                    continue

                # Parse feed
                feed = feedparser.parse(response.text)

                for entry in feed.entries:
                    link = entry.get("link")
                    if not link:
                        continue

                    title = entry.get("title")
                    published = None

                    if "published_parsed" in entry and entry.get("published_parsed"):
                        published = time.strftime("%Y-%m-%d", entry.get("published_parsed"))

                    all_urls.append(
                        ExtractedURL(
                            url=link,
                            title=title,
                            published_date=published,
                            extraction_method="rss",
                            authority_score=0.0,
                            content_score=0.85,  # RSS URLs tend to be recent
                            rank_score=0.0,
                        )
                    )

                    if len(all_urls) >= max_urls:
                        break

            except requests.RequestException:
                continue

        return all_urls[:max_urls]

    def _extract_by_crawl(
        self, base_url: str, max_urls: int, max_depth: int = 2
    ) -> list[ExtractedURL]:
        """Extract URLs by crawling (BFS with depth limit).

        Args:
            base_url: Base URL to start crawling
            max_urls: Maximum URLs to extract
            max_depth: Maximum crawl depth (default: 2)

        Returns:
            List of ExtractedURL objects from crawling
        """
        visited = set()
        to_visit = [(base_url, 0)]  # (url, depth)
        all_urls = []

        base_domain = urlparse(base_url).netloc

        while to_visit and len(all_urls) < max_urls:
            current_url, depth = to_visit.pop(0)

            if current_url in visited or depth > max_depth:
                continue

            visited.add(current_url)

            try:
                # Check robots.txt
                if not self._check_robots_txt(current_url):
                    continue

                response = requests.get(
                    current_url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )

                if response.status_code != 200:
                    continue

                if "text/html" not in response.headers.get("content-type", ""):
                    continue

                # Parse HTML and extract links
                soup = BeautifulSoup(response.text, "html.parser")

                for link_elem in soup.find_all("a", href=True):
                    href = link_elem.get("href")
                    absolute_url = urljoin(current_url, href)

                    # Only follow links on same domain
                    if urlparse(absolute_url).netloc != base_domain:
                        continue

                    # Extract article title from link text
                    title = link_elem.string if link_elem.string else None

                    all_urls.append(
                        ExtractedURL(
                            url=absolute_url,
                            title=title,
                            published_date=None,
                            extraction_method="crawl",
                            authority_score=0.0,
                            content_score=0.75,  # Crawled URLs less certain
                            rank_score=0.0,
                        )
                    )

                    # Add to queue for further crawling
                    if depth < max_depth:
                        to_visit.append((absolute_url, depth + 1))

                    if len(all_urls) >= max_urls:
                        break

            except (requests.RequestException, Exception):
                continue

        return all_urls[:max_urls]

    def _extract_via_llm(self, source: DiscoveredSource, max_urls: int) -> list[ExtractedURL]:
        """Extract URLs using LLM suggestions.

        Args:
            source: DiscoveredSource to extract from
            max_urls: Maximum URLs to extract

        Returns:
            List of ExtractedURL objects from LLM

        Raises:
            LLMAPIError: On LLM API failures
        """
        prompt = f"""You are helping discover article URLs from an authoritative source.

Source: {source.domain} ({source.url})
Rationale: {source.rationale}

Suggest up to {max_urls} specific article URLs from this source that would be valuable for a knowledge base.

For each URL, provide:
1. Full URL
2. Article title (your best guess)
3. Why this article is valuable (rationale)

Focus on:
- Comprehensive overview articles
- Technical depth
- Recent content (prefer last 2 years)
- Canonical references

Return JSON with this exact structure:
{{
  "articles": [
    {{
      "url": "https://example.com/article",
      "title": "Article Title",
      "rationale": "Why valuable"
    }}
  ]
}}"""

        try:
            response = self._call_llm_with_retry(prompt)
            articles_data = json.loads(response)

            urls = []
            for article in articles_data["articles"]:
                urls.append(
                    ExtractedURL(
                        url=article["url"],
                        title=article["title"],
                        published_date=None,
                        extraction_method="llm",
                        authority_score=source.authority_score,
                        content_score=0.9,  # LLM-suggested URLs assumed high quality
                        rank_score=0.0,
                    )
                )

            return urls[:max_urls]

        except json.JSONDecodeError as e:
            raise LLMAPIError(f"Invalid JSON response from LLM: {e}") from e
        except Exception as e:
            raise LLMAPIError(f"LLM API error: {e}") from e

    # ========================================================================
    # Private Methods: Scoring and Validation
    # ========================================================================

    def _score_content(self, _url: str) -> float:
        """Score article content quality (0.0-1.0).

        Args:
            url: URL to score

        Returns:
            Content quality score
        """
        # Simplified content scoring (could be enhanced)
        # For now, return default score
        return 0.8

    def _score_recency(self, published_date: str | None) -> float:
        """Score recency based on publication date.

        Args:
            published_date: ISO format date string

        Returns:
            Recency score (0.0-1.0), 1.0 for recent, 0.0 for >2 years old
        """
        if not published_date:
            return 0.5  # Unknown date gets neutral score

        try:
            pub_date = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
            age_days = (datetime.now() - pub_date.replace(tzinfo=None)).days

            # Prefer articles within 2 years (730 days)
            if age_days < 0:
                return 1.0  # Future date (likely error, but give benefit)
            if age_days > 730:
                return 0.0  # Too old

            # Linear decay over 2 years
            return 1.0 - (age_days / 730.0)

        except (ValueError, AttributeError):
            return 0.5  # Parse error gets neutral score

    def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt.

        Args:
            url: URL to check

        Returns:
            True if URL is allowed, False if disallowed
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()

            return rp.can_fetch(self.user_agent, url)

        except Exception:
            # If robots.txt check fails, allow by default
            return True

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Call LLM with exponential backoff retry.

        Args:
            prompt: Prompt to send to LLM
            max_retries: Maximum number of retries

        Returns:
            LLM response text

        Raises:
            LLMAPIError: On API failures after retries
        """
        for attempt in range(max_retries):
            try:
                message = self.anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}],
                )

                return message.content[0].text

            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2**attempt
                    logger.warning(
                        f"LLM API error (attempt {attempt+1}), retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    raise LLMAPIError(f"LLM API failed after {max_retries} attempts: {e}") from e
