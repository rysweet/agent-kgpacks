"""Wikipedia API module for WikiGR.

Public interface for fetching and parsing Wikipedia articles.
"""

from .api_client import (
    ArticleNotFoundError,
    RateLimitError,
    WikipediaAPIClient,
    WikipediaAPIError,
    WikipediaArticle,
)
from .parser import parse_sections, strip_wikitext

__all__ = [
    "WikipediaAPIClient",
    "WikipediaArticle",
    "WikipediaAPIError",
    "RateLimitError",
    "ArticleNotFoundError",
    "parse_sections",
    "strip_wikitext",
]
