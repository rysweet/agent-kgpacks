# ContentSource Architecture

Understanding how WikiGR achieves source-agnostic knowledge graph construction.

## The Problem

Building knowledge graphs from different content sources (Wikipedia, web pages, local files) requires handling:

- Different data formats (API responses, HTML, markdown)
- Different link structures (wiki links vs URLs vs file paths)
- Different metadata (page IDs vs URLs vs file paths)

Traditional approaches tightly couple extraction logic to each source, leading to code duplication and inconsistent extraction quality.

## The Solution: ContentSource Protocol

WikiGR uses a protocol-based architecture that separates **content acquisition** from **content processing**.

### ContentSource Protocol

```python
from typing import Protocol, Generator

class ContentSource(Protocol):
    """
    Protocol for content sources.

    Any object implementing get_articles() can be used as a content source.
    """
    def get_articles(self) -> Generator[Article, None, None]:
        """Yields Article objects from the source."""
        ...
```

**Key insight:** All content sources produce the same output type (`Article`), regardless of input format.

### Article: The Universal Data Model

```python
@dataclass
class Article:
    title: str        # Article title
    content: str      # Main text content
    url: str          # Unique identifier
    links: List[str]  # Links for expansion
```

An `Article` is source-agnostic:

- **Wikipedia**: `title` from API, `content` from wikitext, `url` = Wikipedia URL
- **Web**: `title` from `<title>`, `content` from HTML parsing, `url` = web URL
- **Local files**: `title` from filename, `content` from file, `url` = file path

### Shared ArticleProcessor

All sources use the same processor:

```python
processor = ArticleProcessor(conn, use_llm=True)

for article in source.get_articles():
    processor.process_article(
        title=article.title,
        content=article.content,
        url=article.url
    )
```

**Result:** Identical extraction quality across all sources.

## Architecture Diagram

```
┌─────────────────┐
│ WikiGR CLI      │
│ (wikigr create) │
└────────┬────────┘
         │
         ├─────────────────┐
         │                 │
┌────────▼─────────┐  ┌───▼──────────────┐
│ Wikipedia Source │  │ Web Source       │
│ (API calls)      │  │ (HTTP requests)  │
└────────┬─────────┘  └───┬──────────────┘
         │                │
         │  Article       │  Article
         │  objects       │  objects
         │                │
         └────────┬───────┘
                  │
         ┌────────▼────────────┐
         │ ArticleProcessor    │
         │ (shared extraction) │
         └────────┬────────────┘
                  │
         ┌────────▼────────────┐
         │ Kuzu Database       │
         │ (knowledge graph)   │
         └─────────────────────┘
```

## Design Principles

### 1. Separation of Concerns

**ContentSource** responsibilities:
- Fetch content from external source
- Parse into Article objects
- Handle source-specific errors (network, API limits)

**ArticleProcessor** responsibilities:
- Extract entities from articles
- Identify relationships
- Create graph nodes and edges
- Generate embeddings

**Why this matters:** Can improve extraction without touching source connectors, or add new sources without changing extraction logic.

### 2. Protocol Over Inheritance

We use protocols (structural subtyping) instead of inheritance:

```python
# Not this (inheritance):
class WebContentSource(BaseContentSource):
    pass

# This (protocol):
class WebContentSource:
    def get_articles(self) -> Generator[Article, None, None]:
        ...
```

**Benefits:**
- No forced base class
- Duck typing flexibility
- Easier testing (mock any object with `get_articles()`)

### 3. Composition Over Configuration

Sources compose behavior rather than configure it:

```python
# Web source with BFS expansion
web_source = WebContentSource(
    url="...",
    max_depth=2,
    max_links=50
)

# Web source without expansion
web_source_simple = WebContentSource(url="...", max_depth=0)
```

Processing behavior is composed separately:

```python
# LLM extraction with relationships
processor = ArticleProcessor(conn, use_llm=True, extract_relationships=True)

# Heuristic extraction without relationships
processor_fast = ArticleProcessor(conn, use_llm=False, extract_relationships=False)
```

## Implementation: WebContentSource

Let's examine how `WebContentSource` implements the protocol.

### Initialization

```python
class WebContentSource:
    def __init__(
        self,
        url: str,
        max_depth: int = 0,
        max_links: int = 1,
        same_domain_only: bool = True,
        include_pattern: Optional[str] = None,
        exclude_pattern: Optional[str] = None
    ):
        self.url = url
        self.max_depth = max_depth
        self.max_links = max_links
        self.same_domain_only = same_domain_only
        self.include_pattern = include_pattern
        self.exclude_pattern = exclude_pattern
        self.visited = set()
```

**Design choice:** Configuration in constructor, not global config files.

### Article Generation

```python
def get_articles(self) -> Generator[Article, None, None]:
    """
    Yields Article objects using BFS.

    Algorithm:
    1. Start with root URL
    2. Fetch and parse HTML
    3. Yield Article object
    4. Extract links from page
    5. Apply filters (domain, patterns)
    6. Add to queue for next depth level
    7. Repeat until max_depth or max_links reached
    """
    queue = [(self.url, 0)]  # (url, depth)

    while queue and len(self.visited) < self.max_links:
        current_url, depth = queue.pop(0)

        if current_url in self.visited:
            continue

        # Fetch and parse
        response = requests.get(current_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract content
        title = soup.find("title").text
        content = soup.get_text()
        links = [a["href"] for a in soup.find_all("a", href=True)]

        self.visited.add(current_url)

        # Yield Article
        yield Article(title=title, content=content, url=current_url, links=links)

        # Expand if not at max depth
        if depth < self.max_depth:
            filtered_links = self.expand_links(current_url, links, depth)
            queue.extend((link, depth + 1) for link in filtered_links)
```

**Key aspects:**

- **Generator pattern:** Memory-efficient for large crawls
- **BFS traversal:** Breadth-first ensures proximity to root
- **Lazy evaluation:** Articles only fetched when consumed

### Link Filtering

```python
def expand_links(self, root_url: str, links: List[str], depth: int) -> List[str]:
    """
    Apply filters to discovered links.

    Filter order (short-circuit):
    1. Already visited → skip
    2. Same domain check
    3. Include pattern match
    4. Exclude pattern rejection
    5. Max links enforcement
    """
    filtered = []
    root_domain = urlparse(root_url).netloc

    for link in links:
        # Already visited
        if link in self.visited:
            continue

        # Same domain filter
        if self.same_domain_only:
            link_domain = urlparse(link).netloc
            if link_domain != root_domain:
                continue

        # Include pattern
        if self.include_pattern and not re.search(self.include_pattern, link):
            continue

        # Exclude pattern
        if self.exclude_pattern and re.search(self.exclude_pattern, link):
            continue

        # Max links
        if len(self.visited) + len(filtered) >= self.max_links:
            break

        filtered.append(link)

    return filtered
```

**Design choice:** Early filtering saves HTTP requests and processing time.

## Feature Parity Achievement

Web sources now have full parity with Wikipedia sources:

| Feature | Wikipedia | Web | Implementation |
|---------|-----------|-----|----------------|
| Entity extraction | ✓ LLM | ✓ LLM | Shared ArticleProcessor |
| Relationship extraction | ✓ LLM | ✓ LLM | Shared ArticleProcessor |
| Link expansion | ✓ Wiki links | ✓ BFS crawl | Source-specific in get_articles() |
| Incremental updates | ✓ `update` | ✓ `update` | URL-based deduplication |
| Vector embeddings | ✓ | ✓ | Shared ArticleProcessor |
| Graph structure | ✓ | ✓ | Shared ArticleProcessor |

## Extension Points

The architecture makes it easy to add new sources:

### Example: GitHub Wiki Source

```python
class GitHubWikiSource:
    def __init__(self, repo: str, owner: str):
        self.repo = repo
        self.owner = owner

    def get_articles(self) -> Generator[Article, None, None]:
        # Use GitHub API to list wiki pages
        pages = github_api.get_wiki_pages(self.owner, self.repo)

        for page in pages:
            content = github_api.get_wiki_content(self.owner, self.repo, page.name)
            yield Article(
                title=page.title,
                content=content,
                url=page.url,
                links=extract_wiki_links(content)
            )
```

**That's it.** No changes to ArticleProcessor or CLI needed.

### Example: Local Markdown Source

```python
class LocalMarkdownSource:
    def __init__(self, directory: Path):
        self.directory = directory

    def get_articles(self) -> Generator[Article, None, None]:
        for file_path in self.directory.glob("**/*.md"):
            with open(file_path) as f:
                content = f.read()

            title = file_path.stem
            url = f"file://{file_path.absolute()}"
            links = extract_markdown_links(content)

            yield Article(title=title, content=content, url=url, links=links)
```

**Integration:** Add `--source=local` to CLI, wire up the source.

## Trade-offs

### Benefits

**Modularity:** Sources and processor are independent
- Change extraction without touching sources
- Add sources without changing extraction

**Consistency:** Same extraction across all sources
- Wikipedia and web produce identical graph structure
- Users learn one interface

**Testability:** Easy to mock and test
- Mock `get_articles()` for testing processor
- Mock processor for testing sources

**Extensibility:** Add sources with minimal code
- Implement `get_articles()` protocol
- Wire into CLI
- Done

### Costs

**Indirection:** One extra layer between source and processor
- Negligible performance cost
- Worth it for modularity

**Memory:** Article objects created even if not used
- Generator pattern mitigates this
- Only active article in memory at once

**Type safety:** Protocol enforcement at runtime, not compile time
- Python limitation, not architecture flaw
- Consider using `@runtime_checkable` for stricter validation

## Comparison to Alternatives

### Monolithic Approach (Avoided)

```python
def create_kg_from_wikipedia(title: str, conn: Connection):
    # Fetch from Wikipedia API
    # Extract entities inline
    # Create graph inline
    pass

def create_kg_from_web(url: str, conn: Connection):
    # Fetch from web
    # Extract entities inline (duplicate code!)
    # Create graph inline (duplicate code!)
    pass
```

**Problems:**
- Code duplication between sources
- Inconsistent extraction quality
- Hard to test components in isolation

### Inheritance Hierarchy (Avoided)

```python
class BaseContentSource(ABC):
    @abstractmethod
    def fetch_content(self) -> str:
        pass

    def process(self, conn: Connection):
        content = self.fetch_content()
        # Processing logic in base class (tight coupling!)
        pass
```

**Problems:**
- Forces inheritance (rigid)
- Processing logic in base class (hard to swap)
- Difficult to compose behaviors

### Current Approach (Protocol + Composition)

```python
# Protocol (flexible interface)
class ContentSource(Protocol):
    def get_articles(self) -> Generator[Article, None, None]: ...

# Composition (flexible behavior)
processor = ArticleProcessor(conn, use_llm=True)
for article in source.get_articles():
    processor.process_article(article.title, article.content, article.url)
```

**Benefits:**
- Loose coupling via protocol
- Flexible composition
- Easy to test and extend

## Future Directions

### Streaming Processing

Process articles in parallel:

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = []
    for article in source.get_articles():
        future = executor.submit(processor.process_article, article.title, article.content, article.url)
        futures.append(future)

    for future in futures:
        stats = future.result()
```

### Source Composition

Combine multiple sources:

```python
class MultiSource:
    def __init__(self, sources: List[ContentSource]):
        self.sources = sources

    def get_articles(self) -> Generator[Article, None, None]:
        for source in self.sources:
            yield from source.get_articles()

combined = MultiSource([
    WikipediaContentSource(title="Kubernetes"),
    WebContentSource(url="https://kubernetes.io/docs/"),
    LocalMarkdownSource(directory=Path("./my-notes/"))
])
```

### Incremental Processing

Track which articles have been processed:

```python
class IncrementalProcessor:
    def __init__(self, processor: ArticleProcessor, cache_path: Path):
        self.processor = processor
        self.processed = self.load_cache(cache_path)

    def process_articles(self, source: ContentSource):
        for article in source.get_articles():
            if article.url not in self.processed:
                self.processor.process_article(...)
                self.processed.add(article.url)
                self.save_cache()
```

## Related Documentation

- [Web Content Source API Reference](../reference/web-content-source.md)
- [ArticleProcessor API Reference](../reference/article-processor.md)
- [Getting Started with Web Sources](../tutorials/web-sources-getting-started.md)
- [Understanding BFS Link Expansion](./bfs-link-expansion.md)
