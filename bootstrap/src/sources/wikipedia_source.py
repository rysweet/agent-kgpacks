"""Wikipedia content source implementation.

Wraps the existing WikipediaAPIClient to implement the ContentSource protocol.
"""

import logging

from ..wikipedia import ArticleNotFoundError as WikiNotFoundError
from ..wikipedia import WikipediaAPIClient, WikipediaArticle
from ..wikipedia.parser import parse_sections
from .base import Article, ArticleNotFoundError

logger = logging.getLogger(__name__)


class WikipediaContentSource:
    """ContentSource implementation for Wikipedia articles.

    Wraps the existing WikipediaAPIClient, adapting WikipediaArticle
    to the common Article dataclass.
    """

    def __init__(self, client: WikipediaAPIClient | None = None):
        self._client = client or WikipediaAPIClient()

    def fetch_article(self, title_or_url: str) -> Article:
        """Fetch a Wikipedia article by title.

        Args:
            title_or_url: Wikipedia article title.

        Returns:
            Article with wikitext content, links, and categories.

        Raises:
            ArticleNotFoundError: If the article doesn't exist.
        """
        try:
            wiki_article: WikipediaArticle = self._client.fetch_article(title_or_url)
        except WikiNotFoundError as e:
            raise ArticleNotFoundError(str(e)) from e

        return Article(
            title=wiki_article.title,
            content=wiki_article.wikitext,
            links=wiki_article.links,
            categories=wiki_article.categories,
            source_url=f"https://en.wikipedia.org/wiki/{wiki_article.title.replace(' ', '_')}",
            source_type="wikipedia",
        )

    def parse_sections(self, content: str) -> list[dict]:
        """Parse wikitext into sections using the existing parser."""
        return parse_sections(content)

    def get_links(self, content: str) -> list[str]:
        """Extract wiki links from wikitext.

        Note: Links are already extracted during fetch_article() and stored
        in Article.links. This method provides an alternative for re-parsing.
        """
        import re

        links = []
        for match in re.finditer(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", content):
            link = match.group(1).strip()
            if not link.startswith(("File:", "Image:", "Category:", "Wikipedia:", "Help:")):
                links.append(link)
        return links
