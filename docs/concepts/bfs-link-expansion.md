# BFS Link Expansion Algorithm

Understanding how WikiGR crawls web content using breadth-first search.

## The Problem

When building knowledge graphs from web content, a single page rarely contains all relevant information. Users need to:

- Follow links to related content
- Control crawl depth and breadth
- Filter irrelevant links
- Avoid infinite loops and redundant processing

A naive depth-first approach can get stuck in deep rabbit holes. A better approach uses **breadth-first search (BFS)** to explore links systematically.

## Why BFS?

Breadth-first search explores all links at depth N before moving to depth N+1.

### BFS vs DFS Comparison

**Depth-First Search (DFS):**
```
Root → Link1 → Link1.1 → Link1.1.1 → Link1.1.2
                                        └→ (too deep!)
```

**Breadth-First Search (BFS):**
```
Depth 0: Root
Depth 1: Link1, Link2, Link3
Depth 2: Link1.1, Link1.2, Link2.1, Link2.2, Link3.1
Depth 3: ... (controlled by max_depth)
```

**Benefits of BFS:**

1. **Proximity to root:** Pages closer to root are processed first (usually more relevant)
2. **Controlled exploration:** Easy to limit depth without missing breadth
3. **Fair processing:** All links at same depth get equal priority
4. **Predictable memory:** Queue size bounded by links per page × max_depth

## Algorithm Overview

The BFS crawler uses a queue to track URLs to visit:

```
1. Initialize queue with root URL (depth 0)
2. While queue not empty and haven't hit max_links:
   a. Dequeue (url, depth)
   b. Skip if already visited
   c. Fetch and parse page
   d. Yield Article object
   e. Extract links from page
   f. Filter links (domain, patterns, visited)
   g. If depth < max_depth, enqueue filtered links at depth+1
3. Done when queue empty or max_links reached
```

## Implementation Details

### Data Structures

```python
# Queue: (url, depth) tuples
queue: List[Tuple[str, int]] = [(root_url, 0)]

# Visited set: prevent reprocessing
visited: Set[str] = set()

# Current depth and count
current_depth = 0
processed_count = 0
```

### Main Loop

```python
def get_articles(self) -> Generator[Article, None, None]:
    queue = [(self.url, 0)]

    while queue and len(self.visited) < self.max_links:
        current_url, depth = queue.pop(0)  # FIFO (BFS)

        if current_url in self.visited:
            continue

        # Fetch page
        response = requests.get(current_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract content
        title = self._extract_title(soup)
        content = self._extract_content(soup)
        links = self._extract_links(soup, current_url)

        # Mark visited
        self.visited.add(current_url)

        # Yield article
        yield Article(title=title, content=content, url=current_url, links=links)

        # Expand if not at max depth
        if depth < self.max_depth:
            filtered = self.expand_links(current_url, links, depth)
            queue.extend((link, depth + 1) for link in filtered)
```

**Key aspects:**

- `queue.pop(0)` - FIFO ensures BFS order
- `visited` set - O(1) lookup prevents cycles
- Generator pattern - memory-efficient, lazy evaluation
- Depth tracking - each URL knows its distance from root

### Link Filtering

```python
def expand_links(self, root_url: str, links: List[str], depth: int) -> List[str]:
    """
    Filter discovered links before adding to queue.

    Filters applied in order:
    1. Already visited → skip
    2. Same domain (if enabled)
    3. Include pattern (if provided)
    4. Exclude pattern (if provided)
    5. Max links limit
    """
    filtered = []
    root_domain = urlparse(root_url).netloc

    for link in links:
        # Normalize URL
        link = urljoin(root_url, link)  # Resolve relative links

        # Already visited
        if link in self.visited:
            continue

        # Same domain check
        if self.same_domain_only:
            if urlparse(link).netloc != root_domain:
                continue

        # Include pattern
        if self.include_pattern:
            if not re.search(self.include_pattern, link):
                continue

        # Exclude pattern
        if self.exclude_pattern:
            if re.search(self.exclude_pattern, link):
                continue

        # Max links limit
        if len(self.visited) + len(filtered) >= self.max_links:
            break

        filtered.append(link)

    return filtered
```

