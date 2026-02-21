# Expansion State Machine

**Purpose:** Document article expansion states and transitions

---

## State Diagram

```
     ┌────────────────────────────────────────┐
     │          INITIALIZATION                 │
     │   initialize_seeds(seed_titles)         │
     └──────────────┬─────────────────────────┘
                    │
                    ▼
            ┌──────────────┐
            │ DISCOVERED   │ (Found via links, depth > 0)
            │  (depth=N)   │ (Or seed, depth=0)
            └──────┬───────┘
                   │
                   │ claim_work(batch_size)
                   │
                   ▼
            ┌──────────────┐
            │  CLAIMED     │ (Worker claimed for processing)
            │ claimed_at=T │
            └──────┬───────┘
                   │
                   │ process_article()
                   │
         ┌─────────┴─────────┐
         │                   │
    SUCCESS                FAILURE
         │                   │
         ▼                   ▼
  ┌──────────────┐   ┌──────────────┐
  │   LOADED     │   │  retry_count │
  │processed_at=T│   │     += 1     │
  └──────┬───────┘   └──────┬───────┘
         │                   │
         │            ┌──────┴──────┐
         │            │             │
         │      retry_count    retry_count
         │         < 3           >= 3
         │            │             │
         │            ▼             ▼
         │    ┌──────────────┐  ┌────────┐
         │    │ DISCOVERED   │  │ FAILED │
         │    │ (retry)      │  │ (dead) │
         │    └──────────────┘  └────────┘
         │
         │ discover_links()
         │
         ▼
  ┌──────────────┐
  │  PROCESSED   │ (Links discovered, expansion complete)
  └──────────────┘

  Timeout (no heartbeat):
  CLAIMED ──reclaim_stale()──> DISCOVERED
```

---

## States

### 1. DISCOVERED
**Meaning:** Article identified but not yet processed

**Entry conditions:**
- Initial seeds via `initialize_seeds()`
- Found via links from processed articles
- Reclaimed from stale claims
- Retry after failure (retry_count < max_retries)

**Properties:**
- `expansion_state = 'discovered'`
- `expansion_depth = N` (0 for seeds, N+1 for links)
- `claimed_at = NULL`
- `processed_at = NULL`

**Exit transitions:**
- → CLAIMED (via `claim_work()`)

---

### 2. CLAIMED
**Meaning:** Article claimed by worker for processing

**Entry conditions:**
- Claimed via `claim_work()`

**Properties:**
- `expansion_state = 'claimed'`
- `claimed_at = TIMESTAMP` (set when claimed)
- Heartbeat updated during processing

**Exit transitions:**
- → LOADED (success)
- → DISCOVERED (failure + retry)
- → FAILED (failure + max retries)
- → DISCOVERED (timeout + reclaim)

**Timeout:**
- If no heartbeat for `timeout_seconds` (default 300s)
- Automatically reclaimed via `reclaim_stale()`

---

### 3. LOADED
**Meaning:** Article successfully loaded into database

**Entry conditions:**
- Successful processing via `process_article()`

**Properties:**
- `expansion_state = 'loaded'`
- `processed_at = TIMESTAMP` (set when loaded)
- All sections and relationships created

**Exit transitions:**
- → PROCESSED (after link discovery)

**Next action:**
- `discover_links()` to find new articles

---

### 4. PROCESSED
**Meaning:** Article loaded AND links discovered

**Entry conditions:**
- Links discovered via `discover_links()`

**Properties:**
- `expansion_state = 'processed'`
- `processed_at = TIMESTAMP`
- LINKS_TO relationships created

**Exit transitions:**
- None (terminal state for this expansion session)

**Note:** In current implementation, we may combine LOADED and PROCESSED.

---

### 5. FAILED
**Meaning:** Article failed after max retry attempts

**Entry conditions:**
- Processing failed `max_retries` times (default 3)

**Properties:**
- `expansion_state = 'failed'`
- `retry_count >= max_retries`
- Error logged

**Exit transitions:**
- None (terminal state - manual intervention required)

**Recovery:**
- Manual reset to DISCOVERED if needed
- Or exclude from expansion permanently

---

## State Transitions

### initialize_seeds(seed_titles)
```
NULL → DISCOVERED (depth=0)
```

**Action:**
```cypher
CREATE (a:Article {
    title: $title,
    expansion_state: 'discovered',
    expansion_depth: 0,
    claimed_at: NULL,
    processed_at: NULL,
    retry_count: 0
})
```

---

### claim_work(batch_size)
```
DISCOVERED → CLAIMED
```

**Action:**
```cypher
MATCH (a:Article)
WHERE a.expansion_state = 'discovered'
ORDER BY a.expansion_depth ASC
LIMIT $batch_size

SET a.expansion_state = 'claimed',
    a.claimed_at = $now

RETURN a.title, a.expansion_depth
```

**Result:** List of claimed articles

---

### process_article(title) - SUCCESS
```
CLAIMED → LOADED
```

**Action:**
```cypher
MATCH (a:Article {title: $title})
SET a.expansion_state = 'loaded',
    a.processed_at = $now
```

**Side effects:**
- Article data inserted
- Sections created with embeddings
- HAS_SECTION relationships created
- IN_CATEGORY relationship created

---

### process_article(title) - FAILURE (retry < max)
```
CLAIMED → DISCOVERED (retry)
```

**Action:**
```cypher
MATCH (a:Article {title: $title})
SET a.expansion_state = 'discovered',
    a.claimed_at = NULL,
    a.retry_count = a.retry_count + 1
```

