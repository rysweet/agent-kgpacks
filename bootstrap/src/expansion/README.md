# Expansion Module

**Location:** `bootstrap/src/expansion/`

Graph expansion orchestration for WikiGR, managing incremental article discovery and loading through work queues and link traversal.

## Modules

- `work_queue.py` - Work queue management with claim-based distribution
- `link_discovery.py` - Link discovery and graph expansion
- `processor.py` - Article processing orchestration

---

## LinkDiscovery

**Module:** `bootstrap/src/expansion/link_discovery.py`

Discovers new articles from links in existing articles, managing expansion depth and creating LINKS_TO relationships in the graph.

### Features

- **Link filtering**: Automatically filters invalid links (special pages, meta pages, lists, disambiguation)
- **Depth tracking**: Controls expansion depth to prevent infinite traversal
- **Duplicate handling**: Prevents duplicate articles and relationships
- **Relationship creation**: Creates LINKS_TO edges between articles

### Usage

```python
from expansion import LinkDiscovery
import kuzu

# Initialize with Kuzu connection
conn = kuzu.Connection(kuzu.Database("path/to/db"))
discovery = LinkDiscovery(conn)

# Discover links from a source article
# links would typically come from WikipediaArticle.links
links = ["Machine Learning", "Deep Learning", "Statistics"]

new_count = discovery.discover_links(
    source_title="Artificial Intelligence",
    links=links,
    current_depth=0,
    max_depth=2
)

print(f"Discovered {new_count} new articles")
```

### API Reference

#### `discover_links(source_title, links, current_depth, max_depth=2) -> int`

Process links and discover new articles.

**Args:**
- `source_title`: Source article title
- `links`: List of linked article titles
- `current_depth`: Current expansion depth
- `max_depth`: Maximum expansion depth (default: 2)

**Returns:**
- Number of new articles discovered

