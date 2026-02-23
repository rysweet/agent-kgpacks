"""Generic web content source implementation.

Fetches and parses arbitrary web pages into the Article format,
enabling knowledge graph construction from any documentation site
(e.g., Microsoft Learn, MDN, ReadTheDocs).
"""

import logging
import re
from urllib.parse import urljoin, urlparse

import requests

from .base import Article, ArticleNotFoundError, ContentSource

logger = logging.getLogger(__name__)


def _html_to_markdown(html: str) -> str:
    """Convert HTML to markdown-like plain text.

    Simple converter that handles common HTML elements without
    requiring heavy dependencies like html2text or markdownify.
    """
    import html as html_mod

    text = html

    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL)

    # Convert headings to markdown
    for level in range(1, 7):
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, lv=level: f"\n{'#' * lv} {m.group(1).strip()}\n",
            text,
            flags=re.DOTALL,
        )

    # Convert paragraphs to double newlines
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL)

    # Convert list items
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL)

    # Convert links: <a href="url">text</a> -> text
    text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", text, flags=re.DOTALL)

    # Convert code blocks
    text = re.sub(r"<pre[^>]*>(.*?)</pre>", r"```\n\1\n```\n", text, flags=re.DOTALL)
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = html_mod.unescape(text)

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract absolute URLs from HTML anchor tags."""
    links = []
    for match in re.finditer(r'<a[^>]+href="([^"]*)"', html):
        href = match.group(1)
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        absolute = urljoin(base_url, href)
        # Only include links from the same domain
        if urlparse(absolute).netloc == urlparse(base_url).netloc:
            links.append(absolute)
    return list(dict.fromkeys(links))  # Dedupe preserving order


def _extract_title(html: str, url: str) -> str:
    """Extract page title from HTML or fall back to URL path."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
    if match:
        title = match.group(1).strip()
        # Clean common suffixes like " | Microsoft Learn"
        title = re.split(r"\s*[|–—]\s*", title)[0].strip()
        if title:
            return title
    # Fall back to URL path
    path = urlparse(url).path.rstrip("/").split("/")[-1]
    return path.replace("-", " ").replace("_", " ").title()


def _infer_categories(url: str) -> list[str]:
    """Infer categories from URL path segments and content."""
    categories = []
    path = urlparse(url).path.strip("/")
    segments = [s for s in path.split("/") if s and len(s) > 2]
    # Use path segments as categories (e.g., /azure/kubernetes/ -> ["azure", "kubernetes"])
    for seg in segments[:3]:
        clean = seg.replace("-", " ").replace("_", " ").title()
        if clean.lower() not in ("en", "us", "docs", "index", "learn"):
            categories.append(clean)
    return categories


class WebContentSource:
    """ContentSource implementation for generic web pages.

    Fetches HTML from any URL, converts to markdown-like text, and
    extracts sections, links, and categories. Works with documentation
    sites like Microsoft Learn, MDN, ReadTheDocs, etc.
    """

    def __init__(
        self,
        user_agent: str = "WikiGR/1.0 (Knowledge Graph Builder)",
        timeout: int = 30,
        rate_limit_delay: float = 0.5,
    ):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self._timeout = timeout
        self._rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

    def fetch_article(self, title_or_url: str) -> Article:
        """Fetch a web page by URL.

        Args:
            title_or_url: Full URL to fetch.

        Returns:
            Article with markdown content, links, and inferred categories.

        Raises:
            ArticleNotFoundError: If the URL returns 404 or fails.
        """
        import time

        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)

        try:
            response = self._session.get(title_or_url, timeout=self._timeout)
            self._last_request_time = time.time()

            if response.status_code == 404:
                raise ArticleNotFoundError(f"Page not found: {title_or_url}")
            response.raise_for_status()
        except requests.RequestException as e:
            raise ArticleNotFoundError(f"Failed to fetch {title_or_url}: {e}") from e

        html = response.text
        title = _extract_title(html, title_or_url)
        markdown = _html_to_markdown(html)
        links = _extract_links(html, title_or_url)
        categories = _infer_categories(title_or_url)

        logger.info(f"Fetched web page: {title} ({len(markdown)} chars, {len(links)} links)")

        return Article(
            title=title,
            content=markdown,
            links=links,
            categories=categories,
            source_url=title_or_url,
            source_type="web",
        )

    def parse_sections(self, content: str) -> list[dict]:
        """Parse markdown-like content into sections by headings."""
        sections: list[dict] = []
        current_title = ""
        current_level = 0
        current_lines: list[str] = []

        for line in content.split("\n"):
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Save previous section
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text and len(text) > 20:
                        sections.append(
                            {
                                "title": current_title or "Introduction",
                                "content": text,
                                "level": current_level or 2,
                            }
                        )
                current_level = len(heading_match.group(1))
                current_title = heading_match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        if current_lines:
            text = "\n".join(current_lines).strip()
            if text and len(text) > 20:
                sections.append(
                    {
                        "title": current_title or "Introduction",
                        "content": text,
                        "level": current_level or 2,
                    }
                )

        return sections

    def get_links(self, content: str) -> list[str]:
        """Extract URLs from markdown-like content.

        Note: Links are already extracted during fetch_article(). This
        method re-extracts from the converted markdown text.
        """
        links = []
        for match in re.finditer(r"https?://[^\s<>\"')\]]+", content):
            links.append(match.group(0))
        return list(dict.fromkeys(links))


# Verify protocol compliance
assert isinstance(WebContentSource(), ContentSource)