**Result:** Article goes back to queue for retry

---

### process_article(title) - FAILURE (retry >= max)
```
CLAIMED → FAILED
```

**Action:**
```cypher
MATCH (a:Article {title: $title})
SET a.expansion_state = 'failed',
    a.processed_at = $now
```

**Result:** Article marked as permanently failed

---

### discover_links(source_title, links, depth)
```
LOADED → PROCESSED
(+ creates new DISCOVERED articles)
```

**Actions:**
```cypher
// 1. Mark source as processed
MATCH (source:Article {title: $source_title})
SET source.expansion_state = 'processed'

// 2. For each link:
// If link exists: Create LINKS_TO only
MATCH (source:Article {title: $source}),
      (target:Article {title: $link})
CREATE (source)-[:LINKS_TO]->(target)

// If link is new: Create article + relationship
CREATE (target:Article {
    title: $link,
    expansion_state: 'discovered',
    expansion_depth: $depth + 1,
    ...
})

MATCH (source:Article {title: $source})
CREATE (source)-[:LINKS_TO]->(target)
```

---

### reclaim_stale(timeout_seconds)
```
CLAIMED (stale) → DISCOVERED
```

**Action:**
```cypher
MATCH (a:Article)
WHERE a.expansion_state = 'claimed'
  AND a.claimed_at < $cutoff

SET a.expansion_state = 'discovered',
    a.claimed_at = NULL

RETURN COUNT(a) AS reclaimed
```

**Cutoff:** NOW - timeout_seconds

**Result:** Count of reclaimed articles

---

## Heartbeat Mechanism

**Purpose:** Prevent stale claims from blocking expansion

**Implementation:**

```python
def update_heartbeat(conn, article_title: str):
    """Update heartbeat for active processing"""
    conn.execute("""
        MATCH (a:Article {title: $title})
        WHERE a.expansion_state = 'claimed'
        SET a.claimed_at = $now
    """, {"title": article_title, "now": datetime.now()})
```

**Frequency:** Update every 30-60 seconds during long operations (e.g., embedding generation)

**Timeout:** If no heartbeat for 300 seconds (5 minutes), article is reclaimed

---

## Error Handling

### Retry Strategy

**Max retries:** 3 (configurable)

**Retry logic:**
```python
if retry_count < max_retries:
    # Reset to discovered for retry
    state = 'discovered'
    claimed_at = NULL
    retry_count += 1
else:
    # Mark as permanently failed
    state = 'failed'
    processed_at = NOW
```

**Exponential backoff:** Not implemented at state level (handled by work queue ordering)

---

### Failure Categories

**Transient failures (retry):**
- Network timeout
- Wikipedia API 500 error
- Rate limiting (429)

**Permanent failures (mark failed):**
- Article not found (404)
- Invalid article (disambiguation, redirect loop)
- Parsing error (malformed wikitext)

---

## State Queries

### Get state distribution

```cypher
MATCH (a:Article)
RETURN a.expansion_state AS state,
       COUNT(a) AS count,
       AVG(a.expansion_depth) AS avg_depth
ORDER BY count DESC
```

### Get work queue size

```cypher
MATCH (a:Article)
WHERE a.expansion_state = 'discovered'
RETURN COUNT(a) AS queue_size
```

### Get processing progress

```cypher
MATCH (a:Article)
WITH COUNT(a) AS total

MATCH (loaded:Article)
WHERE loaded.expansion_state IN ['loaded', 'processed']
WITH total, COUNT(loaded) AS loaded_count

RETURN loaded_count, total, (100.0 * loaded_count / total) AS percent_complete
```

### Get stale claims

```cypher
MATCH (a:Article)
WHERE a.expansion_state = 'claimed'
  AND a.claimed_at < $cutoff
RETURN a.title, a.claimed_at, a.expansion_depth
```

---

## Implementation Notes

### Concurrency

**Single worker:** Simple, no coordination needed
**Multiple workers:** Each claims independent batch, heartbeat prevents conflicts

**Race conditions:**
- Claim: Handled by Kuzu transaction isolation
- Heartbeat: Last write wins (acceptable)
- Reclaim: May reclaim article being processed (worker will detect and skip)

### Performance

**Claim query:** O(log N) with index on expansion_state + expansion_depth
**Heartbeat update:** O(1) by primary key
**Reclaim query:** O(N) but infrequent (every few minutes)

### Monitoring

**Key metrics:**
- Queue size (discovered count)
- Active workers (claimed count)
- Completion rate (loaded count)
- Failure rate (failed count)
- Depth distribution

---

## Example Usage

```python
from bootstrap.src.expansion.work_queue import WorkQueueManager

# Initialize
queue = WorkQueueManager(conn)

# Main processing loop
while True:
    # Claim work
    batch = queue.claim_work(batch_size=10, timeout_seconds=300)

    if not batch:
        print("No more work")
        break

    # Process each article
    for article in batch:
        try:
            # Heartbeat during long operation
            queue.update_heartbeat(article['title'])

            # Process article (fetch, parse, embed, load)
            process_article(article['title'])

            # Mark as loaded
            queue.advance_state(article['title'], 'loaded')

        except Exception as e:
            # Mark as failed (with retry)
            queue.mark_failed(article['title'], str(e))

    # Reclaim stale claims periodically
    reclaimed = queue.reclaim_stale(timeout_seconds=300)
    if reclaimed > 0:
        print(f"Reclaimed {reclaimed} stale claims")
```
