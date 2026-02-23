"""Abstract content source protocol for WikiGR.

Defines the interface that all content sources (Wikipedia, web, etc.) must implement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Article:
    """Source-agnostic article representation.

    This is the common data structure returned by all ContentSource
    implementations. It replaces the Wikipedia-specific WikipediaArticle
    for new code paths while remaining compatible with existing pipeline code.
    """

    title: str
    content: str  # Raw text content (wikitext for Wikipedia, markdown for web)
    links: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    source_url: str = ""
    source_type: str = "unknown"  # "wikipedia", "web", etc.


class ArticleNotFoundError(Exception):
    """Raised when a content source cannot find the requested article."""


@runtime_checkable
class ContentSource(Protocol):
    """Protocol for pluggable content sources.

    Implementations must provide methods to fetch articles, parse them
    into sections, and extract outgoing links.
    """

    def fetch_article(self, title_or_url: str) -> Article:
        """Fetch an article by title (Wikipedia) or URL (web).

        Args:
            title_or_url: Article title for named sources, or full URL for web.

        Returns:
            Article with content, links, and categories populated.

        Raises:
            ArticleNotFoundError: If the article/URL cannot be fetched.
        """
        ...

    def parse_sections(self, content: str) -> list[dict]:
        """Parse article content into sections.

        Args:
            content: Raw article content (wikitext, markdown, HTML).

        Returns:
            List of dicts with keys: title, content, level.
        """
        ...

    def get_links(self, content: str) -> list[str]:
        """Extract outgoing links from article content.

        Args:
            content: Raw article content.

        Returns:
            List of link targets (titles for Wikipedia, URLs for web).
        """
        ...
