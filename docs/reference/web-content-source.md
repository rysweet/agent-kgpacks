# Web Content Source API Reference

Complete reference for `WebContentSource` class and related interfaces.

## WebContentSource

Implementation of `ContentSource` protocol for web-based knowledge graph creation.

### Class Definition

```python
from backend.sources.web_content_source import WebContentSource

class WebContentSource(ContentSource):
    """
    Content source for web URLs with LLM extraction and BFS link expansion.

    Provides feature parity with WikipediaContentSource:
    - LLM entity and relationship extraction
    - BFS link crawling with configurable depth
    - Incremental updates with URL deduplication
    - Shared ArticleProcessor for consistent extraction
    """
```

### Constructor

```python
def __init__(
    self,
    url: str,
    max_depth: int = 0,
    max_links: int = 1,
    same_domain_only: bool = True,
    include_pattern: Optional[str] = None,
    exclude_pattern: Optional[str] = None
)
```

**Parameters:**

- `url` (str, required): Starting URL for content extraction
- `max_depth` (int, default: 0): Maximum BFS depth for link expansion (0 = no expansion)
- `max_links` (int, default: 1): Maximum total pages to process
- `same_domain_only` (bool, default: True): Only follow links within same domain
- `include_pattern` (Optional[str], default: None): Regex pattern - only follow matching URLs
- `exclude_pattern` (Optional[str], default: None): Regex pattern - skip matching URLs

**Example:**

```python
source = WebContentSource(
    url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks",
    max_depth=2,
    max_links=50,
    same_domain_only=True,
    include_pattern=r"/azure/aks/",
    exclude_pattern=r"/api-reference/"
)
```

### Methods

#### get_articles()

```python
def get_articles(self) -> Generator[Article, None, None]:
    """
    Yields Article objects from web content.

    Yields:
        Article: Each discovered web page as an Article with:
            - title: Extracted from <title> or <h1> tag
            - content: Main text content (HTML stripped)
            - url: Full URL of the page
            - links: Discovered links for BFS expansion

    Raises:
        ValueError: If URL is invalid or unreachable
        requests.HTTPError: If HTTP request fails

    Example:
        >>> source = WebContentSource(url="https://example.com")
        >>> for article in source.get_articles():
        ...     print(f"{article.title}: {len(article.content)} chars")
        Example Page: 1234 chars
    """
```

#### expand_links()

```python
def expand_links(self, root_url: str, links: List[str], depth: int) -> List[str]:
    """
    Expand links using BFS with filtering.

    Args:
        root_url: Starting URL (for domain checking)
        links: List of discovered links from current page
        depth: Current depth in BFS traversal

    Returns:
        List of filtered URLs to process at next depth level

    Filtering applied:
        1. Same domain check (if same_domain_only=True)
        2. Include pattern match (if include_pattern set)
        3. Exclude pattern rejection (if exclude_pattern set)
        4. Duplicate removal (already visited)
        5. Max links enforcement

    Example:
        >>> source = WebContentSource(
        ...     url="https://example.com",
        ...     same_domain_only=True,
        ...     exclude_pattern=r"/admin/"
        ... )
        >>> links = [
        ...     "https://example.com/about",
        ...     "https://example.com/admin/settings",
        ...     "https://other.com/page"
        ... ]
        >>> filtered = source.expand_links("https://example.com", links, 1)
        >>> print(filtered)
        ['https://example.com/about']
    """
```

## Command-Line Interface

### wikigr create --source=web

Create a knowledge graph from web content.

```bash
wikigr create --source=web [OPTIONS]
```

**Required Options:**

- `--url URL`: Starting URL for content extraction
- `--db-path PATH`: Output database file path

**Optional Options:**

- `--max-depth INT`: BFS depth (default: 0, no expansion)
- `--max-links INT`: Maximum pages to process (default: 1)
- `--same-domain-only`: Only follow same-domain links (default: enabled)
- `--include-pattern REGEX`: Only follow URLs matching pattern
- `--exclude-pattern REGEX`: Skip URLs matching pattern
- `--max-entities INT`: Maximum entities per page (default: 50)
- `--no-relationships`: Skip relationship extraction (faster)

**Examples:**

```bash
# Single page
wikigr create \
  --source=web \
  --url="https://example.com/article" \
  --db-path=output.db

# Crawl with depth 2, max 25 pages
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/intro" \
  --max-depth=2 \
  --max-links=25 \
  --db-path=azure_aks.db

# Filter by URL pattern
wikigr create \
  --source=web \
  --url="https://docs.python.org/3/library/" \
  --max-depth=1 \
  --include-pattern="/library/" \
  --exclude-pattern="/genindex" \
  --db-path=python_stdlib.db
```

**Exit Codes:**

- `0`: Success
- `1`: Invalid URL or unreachable
- `2`: Database error
- `3`: LLM extraction failure

### wikigr update --source=web

Update existing knowledge graph with new web content.

```bash
wikigr update --source=web [OPTIONS]
```

**Required Options:**

- `--url URL`: URL to add/update
- `--db-path PATH`: Existing database file path

**Optional Options:**

Same as `wikigr create --source=web` (excluding `--db-path` which must exist)

**Behavior:**

