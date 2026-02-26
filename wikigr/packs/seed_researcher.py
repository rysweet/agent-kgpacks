"""
LLM-based seed researcher for automatic source discovery.

Uses Claude Opus 4.6 to discover authoritative sources for a domain,
extract article URLs using multiple strategies (sitemap, RSS, crawling, LLM),
validate accessibility, and rank by authority/recency/content.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urljoin, urlparse

import requests
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSource:
    """Represents a discovered authoritative source for a domain.

    Attributes:
        url: Base URL of the source
        authority_score: Authority score (0.0-1.0, higher is more authoritative)
        content_type: Type of content (official_docs, blog, tutorial, reference, news)
        estimated_articles: Estimated number of relevant articles
        description: Brief description of what the source contains
    """

    url: str
    authority_score: float
    content_type: Literal["official_docs", "blog", "tutorial", "reference", "news"]
    estimated_articles: int
    description: str


class LLMSeedResearcher:
    """LLM-based researcher for discovering and extracting authoritative sources.

    Uses Claude Opus 4.6 to intelligently discover sources, extract URLs,
    and rank content for knowledge pack creation.

    Args:
        anthropic_api_key: API key for Claude (or uses ANTHROPIC_API_KEY env var)
        model: Claude model to use (default: claude-opus-4-6-20250826)
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retries for HTTP requests

    Example:
        >>> researcher = LLMSeedResearcher()
        >>> sources = researcher.discover_sources(".NET programming")
        >>> print(f"Found {len(sources)} authoritative sources")
        >>> urls = researcher.extract_article_urls(sources[0].url, max_urls=50)
        >>> print(f"Extracted {len(urls)} article URLs")
    """

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        model: str = "claude-opus-4-6-20250826",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.claude = Anthropic(api_key=anthropic_api_key)
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def discover_sources(self, domain: str, max_sources: int = 10) -> list[DiscoveredSource]:
        """Discover top authoritative sources for a given domain using Claude.

        Uses Claude Opus 4.6 to identify high-quality, authoritative sources
        that would make good seed material for knowledge packs.

        Args:
            domain: Domain/topic to research (e.g., ".NET programming", "Rust language")
            max_sources: Maximum number of sources to return

        Returns:
            List of DiscoveredSource objects, sorted by authority_score descending

        Raises:
            ValueError: If domain is empty or Claude returns invalid JSON
            requests.exceptions.RequestException: If API call fails
        """
        if not domain or not domain.strip():
            raise ValueError("Domain cannot be empty")

        logger.info(f"Discovering authoritative sources for domain: {domain}")

        prompt = f"""You are a research assistant helping to build a knowledge graph. Find the top {max_sources} most authoritative sources for learning about "{domain}".

CRITICAL REQUIREMENTS:
1. Prioritize official documentation and authoritative sources
2. Return sources that are publicly accessible (no paywalls)
3. Focus on technical depth and accuracy
4. Prefer sources with many high-quality articles

AUTHORITY HIERARCHY (highest to lowest):
- Official documentation: 0.9-1.0
- Official blogs/sites: 0.7-0.9
- Well-known technical sites: 0.6-0.8
- Community blogs (established): 0.4-0.6
- News sites: 0.3-0.5

OUTPUT FORMAT:
Return ONLY valid JSON (no markdown, no explanations) as an array of objects:
[
  {{
    "url": "https://example.com",
    "authority_score": 0.95,
    "content_type": "official_docs",
    "estimated_articles": 500,
    "description": "Official documentation site"
  }}
]

Valid content_type values: official_docs, blog, tutorial, reference, news