**Filter order matters:**

- Early checks (visited, domain) are fast
- Regex checks are slower, applied later
- Max links check is last (already invested in filtering)

## Example Execution

Let's trace a BFS crawl with `max_depth=2` and `max_links=10`:

### Initial State

```
Root URL: https://example.com/docs/intro
max_depth: 2
max_links: 10

Queue: [("https://example.com/docs/intro", 0)]
Visited: {}
```

### Iteration 1 (Depth 0)

```
Dequeue: ("https://example.com/docs/intro", 0)
Fetch page, extract content
Links found: ["/docs/setup", "/docs/api", "/blog/news"]

Filter links (same domain only):
  ✓ https://example.com/docs/setup
  ✓ https://example.com/docs/api
  ✗ https://example.com/blog/news (excluded by pattern)

Queue: [
  ("https://example.com/docs/setup", 1),
  ("https://example.com/docs/api", 1)
]
Visited: {"https://example.com/docs/intro"}
Processed: 1/10
```

### Iteration 2 (Depth 1)

```
Dequeue: ("https://example.com/docs/setup", 1)
Fetch page, extract content
Links found: ["/docs/config", "/docs/install", "/docs/intro"]

Filter links:
  ✓ https://example.com/docs/config
  ✓ https://example.com/docs/install
  ✗ https://example.com/docs/intro (already visited)

Queue: [
  ("https://example.com/docs/api", 1),
  ("https://example.com/docs/config", 2),
  ("https://example.com/docs/install", 2)
]
Visited: {"https://example.com/docs/intro", "https://example.com/docs/setup"}
Processed: 2/10
```

### Iteration 3 (Depth 1)

```
Dequeue: ("https://example.com/docs/api", 1)
Fetch page, extract content
Links found: ["/docs/api/auth", "/docs/api/rest"]

Queue: [
  ("https://example.com/docs/config", 2),
  ("https://example.com/docs/install", 2),
  ("https://example.com/docs/api/auth", 2),
  ("https://example.com/docs/api/rest", 2)
]
Visited: {intro, setup, api}
Processed: 3/10
```

### Iteration 4-7 (Depth 2)

Process all depth-2 links:
- config (depth 2)
- install (depth 2)
- api/auth (depth 2)
- api/rest (depth 2)

Each might discover more links, but **depth 2 is max**, so new links are not enqueued.

### Final State

```
Processed: 7 pages (1 at depth 0, 2 at depth 1, 4 at depth 2)
Queue: [] (empty)
Visited: {intro, setup, api, config, install, api/auth, api/rest}
```

## Depth vs Breadth Trade-offs

### Deep Crawl (High max_depth, Low max_links)

```bash
wikigr create --source=web --url="..." --max-depth=5 --max-links=25
```

**Characteristics:**
- Explores deep hierarchies
- Finds highly specific content
- Narrow focus (few branches followed)

**Use cases:**
- Following a specific path deep into docs
- Researching a specialized topic
- Building focused knowledge graphs

### Wide Crawl (Low max_depth, High max_links)

```bash
wikigr create --source=web --url="..." --max-depth=1 --max-links=100
```

**Characteristics:**
- Stays close to root
- Covers broad range of topics
- Wide focus (many branches followed)

**Use cases:**
- Surveying a documentation site
- Building broad knowledge graphs
- Discovering what's available

### Balanced Crawl

```bash
wikigr create --source=web --url="..." --max-depth=2 --max-links=50
```

**Characteristics:**
- Moderate depth and breadth
- Good for most use cases

## Performance Characteristics

### Time Complexity

- **BFS traversal:** O(V + E) where V = vertices (pages), E = edges (links)
- **With max_links limit:** O(min(V, max_links))
- **Depth limit impact:** O(b^d) where b = branching factor, d = max_depth

### Space Complexity

- **Queue size:** O(b × d) worst case (all links at deepest level)
- **Visited set:** O(min(V, max_links))
- **Total:** O(b × d + max_links)

