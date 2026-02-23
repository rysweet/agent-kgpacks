"""Generic web content source implementation.

Fetches and parses arbitrary web pages into the Article format,
enabling knowledge graph construction from any documentation site
(e.g., Microsoft Learn, MDN, ReadTheDocs).
"""

import ipaddress
import logging
import re
import socket
from urllib.parse import urljoin, urlparse

import requests

from .base import Article, ArticleNotFoundError

logger = logging.getLogger(__name__)


def _html_to_markdown(html_content: str) -> str:
    """Convert HTML to markdown-like plain text using stdlib html.parser.

    Uses the standard library HTMLParser for robust handling of nested tags,
    malformed HTML, and encoding issues — avoiding regex-based parsing pitfalls.
    """
    import html as html_mod
    from html.parser import HTMLParser

    class _MarkdownConverter(HTMLParser):
        def __init__(self):
            super().__init__()
            self.output: list[str] = []
            self._skip = False  # Inside script/style/nav/footer
            self._skip_tags = {"script", "style", "nav", "footer", "header"}
            self._skip_depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):  # noqa: ARG002
            if tag in self._skip_tags:
                self._skip = True
                self._skip_depth += 1
                return
            if self._skip:
                return
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(tag[1])
                self.output.append(f"\n{'#' * level} ")
            elif tag == "p":
                self.output.append("\n\n")
            elif tag == "li":
                self.output.append("\n- ")
            elif tag == "pre":
                self.output.append("\n```\n")
            elif tag == "code":
                self.output.append("`")
            elif tag == "br":
                self.output.append("\n")

        def handle_endtag(self, tag: str):
            if tag in self._skip_tags and self._skip_depth > 0:
                self._skip_depth -= 1
                if self._skip_depth == 0:
                    self._skip = False
                return
            if self._skip:
                return
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6") or tag == "p":
                self.output.append("\n")
            elif tag == "pre":
                self.output.append("\n```\n")
            elif tag == "code":
                self.output.append("`")

        def handle_data(self, data: str):
            if not self._skip:
                self.output.append(data)

        def handle_entityref(self, name: str):
            if not self._skip:
                self.output.append(html_mod.unescape(f"&{name};"))

        def handle_charref(self, name: str):
            if not self._skip:
                self.output.append(html_mod.unescape(f"&#{name};"))

    converter = _MarkdownConverter()
    converter.feed(html_content)
    text = "".join(converter.output)

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


def _extract_title(html_content: str, url: str) -> str:
    """Extract page title from HTML or fall back to URL path."""
    import html as html_mod

    match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.DOTALL)
    if match:
        title = html_mod.unescape(match.group(1).strip())
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


def _validate_url(url: str) -> None:
    """Validate URL to prevent SSRF attacks.

    Rejects:
    - Non-HTTP(S) schemes (file://, ftp://, etc.)
    - Private/reserved IP ranges (127.x, 10.x, 172.16-31.x, 192.168.x, 169.254.x)
    - IPv6 loopback (::1)
    - Cloud metadata endpoints (169.254.169.254)

    Raises:
        ValueError: If the URL is unsafe.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only HTTP(S) URLs are allowed, got scheme: {parsed.scheme!r}")

    if not parsed.hostname:
        raise ValueError(f"URL has no hostname: {url}")

    # Resolve hostname to IP and check against private ranges
    try:
        resolved_ips = socket.getaddrinfo(parsed.hostname, None)
        for _family, _type, _proto, _canonname, sockaddr in resolved_ips:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                raise ValueError(f"URL resolves to private/reserved IP {ip}: {url}")
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve hostname in URL {url}: {e}") from e


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

        # Validate URL to prevent SSRF attacks
        _validate_url(title_or_url)

        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)

        try:
            response = self._session.get(title_or_url, timeout=self._timeout, allow_redirects=False)
            self._last_request_time = time.time()

            if response.status_code == 404:
                raise ArticleNotFoundError(f"Page not found: {title_or_url}")
            response.raise_for_status()
        except requests.RequestException as e:
            raise ArticleNotFoundError(f"Failed to fetch {title_or_url}: {e}") from e

        # Use apparent encoding for non-UTF-8 pages (chardet-based detection)
        if response.encoding and response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
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
