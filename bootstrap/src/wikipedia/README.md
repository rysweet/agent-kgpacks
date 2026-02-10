# Wikipedia API Client Module

Self-contained module for fetching articles from Wikipedia's Action API.

## Module Contract

### Purpose
Fetch Wikipedia articles with complete wikitext, links, and categories using the Parse endpoint.

### Public Interface

```python
# Classes
WikipediaAPIClient  # Main API client
WikipediaArticle    # Data model for articles

# Exceptions
WikipediaAPIError       # Base exception
RateLimitError         # Rate limit violations
ArticleNotFoundError   # 404 errors
```

### Dependencies
- `requests` - HTTP client
- Standard library: `time`, `dataclasses`, `typing`, `urllib.parse`

## Usage

### Basic Fetching

```python
from wikipedia import WikipediaAPIClient

client = WikipediaAPIClient()
article = client.fetch_article("Python (programming language)")

print(article.title)        # "Python (programming language)"
print(len(article.wikitext)) # ~138000 chars
print(len(article.links))    # ~700+ links
print(len(article.categories)) # ~45 categories
print(article.pageid)        # 23862
```

### Batch Fetching

```python
titles = [
    "Python (programming language)",
    "Artificial Intelligence",
    "Machine Learning"
]

results = client.fetch_batch(titles, continue_on_error=True)

for title, article, error in results:
    if error:
        print(f"Failed: {title} - {error}")
    else:
        print(f"Success: {title} - {len(article.wikitext)} chars")
```

### With Caching

```python
client = WikipediaAPIClient(cache_enabled=True)

# First fetch - hits API
article1 = client.fetch_article("Python (programming language)")

# Second fetch - from cache (no API call)
article2 = client.fetch_article("Python (programming language)")

# Clear cache when needed
client.clear_cache()
```

### Error Handling

```python
from wikipedia import ArticleNotFoundError, WikipediaAPIError

try:
    article = client.fetch_article("Nonexistent Article")
except ArticleNotFoundError as e:
    print(f"Article not found: {e}")
except WikipediaAPIError as e:
    print(f"API error: {e}")
```

### Custom Configuration

```python
client = WikipediaAPIClient(
    cache_enabled=True,
    rate_limit_delay=0.2,  # 200ms between requests
    max_retries=5,         # More aggressive retries
    timeout=60             # Longer timeout
)
```

## Implementation Details

### Rate Limiting
- Default: 100ms delay between requests
- Enforced before each API call
- Respects Wikipedia's guidelines

### Retry Logic
- Exponential backoff: 2^retry * delay
- Default max retries: 3
- Triggers on: 429 (rate limit), 5xx (server errors), timeouts

### Error Handling
- **404**: Raises `ArticleNotFoundError`
- **429**: Retries with backoff, then raises `RateLimitError`
- **5xx**: Retries with backoff, then raises `WikipediaAPIError`
- **Timeout**: Retries, then raises `WikipediaAPIError`

### API Endpoint
```
https://en.wikipedia.org/w/api.php?action=parse&page={title}&prop=wikitext|links|categories&format=json
```

### Response Processing
- Extracts wikitext from `parse.wikitext.*`
- Filters links to namespace 0 (main articles only)
- Extracts all categories
- Preserves page ID for reference

## Data Model

### WikipediaArticle

```python
@dataclass
class WikipediaArticle:
    title: str              # Article title (may differ from requested)
    wikitext: str          # Raw wikitext content
    links: list[str]       # Links to other articles (namespace 0)
    categories: list[str]  # Article categories
    pageid: Optional[int]  # Wikipedia page ID
```

## Testing

Run built-in tests:

```bash
cd bootstrap
python src/wikipedia/api_client.py
```

Expected output:
- ✓ Fetch article successfully
- ✓ Handle 404 errors correctly
- ✓ Batch fetch with mixed success/failure

## Architecture Notes

### Self-Contained
- No external configuration files
- No database dependencies
- Can run standalone

### Regeneratable
- All behavior specified in this README
- No hidden state or side effects
- Can be rebuilt from specification

### Rate Limit Compliant
- Respects Wikipedia's crawl-delay guidelines
- Uses proper User-Agent header
- Implements exponential backoff

### Future Enhancements
The module structure supports future additions:
- Async/await for batch fetching
- Redis caching backend
- Language-specific endpoints
- Section-specific parsing

## Performance Characteristics

- **Single article**: ~200-300ms (including rate limit delay)
- **Batch (10 articles)**: ~2-3 seconds (sequential with rate limiting)
- **Cache hit**: <1ms
- **Memory**: ~1MB per 100KB wikitext article cached

## Notes

### Sequential Batch Fetching
The current implementation fetches articles sequentially to ensure rate limit compliance.

### Main Namespace Only
Links are filtered to namespace 0 (main articles). This excludes:
- Talk pages
- User pages
- Wikipedia meta pages
- File/Image pages

This ensures downstream consumers only see article-to-article links.

### Redirect Handling
Wikipedia's API automatically handles redirects. The returned `title` may differ from the requested title if a redirect occurred.

Example:
```python
article = client.fetch_article("USA")
# article.title == "United States"
```