**Behavior:**
1. If `current_depth >= max_depth`: return 0 (don't expand further)
2. For each link:
   - Filter out invalid links
   - Check if article exists in DB
   - If exists: Create LINKS_TO relationship only
   - If new: INSERT as discovered (depth = current_depth + 1) and create LINKS_TO
3. Return count of new articles

#### `article_exists(title) -> tuple[bool, Optional[str]]`

Check if article exists in database.

**Returns:**
- `(exists, state)` where:
  - `exists`: True if article found
  - `state`: expansion_state if found, None otherwise

#### `get_discovered_count() -> int`

Get count of discovered but not yet loaded articles.

**Returns:**
- Number of articles in 'discovered' state

### Link Filtering

The following link types are automatically filtered out:

- **Namespace pages**: `Wikipedia:`, `Help:`, `Template:`, `Category:`, `Portal:`, `Talk:`, `User:`, `MediaWiki:`, `Special:`
- **File pages**: `File:`, `Image:`
- **List pages**: `List of ...`
- **Disambiguation pages**: `... (disambiguation)`
- **Empty or very short titles**

### Expansion Strategy

Breadth-first expansion through depth levels:

```
depth=0 (Seeds)
   ├─→ depth=1 (Direct links from seeds)
   │      ├─→ depth=2 (Links from depth-1)
   │      │      └─→ max_depth=2 (stop here)
```

### Testing

Run standalone tests:

```bash
python src/expansion/link_discovery.py
```

See also: `src/expansion/tests/test_link_discovery.py`

### Example

See `src/expansion/examples/basic_usage.py` for a complete demonstration.

---

## WorkQueueManager

**Module:** `bootstrap/src/expansion/work_queue.py`

The WorkQueueManager implements the expansion state machine for coordinating work across workers. It provides mechanisms for:

- **Claiming work**: Batch claim of articles for processing
- **Heartbeat updates**: Keep-alive signals to prevent premature reclamation
- **Stale reclamation**: Automatic recovery of abandoned work
- **State transitions**: Move articles through processing states
- **Failure handling**: Retry logic with configurable max attempts

## State Machine

```
┌──────────┐
│DISCOVERED│ (Ready to process)
└────┬─────┘
     │ claim_work()
     ▼
┌──────────┐
│ CLAIMED  │ (Worker processing)
└────┬─────┘
     │ process_article()
     ├─ Success → advance_state('loaded')
     │            ┌──────────┐
     │            │  LOADED  │
     │            └──────────┘
     │
     ├─ Failure → mark_failed()
     │            ┌──────────┐
     │            │  FAILED  │ (max retries exceeded)
     │            └──────────┘
     │            OR
     │            ┌──────────┐
     │            │DISCOVERED│ (retry, back to queue)
     │            └──────────┘
     │
     └─ Timeout → reclaim_stale()
                  ┌──────────┐
                  │DISCOVERED│ (back to queue)
                  └──────────┘
```

## Usage

### Basic Usage

```python
import kuzu
from src.expansion import WorkQueueManager

# Initialize
db = kuzu.Database("data/wikigr.db")
conn = kuzu.Connection(db)
manager = WorkQueueManager(conn, max_retries=3)

# Claim work
articles = manager.claim_work(batch_size=10)

# Process each article
for article in articles:
    title = article['title']

    # Update heartbeat periodically during processing
    manager.update_heartbeat(title)

    # Process article...
    success = process_article(title)

    if success:
        manager.advance_state(title, "loaded")
    else:
        manager.mark_failed(title, "Processing error")

# Reclaim stale work
reclaimed = manager.reclaim_stale(timeout_seconds=300)
```

### Worker Loop Pattern

```python
def worker_loop(manager, timeout_seconds=300):
    """Continuous worker processing loop"""

    while True:
        # Reclaim stale work
        manager.reclaim_stale(timeout_seconds)

        # Claim batch
        articles = manager.claim_work(batch_size=10)

        if not articles:
            print("No work available")
            time.sleep(60)
            continue

        # Process batch
        for article in articles:
            try:
                # Heartbeat every 30 seconds
                manager.update_heartbeat(article['title'])

                # Process
                result = process_article(article)

                if result.success:
                    manager.advance_state(article['title'], 'loaded')
                else:
                    manager.mark_failed(article['title'], result.error)

            except Exception as e:
                manager.mark_failed(article['title'], str(e))
```

## API Reference

### WorkQueueManager

#### `__init__(conn, max_retries=3)`

Initialize work queue manager.

**Args:**
- `conn`: Kuzu database connection
- `max_retries`: Maximum retry attempts before marking as failed (default: 3)

#### `claim_work(batch_size=10, timeout_seconds=300) -> list[dict]`

Claim a batch of articles for processing.

**Args:**
- `batch_size`: Number of articles to claim (default: 10)
- `timeout_seconds`: How long to hold claim before reclaim (default: 300)

**Returns:**
- List of claimed articles: `[{'title': str, 'expansion_depth': int, 'claimed_at': datetime}]`
- Empty list if no work available

**Behavior:**
- Finds articles with `expansion_state = 'discovered'`
- Orders by `expansion_depth ASC` (processes seeds first)
- Updates state to `'claimed'` with current timestamp
- Returns list of claimed articles

#### `update_heartbeat(article_title)`

Update heartbeat timestamp for claimed article.

**Args:**
- `article_title`: Article being processed

**Behavior:**
- Updates `claimed_at` to current time
- Prevents reclamation while processing

#### `reclaim_stale(timeout_seconds=300) -> int`

Reclaim articles with stale claims (no heartbeat).

**Args:**
- `timeout_seconds`: Timeout for stale claims (default: 300)

**Returns:**
- Number of articles reclaimed

**Behavior:**
- Finds articles with `state = 'claimed'` AND `claimed_at < (NOW - timeout)`
- Updates state to `'discovered'` and clears `claimed_at`

#### `advance_state(article_title, new_state)`

Advance article to new state.

**Args:**
- `article_title`: Article title
- `new_state`: New state ('loaded', 'failed', 'processed')

**Behavior:**
- Updates `expansion_state` to new_state
- Sets `processed_at` to current time

#### `mark_failed(article_title, error)`

Mark article as failed with retry logic.

**Args:**
- `article_title`: Article title
- `error`: Error message (for logging)

**Behavior:**
- Increments `retry_count`
- If `retry_count >= max_retries`:
  - Sets state to `'failed'`
  - Sets `processed_at`
- Else:
  - Sets state to `'discovered'` (retry)
  - Clears `claimed_at`

#### `get_queue_stats() -> dict`

Get work queue statistics.

**Returns:**
- Dictionary with counts by state: `{'discovered': int, 'claimed': int, 'loaded': int, 'failed': int, 'total': int}`

## Testing

Run the built-in test suite:

```bash
cd bootstrap
python -m src.expansion.work_queue
```

**Test Coverage:**
- ✓ Claim work from discovered articles
- ✓ Heartbeat updates
- ✓ Stale claim reclamation
- ✓ State transitions (advance_state)
- ✓ Failure handling with retries
- ✓ Queue statistics

## Design Decisions

### Claim-Based Work Distribution

Uses optimistic locking via state transitions rather than database locks:
- Simpler implementation
- Better scalability across multiple workers
- Natural timeout handling via heartbeat

### Priority by Depth

Processes articles by `expansion_depth ASC`:
- Seeds (depth=0) processed first
- Ensures core articles loaded before expanding frontier
- Provides breadth-first expansion pattern

### Heartbeat Pattern

Worker must periodically update heartbeat to retain claim:
- Prevents worker failures from blocking queue
- Configurable timeout for different processing times
- No manual cleanup needed - automatic reclamation

### Retry Logic

Failed articles automatically retry up to `max_retries`:
- Handles transient failures (network, API rate limits)
- Permanent failures eventually marked as 'failed'
- Preserves work queue integrity

## Integration

### With ArticleLoader

```python
from src.database import ArticleLoader
from src.expansion import WorkQueueManager

loader = ArticleLoader(db_path)
manager = WorkQueueManager(loader.conn)

# Claim and process
articles = manager.claim_work(batch_size=5)
for article in articles:
    success, error = loader.load_article(article['title'])
    if success:
        manager.advance_state(article['title'], 'loaded')
    else:
        manager.mark_failed(article['title'], error)
```

### Complete Expansion Workflow

Integration of WorkQueueManager and LinkDiscovery:

```python
from expansion import WorkQueueManager, LinkDiscovery
from wikipedia import WikipediaAPIClient
from database import ArticleLoader

# Setup
client = WikipediaAPIClient()
loader = ArticleLoader(db_path)
discovery = LinkDiscovery(loader.conn)
queue = WorkQueueManager(loader.conn, max_retries=3)

# Expansion loop
while queue.get_queue_stats()['discovered'] > 0:
    # Reclaim stale work
    queue.reclaim_stale(timeout_seconds=300)

    # Claim batch
    articles = queue.claim_work(batch_size=10)

    if not articles:
        break

    # Process each article
    for article_info in articles:
        title = article_info['title']
        depth = article_info['expansion_depth']

        try:
            # Heartbeat
            queue.update_heartbeat(title)

            # Fetch from Wikipedia
            article = client.fetch_article(title)

            # Load into database
            success, error = loader.load_article(
                title=article.title,
                category=article.categories[0] if article.categories else "General",
                expansion_state="loaded",
                expansion_depth=depth
            )

            if success:
                # Discover new links for next depth
                discovery.discover_links(
                    source_title=article.title,
                    links=article.links,
                    current_depth=depth,
                    max_depth=2
                )

                # Mark as loaded
                queue.advance_state(title, 'loaded')
            else:
                queue.mark_failed(title, error)

        except Exception as e:
            queue.mark_failed(title, str(e))
```

## Performance Considerations

- **Batch size**: Balance between throughput and latency
  - Small (5-10): Low latency, good for single worker
  - Large (50-100): Higher throughput, better for parallel workers

- **Heartbeat frequency**: Update every 30-60 seconds
  - Too frequent: Unnecessary database load
  - Too infrequent: Risk of premature reclamation

- **Timeout**: Set based on expected processing time
  - Fast articles (< 1 min): 300s timeout
  - Slow articles (5-10 min): 900s timeout

## References

- **Architecture Spec**: `bootstrap/docs/architecture-specification.md`
- **Database Schema**: See "Article Node" properties (lines 76-90)
- **State Machine**: See "Expansion Orchestrator" section (lines 312-354)
- **Error Handling**: See "Retry Logic" section (lines 646-677)