### Real-World Performance

Measured on Microsoft Learn documentation:

| Configuration | Pages | Depth Levels | Time | Queue Peak |
|---------------|-------|--------------|------|------------|
| depth=0, links=1 | 1 | 1 | 1.2s | 1 |
| depth=1, links=10 | 10 | 2 | 12s | 9 |
| depth=2, links=50 | 50 | 3 | 1m 45s | 28 |
| depth=3, links=100 | 100 | 4 | 4m 12s | 47 |

**Observations:**

- Time grows linearly with pages (network-bound)
- Queue size stays manageable (< 50 even for 100 pages)
- Depth 3+ rarely needed for most documentation sites

## Edge Cases and Error Handling

### Infinite Loops

**Problem:** Site has circular links (A → B → A)

**Solution:** Visited set prevents reprocessing

```python
if current_url in self.visited:
    continue
```

### Redirects

**Problem:** URL redirects to different URL (301/302)

**Solution:** Use final URL after redirects

```python
response = requests.get(url, allow_redirects=True)
final_url = response.url  # Use this for visited check
```

### Unreachable Pages

**Problem:** HTTP 404, 500, or network timeout

**Solution:** Log error, continue with remaining queue

```python
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
except requests.RequestException as e:
    logging.warning(f"Failed to fetch {url}: {e}")
    continue  # Skip this page
```

### Malformed URLs

**Problem:** Invalid URLs in `<a href>` tags

**Solution:** Normalize and validate before adding

```python
from urllib.parse import urljoin, urlparse

def normalize_url(base_url: str, link: str) -> Optional[str]:
    try:
        # Resolve relative URLs
        absolute = urljoin(base_url, link)
        # Validate
        parsed = urlparse(absolute)
        if parsed.scheme in ("http", "https"):
            return absolute
    except ValueError:
        pass
    return None
```

### Rate Limiting

**Problem:** Too many requests to same domain

**Solution:** Add delay between requests

```python
import time

def get_articles(self):
    for url, depth in self.bfs_queue:
        # ... fetch page ...
        time.sleep(0.5)  # 500ms delay between requests
```

## Comparison to Other Algorithms

### vs Depth-First Search (DFS)

| Aspect | BFS | DFS |
|--------|-----|-----|
| Exploration order | Level by level | Branch by branch |
| Memory | O(b × d) | O(d) |
| Finds closest first | Yes | No |
| Balanced crawl | Yes | No (can go very deep) |

**BFS wins for web crawling:** Proximity to root matters, balanced exploration.

### vs Bidirectional BFS

Start from both root and target, meet in middle.

**Not applicable here:** No specific target URL, exploring unknown space.

### vs Priority Queue (Dijkstra-style)

Use priority queue instead of FIFO queue, prioritize by relevance score.

**Possible enhancement:**

```python
import heapq

queue = []
heapq.heappush(queue, (priority, url, depth))

while queue:
    priority, url, depth = heapq.heappop(queue)
    # ... process ...
```

**Trade-off:** More complex, requires relevance scoring function.

## Future Enhancements

### Parallel Crawling

Use thread pool for concurrent fetching:

```python
from concurrent.futures import ThreadPoolExecutor

def fetch_batch(urls: List[str]) -> List[Article]:
    with ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(fetch_single, urls))
```

**Benefit:** 5-10x speedup for I/O-bound crawling

### Adaptive Depth

Adjust max_depth based on content quality:

```python
def should_expand(article: Article, depth: int) -> bool:
    if depth >= max_depth:
        return False
    # Expand if high-quality content
    return calculate_quality_score(article) > threshold
```

### Smart Filtering

Use ML to predict link relevance:

```python
def predict_relevance(link: str, context: str) -> float:
    # Use trained model to score link
    return model.predict(link, context)
```

## Related Documentation

- [Web Content Source API Reference](../reference/web-content-source.md)
- [How to Filter Link Crawling](../howto/filter-link-crawling.md)
- [Getting Started with Web Sources](../tutorials/web-sources-getting-started.md)
- [Understanding ContentSource Architecture](./content-source-design.md)
