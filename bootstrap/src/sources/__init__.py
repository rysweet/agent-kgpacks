"""Pluggable content sources for WikiGR knowledge graph construction.

Provides an abstract ContentSource protocol and implementations for
Wikipedia and generic web content.
"""

from .base import Article, ArticleNotFoundError, ContentSource
from .web import WebContentSource
from .wikipedia_source import WikipediaContentSource

__all__ = [
    "Article",
    "ArticleNotFoundError",
    "ContentSource",
    "WebContentSource",
    "WikipediaContentSource",
]