Find {max_sources} sources for "{domain}"."""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text.strip()

            # Remove markdown code blocks if present
            content = re.sub(r"```json\s*", "", content)
            content = re.sub(r"```\s*$", "", content)

            sources_data = json.loads(content)

            if not isinstance(sources_data, list):
                raise ValueError("Expected JSON array of sources")

            sources = []
            for item in sources_data[:max_sources]:
                # Validate required fields
                if not all(k in item for k in ["url", "authority_score", "content_type"]):
                    logger.warning(f"Skipping source with missing fields: {item}")
                    continue

                # Validate content_type
                valid_types = {"official_docs", "blog", "tutorial", "reference", "news"}
                if item["content_type"] not in valid_types:
                    logger.warning(f"Invalid content_type: {item['content_type']}, skipping")
                    continue

                sources.append(
                    DiscoveredSource(
                        url=item["url"],
                        authority_score=float(item["authority_score"]),
                        content_type=item["content_type"],
                        estimated_articles=int(item.get("estimated_articles", 100)),
                        description=item.get("description", ""),
                    )
                )

            # Sort by authority score descending
            sources.sort(key=lambda s: s.authority_score, reverse=True)

            logger.info(f"Discovered {len(sources)} authoritative sources")
            return sources

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Response content: {content}")
            raise ValueError(f"Invalid JSON response from Claude: {e}") from e
        except Exception as e:
            logger.error(f"Error discovering sources: {e}")
            raise

    def extract_article_urls(
        self,
        base_url: str,
        max_urls: int = 100,
        strategies: list[str] | None = None,
    ) -> list[str]:
        """Extract article URLs from a source using multiple strategies.

        Tries strategies in order: sitemap.xml, RSS/Atom feeds, index page crawl,
        and LLM-based URL generation as fallback.

        Args:
            base_url: Base URL of the source
            max_urls: Maximum number of URLs to return
            strategies: List of strategies to try (default: all)
                       Options: "sitemap", "rss", "index", "llm"

        Returns:
            List of article URLs (deduplicated)

        Raises:
            ValueError: If base_url is invalid
        """
        if not base_url or not base_url.strip():
            raise ValueError("Base URL cannot be empty")

        if strategies is None:
            strategies = ["sitemap", "rss", "index", "llm"]

        logger.info(f"Extracting URLs from {base_url} using strategies: {strategies}")

        all_urls: set[str] = set()

        for strategy in strategies:
            if len(all_urls) >= max_urls:
                break

            try:
                if strategy == "sitemap":
                    urls = self._extract_from_sitemap(base_url)
                elif strategy == "rss":
                    urls = self._extract_from_rss(base_url)
                elif strategy == "index":
                    urls = self._extract_from_index(base_url)
                elif strategy == "llm":
                    urls = self._extract_with_llm(base_url, max_urls - len(all_urls))
                else:
                    logger.warning(f"Unknown strategy: {strategy}")
                    continue

                all_urls.update(urls)
                logger.info(f"Strategy '{strategy}' found {len(urls)} URLs")

            except Exception as e:
                logger.warning(f"Strategy '{strategy}' failed: {e}")
                continue

        result = list(all_urls)[:max_urls]
        logger.info(f"Extracted {len(result)} total URLs")
        return result

    def _extract_from_sitemap(self, base_url: str) -> list[str]:
        """Extract URLs from sitemap.xml."""
        sitemap_urls = [
            urljoin(base_url, "sitemap.xml"),
            urljoin(base_url, "sitemap_index.xml"),
            urljoin(base_url, "sitemap-index.xml"),
        ]

        urls = []
        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=self.timeout)
                if response.status_code == 200:
                    # Simple regex extraction (good enough for most sitemaps)
                    urls.extend(re.findall(r"<loc>(https?://[^<]+)</loc>", response.text))
                    if urls:
                        break
            except Exception as e:
                logger.debug(f"Failed to fetch {sitemap_url}: {e}")
                continue

        return urls

    def _extract_from_rss(self, base_url: str) -> list[str]:
        """Extract URLs from RSS/Atom feeds."""
        feed_paths = ["/feed", "/rss", "/atom", "/feed.xml", "/rss.xml", "/atom.xml"]

        urls = []
        for path in feed_paths:
            try:
                feed_url = urljoin(base_url, path)
                response = requests.get(feed_url, timeout=self.timeout)
                if response.status_code == 200:
                    # Extract links from RSS/Atom
                    urls.extend(re.findall(r"<link[^>]*>(https?://[^<]+)</link>", response.text))
                    urls.extend(re.findall(r'<link[^>]+href="(https?://[^"]+)"', response.text))
                    if urls:
                        break
            except Exception as e:
                logger.debug(f"Failed to fetch feed {path}: {e}")
                continue

        return urls

    def _extract_from_index(self, base_url: str) -> list[str]:
        """Extract URLs by crawling the index page."""
        try:
            response = requests.get(base_url, timeout=self.timeout)
            if response.status_code == 200:
                # Extract all absolute URLs from the page
                domain = urlparse(base_url).netloc
                urls = re.findall(r'href="(https?://[^"]+)"', response.text)

                # Filter to same domain only
                same_domain_urls = [url for url in urls if domain in urlparse(url).netloc]

                return same_domain_urls
        except Exception as e:
            logger.debug(f"Failed to crawl index page: {e}")

        return []

    def _extract_with_llm(self, base_url: str, max_urls: int) -> list[str]:
        """Use LLM to generate potential article URLs based on common patterns."""
        logger.info(f"Using LLM to generate URLs for {base_url}")

        prompt = f"""Generate {max_urls} likely article URLs for the website: {base_url}

