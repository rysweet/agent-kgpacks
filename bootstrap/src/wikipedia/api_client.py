"""Wikipedia API Client

Self-contained module for fetching articles from Wikipedia using the Parse endpoint.

Public Interface:
    - WikipediaAPIClient: Main client class
    - WikipediaArticle: Response data model
    - WikipediaAPIError: Exception for API errors
    - RateLimitError: Exception for rate limit violations

Example:
    >>> client = WikipediaAPIClient()
    >>> article = client.fetch_article("Machine Learning")
    >>> print(article.title)
    >>> print(len(article.wikitext))
"""

import time
from dataclasses import dataclass

import requests


@dataclass
class WikipediaArticle:
    """Structured representation of a Wikipedia article."""

    title: str
    wikitext: str
    links: list[str]
    categories: list[str]
    pageid: int | None = None


class WikipediaAPIError(Exception):
    """Base exception for Wikipedia API errors."""

    pass


class RateLimitError(WikipediaAPIError):
    """Exception raised when rate limit is violated."""

    pass


class ArticleNotFoundError(WikipediaAPIError):
    """Exception raised when article is not found."""

    pass


class WikipediaAPIClient:
    """Client for Wikipedia Action API (Parse endpoint).

    Implements:
        - Rate limiting (100ms between requests)
        - Retry logic with exponential backoff
        - Error handling for 404, 500, timeout
        - Sequential batch fetching

    Args:
        cache_enabled: Enable response caching (default: False)
        rate_limit_delay: Delay between requests in seconds (default: 0.1)
        max_retries: Maximum number of retry attempts (default: 3)
        timeout: Request timeout in seconds (default: 30)

    Example:
        >>> client = WikipediaAPIClient()
        >>> article = client.fetch_article("Python (programming language)")
        >>> print(article.title)
        >>> print(len(article.links))
    """

    BASE_URL = "https://en.wikipedia.org/w/api.php"
    USER_AGENT = "WikiGR/1.0 (Educational Project)"

    def __init__(
        self,
        cache_enabled: bool = False,
        rate_limit_delay: float = 0.1,
        max_retries: int = 3,
        timeout: int = 30,
    ):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
        self.cache_enabled = cache_enabled
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self.last_request_time = 0
        self._cache = {} if cache_enabled else None

    def _enforce_rate_limit(self):
        """Ensure minimum delay between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)

        self.last_request_time = time.time()

    def _make_request(self, params: dict, retry_count: int = 0) -> dict:
        """Make API request with retry logic.

        Args:
            params: Query parameters for the API
            retry_count: Current retry attempt number

        Returns:
            Parsed JSON response

        Raises:
            WikipediaAPIError: On unrecoverable errors
            RateLimitError: On rate limit violations
            ArticleNotFoundError: When article doesn't exist
        """
        self._enforce_rate_limit()

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)

            # Handle HTTP errors
            if response.status_code == 404:
                raise ArticleNotFoundError("Article not found")

            if response.status_code == 429:
                # Rate limited by Wikipedia
                if retry_count < self.max_retries:
                    backoff_delay = (2**retry_count) * self.rate_limit_delay
                    time.sleep(backoff_delay)
                    return self._make_request(params, retry_count + 1)
                raise RateLimitError("Rate limit exceeded after retries")

            if response.status_code >= 500:
                # Server error - retry with backoff
                if retry_count < self.max_retries:
                    backoff_delay = (2**retry_count) * 1.0  # Start with 1 second
                    time.sleep(backoff_delay)
                    return self._make_request(params, retry_count + 1)
                raise WikipediaAPIError(
                    f"Server error {response.status_code} after {self.max_retries} retries"
                )

            response.raise_for_status()
            return response.json()

        except requests.Timeout as e:
            if retry_count < self.max_retries:
                backoff_delay = (2**retry_count) * 1.0
                time.sleep(backoff_delay)
                return self._make_request(params, retry_count + 1)
            raise WikipediaAPIError(f"Request timeout after {self.max_retries} retries") from e

        except requests.RequestException as e:
            raise WikipediaAPIError(f"Request failed: {str(e)}") from e

    def fetch_article(self, title: str) -> WikipediaArticle:
        """Fetch a single article from Wikipedia.

        Args:
            title: Wikipedia article title

        Returns:
            WikipediaArticle with title, wikitext, links, and categories

        Raises:
            ArticleNotFoundError: If article doesn't exist
            WikipediaAPIError: On API errors

        Example:
            >>> client = WikipediaAPIClient()
            >>> article = client.fetch_article("Python (programming language)")
            >>> assert article.title == "Python (programming language)"
            >>> assert len(article.wikitext) > 0
            >>> assert len(article.links) > 0
        """
        # Check cache
        if self._cache is not None and title in self._cache:
            return self._cache[title]

        params = {
            "action": "parse",
            "page": title,
            "prop": "wikitext|links|categories",
            "format": "json",
        }

        data = self._make_request(params)

        # Check for API-level errors
        if "error" in data:
            error_info = data["error"]
            if error_info.get("code") == "missingtitle":
                raise ArticleNotFoundError(f"Article '{title}' not found")
            raise WikipediaAPIError(f"API error: {error_info.get('info', 'Unknown error')}")

        if "parse" not in data:
            raise WikipediaAPIError("Unexpected API response format")

        parse_data = data["parse"]

        # Extract wikitext
        wikitext = parse_data.get("wikitext", {}).get("*", "")

        # Extract links (only namespace 0 - main articles)
        links = [
            link["*"]
            for link in parse_data.get("links", [])
            if link.get("ns") == 0  # Main namespace only
        ]

        # Extract categories
        categories = [cat["*"] for cat in parse_data.get("categories", [])]

        article = WikipediaArticle(
            title=parse_data.get("title", title),
            wikitext=wikitext,
            links=links,
            categories=categories,
            pageid=parse_data.get("pageid"),
        )

        # Cache if enabled
        if self._cache is not None:
            self._cache[title] = article

        return article

    def fetch_batch(
        self, titles: list[str], continue_on_error: bool = True
    ) -> list[tuple[str, WikipediaArticle | None, Exception | None]]:
        """Fetch multiple articles sequentially with rate limiting.

        Args:
            titles: List of article titles to fetch
            continue_on_error: Continue fetching if one article fails

        Returns:
            List of tuples: (title, article_or_none, error_or_none)

        Example:
            >>> client = WikipediaAPIClient()
            >>> results = client.fetch_batch(["Python", "Machine Learning"])
            >>> successful = [(t, a) for t, a, e in results if e is None]
            >>> print(f"Fetched {len(successful)} articles")
        """
        results = []

        for title in titles:
            try:
                article = self.fetch_article(title)
                results.append((title, article, None))
            except Exception as e:
                results.append((title, None, e))
                if not continue_on_error:
                    break

        return results

    def clear_cache(self):
        """Clear the response cache."""
        if self._cache is not None:
            self._cache.clear()


# Simple test/example usage
if __name__ == "__main__":
    print("Testing Wikipedia API Client\n")

    client = WikipediaAPIClient()

    # Test 1: Fetch single article
    print("Test 1: Fetching 'Python (programming language)' article...")
    try:
        article = client.fetch_article("Python (programming language)")
        print(f"✓ Title: {article.title}")
        print(f"✓ Wikitext length: {len(article.wikitext)} chars")
        print(f"✓ Links: {len(article.links)} links")
        print(f"✓ Categories: {len(article.categories)} categories")
        print(f"✓ Page ID: {article.pageid}")

        # Validate structure
        assert article.title, "Title should not be empty"
        assert len(article.wikitext) > 1000, "Wikitext should be substantial"
        assert len(article.links) > 10, "Should have multiple links"
        assert len(article.categories) > 0, "Should have categories"

        print("\n✓ All validations passed!\n")

    except Exception as e:
        print(f"✗ Error: {e}\n")

    # Test 2: Test error handling
    print("Test 2: Testing error handling with non-existent article...")
    try:
        article = client.fetch_article("This Article Definitely Does Not Exist 12345")
        print("✗ Should have raised ArticleNotFoundError")
    except ArticleNotFoundError as e:
        print(f"✓ Correctly raised ArticleNotFoundError: {e}\n")
    except Exception as e:
        print(f"✗ Unexpected error: {e}\n")

    # Test 3: Batch fetching
    print("Test 3: Batch fetching articles...")
    titles = ["Python (programming language)", "Artificial Intelligence", "Invalid Article XYZ"]
    results = client.fetch_batch(titles)

    successful = [(t, a) for t, a, e in results if e is None]
    failed = [(t, e) for t, a, e in results if e is not None]

    print(f"✓ Fetched {len(successful)}/{len(titles)} articles successfully")
    for title, article in successful:
        print(f"  - {title}: {len(article.wikitext)} chars")

    if failed:
        print(f"✓ Failed articles: {len(failed)}")
        for title, error in failed:
            print(f"  - {title}: {type(error).__name__}")

    print("\n✓ All tests completed!")