1. Checks if URL already exists in database
2. Skips if content hash matches (no changes)
3. Updates if content changed
4. Adds new entities and relationships
5. Preserves existing graph structure

**Example:**

```bash
# Add single page to existing graph
wikigr update \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/best-practices" \
  --db-path=azure_aks.db

# Add multiple pages with crawling
wikigr update \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/security-overview" \
  --max-depth=1 \
  --max-links=10 \
  --db-path=azure_aks.db
```

**Exit Codes:**

- `0`: Success (updated or skipped if unchanged)
- `1`: Database not found
- `2`: URL unreachable
- `3`: Update failed (database corruption)

## Article Data Model

Web content is represented using the shared `Article` model.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class Article:
    """
    Represents a single web page for processing.

    Attributes:
        title: Page title (from <title> or <h1>)
        content: Main text content (HTML stripped)
        url: Full URL of the page
        links: Discovered hyperlinks for BFS expansion
    """
    title: str
    content: str
    url: str
    links: List[str]
```

**Example:**

```python
article = Article(
    title="What is Azure Kubernetes Service?",
    content="Azure Kubernetes Service (AKS) is a managed container orchestration...",
    url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks",
    links=[
        "https://learn.microsoft.com/en-us/azure/aks/concepts-clusters-workloads",
        "https://learn.microsoft.com/en-us/azure/aks/tutorial-kubernetes-prepare-app"
    ]
)
```

## ContentSource Protocol

`WebContentSource` implements the `ContentSource` protocol for consistent interface.

```python
from typing import Protocol, Generator

class ContentSource(Protocol):
    """
    Protocol for content sources (Wikipedia, web, local files, etc.).

    All sources must implement get_articles() to yield Article objects.
    """

    def get_articles(self) -> Generator[Article, None, None]:
        """
        Yields Article objects from the content source.

        Yields:
            Article: Content with title, body, URL, and links
        """
        ...
```

**Implementations:**

- `WikipediaContentSource` - Wikipedia articles via API
- `WebContentSource` - Web pages via HTTP
- *(Future)* `LocalFileSource` - Local markdown/HTML files
- *(Future)* `GitHubWikiSource` - GitHub wiki pages

## Integration with ArticleProcessor

`WebContentSource` uses the shared `ArticleProcessor` for entity extraction.

```python
from backend.kg_construction.article_processor import ArticleProcessor

processor = ArticleProcessor(conn, use_llm=True)

for article in web_source.get_articles():
    processor.process_article(
        title=article.title,
        content=article.content,
        url=article.url
    )
```

**Shared behavior across all sources:**

- Same LLM extraction pipeline
- Same entity normalization
- Same relationship identification
- Same vector embedding generation

See [ArticleProcessor API Reference](./article-processor.md) for details.

## Environment Variables

Configure LLM extraction behavior:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | None |
| `OPENAI_MODEL` | Model for extraction | `gpt-4-turbo-preview` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.0` |
| `LLM_MAX_RETRIES` | Retry attempts on failure | `3` |
| `LLM_RETRY_DELAY` | Seconds between retries | `1.0` |

**Example:**

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-3.5-turbo
export LLM_TEMPERATURE=0.0
wikigr create --source=web --url="..." --db-path=output.db
```

## Error Handling

### Common Exceptions

```python
# Invalid URL
try:
    source = WebContentSource(url="not-a-valid-url")
except ValueError as e:
    print(f"Invalid URL: {e}")

# Unreachable URL
try:
    for article in source.get_articles():
        pass
except requests.HTTPError as e:
    print(f"HTTP error: {e}")

# LLM extraction failure
try:
    processor.process_article(title, content, url)
except openai.error.RateLimitError as e:
    print(f"Rate limit: {e}")
```

### Graceful Degradation

If LLM extraction fails:
1. Retries up to `LLM_MAX_RETRIES` times
2. Logs error and continues to next article
3. Partial graph created from successful extractions

## Performance Characteristics

### Time Complexity

- Single page: O(1) HTTP request + O(n) LLM extraction (n = content length)
- BFS crawling: O(d × l) where d = depth, l = links per page
- Total: O(d × l × n) for full crawl with extraction

### Space Complexity

- Memory: O(l) for link queue + O(n) for article content
- Database: O(e + r) where e = entities, r = relationships

### Benchmarks

Measured on Azure AKS documentation:

| Operation | Pages | Entities | Relationships | Time | Cost |
|-----------|-------|----------|---------------|------|------|
| Single page | 1 | 42 | 28 | 3.2s | $0.02 |
| Depth 1 (10 pages) | 10 | 312 | 187 | 28s | $0.15 |
| Depth 2 (50 pages) | 50 | 1,456 | 892 | 2m 14s | $0.68 |

*Using GPT-4-turbo-preview, temperatures 0.0*

## Related Documentation

- [Getting Started with Web Sources](../tutorials/web-sources-getting-started.md)
- [How to Configure LLM Extraction](../howto/configure-llm-extraction.md)
- [How to Filter Link Crawling](../howto/filter-link-crawling.md)
- [ArticleProcessor API Reference](./article-processor.md)
- [Understanding ContentSource Architecture](../concepts/content-source-design.md)