Based on common URL patterns for documentation and blog sites, generate realistic URLs that likely exist.

RULES:
1. Use patterns like: /docs/, /blog/, /tutorial/, /guide/, /article/
2. Include realistic slugs (e.g., /getting-started, /advanced-concepts)
3. Return ONLY valid URLs (one per line, no explanations)
4. URLs must start with {base_url}

Generate {max_urls} URLs:"""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text.strip()
            urls = [line.strip() for line in content.split("\n") if line.strip().startswith("http")]

            return urls[:max_urls]

        except Exception as e:
            logger.error(f"LLM URL generation failed: {e}")
            return []

    def validate_url(self, url: str) -> tuple[bool, dict]:
        """Validate that a URL is accessible and contains substantial content.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, metadata) where metadata contains:
                - status_code: HTTP status code
                - content_length: Content length in bytes
                - content_type: Content type header
                - word_count: Estimated word count
                - is_html: Whether content is HTML
                - error: Error message if validation failed
        """
        if not url or not url.strip():
            return False, {"error": "Empty URL"}

        metadata = {
            "status_code": None,
            "content_length": 0,
            "content_type": "",
            "word_count": 0,
            "is_html": False,
            "error": None,
        }

        try:
            response = requests.head(url, timeout=self.timeout, allow_redirects=True)
            metadata["status_code"] = response.status_code

            if response.status_code != 200:
                metadata["error"] = f"HTTP {response.status_code}"
                return False, metadata

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            metadata["content_type"] = content_type
            metadata["is_html"] = "html" in content_type

            # Get content for analysis
            response = requests.get(url, timeout=self.timeout)
            content = response.text
            metadata["content_length"] = len(content)

            # Estimate word count (rough approximation)
            words = re.findall(r"\b\w+\b", content)
            metadata["word_count"] = len(words)

            # Validation rules
            if not metadata["is_html"]:
                metadata["error"] = "Not HTML content"
                return False, metadata

            if metadata["word_count"] < 100:
                metadata["error"] = "Content too short"
                return False, metadata

            return True, metadata

        except requests.exceptions.Timeout:
            metadata["error"] = "Request timeout"
            return False, metadata
        except requests.exceptions.RequestException as e:
            metadata["error"] = str(e)
            return False, metadata
        except Exception as e:
            metadata["error"] = f"Unexpected error: {e}"
            return False, metadata

    def rank_urls(
        self,
        urls: list[str],
        authority_score: float = 0.5,
        metadata_list: list[dict] | None = None,
    ) -> list[tuple[str, float]]:
        """Rank URLs by authority, recency, and content length.

        Args:
            urls: List of URLs to rank
            authority_score: Base authority score for the source (0.0-1.0)
            metadata_list: Optional list of metadata dicts from validate_url()

        Returns:
            List of (url, score) tuples, sorted by score descending
        """
        if not urls:
            return []

        ranked = []

        for i, url in enumerate(urls):
            metadata = metadata_list[i] if metadata_list else {}

            # Base score from authority
            score = authority_score

            # Boost for content length (normalize to 0-0.2)
            word_count = metadata.get("word_count", 1000)
            length_boost = min(word_count / 5000, 0.2)
            score += length_boost

            # Boost for URL patterns indicating quality content
            if "/docs/" in url or "/documentation/" in url:
                score += 0.15
            elif "/tutorial/" in url or "/guide/" in url:
                score += 0.10
            elif "/blog/" in url or "/article/" in url:
                score += 0.05

            # Penalty for very long URLs (likely auto-generated)
            if len(url) > 200:
                score -= 0.1

            # Check for recency hints in URL (e.g., /2024/, /2025/, /2026/)
            current_year = datetime.now().year
            for year in [current_year, current_year - 1]:
                if f"/{year}/" in url or f"-{year}-" in url:
                    score += 0.08
                    break

            ranked.append((url, max(0.0, min(1.0, score))))  # Clamp to [0,1]

        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked
