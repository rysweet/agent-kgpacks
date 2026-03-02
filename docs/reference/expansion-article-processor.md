# Expansion ArticleProcessor API Reference

Reference for `bootstrap/src/expansion/processor.py` — the `ArticleProcessor` used by the
knowledge-graph expansion pipeline.

> **Note:** This is distinct from the backend `ArticleProcessor` documented in
> [article-processor.md](./article-processor.md). The expansion processor is purpose-built for
> the BFS link-crawl pipeline and returns a structured tuple rather than extraction statistics.

---

## ArticleProcessor

Fetches, parses, embeds, and loads a single article into the Kuzu knowledge graph, then returns
outbound links for further expansion.

### Class Definition

```python
from bootstrap.src.expansion.processor import ArticleProcessor
```

### Constructor

```python
def __init__(
    self,
    conn: kuzu.Connection,
    content_source: ContentSource | None = None,
    wikipedia_client=None,          # deprecated
    embedding_generator: EmbeddingGenerator | None = None,
    llm_extractor=None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `conn` | `kuzu.Connection` | required | Kuzu database connection |
| `content_source` | `ContentSource \| None` | `None` | Content source implementation. Defaults to `WikipediaContentSource` when `None` |
| `wikipedia_client` | any | `None` | **Deprecated.** Legacy Wikipedia client; wraps into `WikipediaContentSource` automatically |
| `embedding_generator` | `EmbeddingGenerator \| None` | `None` | Embedding generator; a default instance is created when `None` |
| `llm_extractor` | any | `None` | Optional LLM extractor for entity/fact enrichment |

**Example:**

```python
import kuzu
from bootstrap.src.expansion.processor import ArticleProcessor

db = kuzu.Database("knowledge.db")
conn = kuzu.Connection(db)

# Default (Wikipedia source, auto-created embedding generator)
processor = ArticleProcessor(conn)

# Custom web content source
from bootstrap.src.sources.web_source import WebContentSource
processor = ArticleProcessor(conn, content_source=WebContentSource())
```

---

## Methods

### `process_article()`

```python
def process_article(
    self,
    title_or_url: str,
    category: str = "General",
    expansion_depth: int = 0,
) -> tuple[bool, list[str], str | None]:
```

Processes a single article end-to-end: fetch → parse sections → generate embeddings → load into
graph → extract outbound links.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title_or_url` | `str` | required | Wikipedia article title **or** a full URL when using a web content source |
| `category` | `str` | `"General"` | Semantic category stored on the article node |
| `expansion_depth` | `int` | `0` | BFS depth at which this article was discovered; stored for later filtering |

**Returns:** `tuple[bool, list[str], str | None]`

| Position | Type | Description |
|----------|------|-------------|
| `[0]` | `bool` | `True` if the article was loaded successfully |
| `[1]` | `list[str]` | Outbound article titles or URLs extracted from the article (used to enqueue further work) |
| `[2]` | `str \| None` | Error message if the call failed; `None` on success |

**Example:**

```python
success, links, error = processor.process_article(
    title_or_url="Kubernetes",
    category="Container Orchestration",
    expansion_depth=1,
)

if success:
    print(f"Loaded. Found {len(links)} outbound links.")
else:
    print(f"Failed: {error}")
```

**Internal processing steps:**

1. Fetch article via the configured `ContentSource`
2. Follow Wikipedia `#REDIRECT` targets (Wikipedia source only)
3. Parse article into sections via `ContentSource.parse_sections()`
4. Generate vector embeddings for each section
5. Run optional LLM extraction for entities, facts, and relationships (skipped on failure, never blocks success)
6. Upsert article node, section nodes, chunks, categories, and any LLM-extracted data in Kuzu
7. Return `(True, article.links, None)` on success

**Edge cases:**

| Scenario | Return value |
|----------|-------------|
| Article not found | `(False, [], "Article not found: <title_or_url>")` |
| Stub article (no parseable sections) | `(True, article.links, None)` — links still propagated |
| Unfollowable redirect target | `(True, [], None)` — silently skipped |
| Redirect target fetch error | `(False, [], "Redirect target fetch failed: <error>")` |

---

## Caller Contract: `ExpansionOrchestrator`

`RyuGraphOrchestrator._process_one(article_info, worker_conn)` is the primary caller. The keyword argument
**must** match the parameter name `title_or_url`:

```python
# orchestrator.py — correct call site
success, links, error = worker_processor.process_article(
    title_or_url=title,        # matches processor.py:118 signature
    category=article_info.get("category", "General"),
    expansion_depth=depth,
)
```

Passing `title=title` instead of `title_or_url=title` raises a `TypeError` at runtime because
Python keyword arguments are matched by name, not position.

---

## Error Sanitization

All error messages emitted by `ArticleProcessor` (logs and returned strings) are passed through
`_sanitize_error()` before leaving the module. This helper redacts:

- API key patterns with separators (`api_key=`, `token=`, `bearer=`, etc.) — redacts values ≥ 20 characters
- Standalone secret keys in quotes (`sk-...` prefix, or any alphanumeric string ≥ 30 characters in quotes)
- Authorization header values (full header line)

```python
from bootstrap.src.expansion.processor import _sanitize_error

# Internal use only — not part of the public API
msg = _sanitize_error('api_key="sk-abc123abc123abc123abc123abc123"')
# → 'api_key=***REDACTED***'
```

---

## Integration with the Expansion Pipeline

```
RyuGraphOrchestrator
  └── _process_one(article_info, worker_conn)
        ├── WorkQueueManager.update_heartbeat(title)
        ├── ArticleProcessor.process_article(title_or_url=title, ...)
        │     └── returns (success, links, error)
        └── LinkDiscovery.discover_links(source_title, links, ...)
```

Each worker thread creates its own `ArticleProcessor` instance backed by an independent
`kuzu.Connection` — Kuzu connections are not thread-safe and must not be shared across threads.

```python
# Worker creates its own processor — do NOT share across threads
worker_conn = kuzu.Connection(db)
worker_processor = ArticleProcessor(
    worker_conn,
    embedding_generator=self._shared_embedding_generator,  # model.encode() is thread-safe
)
```

---

## Related Documentation

- [BFS Link Expansion](../concepts/bfs-link-expansion.md)
- [Expansion Orchestrator](../concepts/architecture.md)
- [Backend ArticleProcessor API Reference](./article-processor.md) — separate class, different interface
- [Content Source Design](../concepts/content-source-design.md)
