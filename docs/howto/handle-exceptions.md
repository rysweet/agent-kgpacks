# Handle Exceptions from WikiGR Components

This guide covers the exceptions that can propagate from `KnowledgeGraphAgent`, `CypherRAG`,
and the build scripts, and shows how to catch them correctly.

## Quick Reference

| Component | Method | Exceptions That Propagate |
|-----------|--------|--------------------------|
| `KnowledgeGraphAgent` | `query()` | `APIConnectionError`, `APIStatusError`, `APITimeoutError`, `RuntimeError` |
| `KnowledgeGraphAgent` | `_identify_seed_articles()` | `APIConnectionError`, `APIStatusError`, `APITimeoutError`, `ValueError` |
| `CypherRAG` | `generate_cypher()` | `APIConnectionError`, `APIStatusError`, `APITimeoutError`, `ValueError`, `json.JSONDecodeError` |
| `LLMSeedResearcher` | URL fetch loop | `requests.RequestException` |
| Build scripts | `process_url()` | `requests.RequestException`, `json.JSONDecodeError` |

Programming bugs (`AttributeError`, `TypeError`, `KeyError`) are **not caught** — they propagate
directly. Fix the bug; do not add a broad `except Exception` around these calls.

---

## KnowledgeGraphAgent

### Anthropic API errors

API errors from synthesis or seed identification propagate as one of three Anthropic exception
types. Catch all three together:

```python
from anthropic import APIConnectionError, APIStatusError, APITimeoutError
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(db_path="data/packs/go-expert/pack.db")

try:
    result = agent.query("What is goroutine scheduling?")
except (APIConnectionError, APITimeoutError) as e:
    # Transient — retry after a brief wait
    print(f"API temporarily unavailable: {e}")
except APIStatusError as e:
    # Permanent for this request (e.g. 400 Bad Request, 401 Unauthorized)
    print(f"API rejected the request: {e.status_code} {e.message}")
    raise
```

### Database errors

Kuzu errors surface as `RuntimeError`. These indicate a corrupt database, a missing pack file,
or a schema mismatch:

```python
try:
    result = agent.query("What is goroutine scheduling?")
except RuntimeError as e:
    print(f"Database error (check pack integrity): {e}")
    raise
```

### Embedding / vector pipeline errors

Vector search failures raise `RuntimeError` or `OSError` (e.g. the embedding model files are
missing or the vector index is corrupt):

```python
try:
    result = agent.query("...")
except (RuntimeError, OSError) as e:
    print(f"Vector pipeline error: {e}")
    raise
```

### Typical caller pattern

For most application code, catching API errors and re-raising the rest is sufficient:

```python
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

try:
    result = agent.query(user_question)
    return result["answer"]
except (APIConnectionError, APITimeoutError):
    return "The AI service is temporarily unavailable. Please try again."
except APIStatusError as e:
    if e.status_code == 401:
        raise RuntimeError("Invalid ANTHROPIC_API_KEY") from e
    raise
```

---

## CypherRAG

`CypherRAG.generate_cypher()` raises exceptions rather than returning a generic fallback query.
Callers that previously relied on a silent passthrough must now handle failure explicitly.

### Empty API response

```python
from wikigr.agent.cypher_rag import CypherRAG
from anthropic import APIConnectionError, APIStatusError, APITimeoutError

try:
    plan = rag.generate_cypher(question)
except ValueError as e:
    # Empty response from Claude — treat as generation failure
    logger.warning("Cypher generation returned empty response: %s", e)
    plan = None
except json.JSONDecodeError as e:
    # Malformed JSON in Claude response
    logger.warning("Cypher generation returned unparseable JSON: %s", e)
    plan = None
except (APIConnectionError, APIStatusError, APITimeoutError):
    raise  # let API errors propagate
```

### Pattern retrieval failure

Pattern retrieval (`FewShotManager.find_similar_examples`) raises `RuntimeError` or `OSError`
when the pattern store is unavailable. `generate_cypher()` handles this internally — if pattern
retrieval fails, it proceeds with no patterns rather than aborting. The caller only sees the
generation-level exceptions listed above.

---

## LLM Seed Researcher

`LLMSeedResearcher` URL fetching catches only `requests.RequestException`. All other exceptions
propagate immediately.

```python
from requests import RequestException
from wikigr.packs.seed_researcher import LLMSeedResearcher

researcher = LLMSeedResearcher(domain="go.dev", topic="Go programming language")

try:
    urls = researcher.discover_urls(max_urls=50)
except RequestException as e:
    # Network failure during source discovery
    print(f"Could not reach {e.request.url if e.request else 'remote source'}: {e}")
```

---

## Build Scripts (`scripts/build_*_pack.py`)

Each build script's `process_url()` function catches only network and JSON errors. Kuzu
errors, embedding failures, and other unexpected errors now **abort the build** with a visible
traceback rather than logging a warning and moving on to the next URL.

This is intentional: a corrupt partial database write is worse than a build that fails fast.

```python
# Inside process_url() — exceptions that are caught (per-URL, non-fatal):
#   requests.RequestException   — network timeout, DNS failure, etc.
#   json.JSONDecodeError        — malformed JSON in API response

# Exceptions that are NOT caught (fatal, abort the build):
#   RuntimeError                — Kuzu database error
#   OSError                     — embedding model file missing
#   AttributeError, TypeError   — programming bug in extraction code
```

If a build aborts with a Kuzu `RuntimeError`, the database may be in a partial state. Delete
the `pack.db` file and re-run the build from scratch.

---

## What You Should NOT Do

### Broad `except Exception`

Do not add a broad `except Exception` around calls to WikiGR components. Broad handlers hide
programming bugs and make debugging harder:

```python
# BAD — swallows AttributeError, TypeError, KeyError (programming bugs)
try:
    result = agent.query(question)
except Exception as e:
    return f"Error: {e}"

# GOOD — catch only the recoverable cases
try:
    result = agent.query(question)
except (APIConnectionError, APITimeoutError):
    return "Temporarily unavailable."
```

### Relying on silent fallbacks (removed)

Two silent fallbacks that existed in earlier versions have been removed:

- **`_fallback_seed_extraction`** — word-splitting was not an acceptable degradation for
  semantic seed identification. API errors from `_identify_seed_articles` now propagate.
- **`_safe_fallback` in `CypherRAG`** — a generic `MATCH` query is not a valid fallback
  for a failed Cypher generation step. `generate_cypher()` now raises `ValueError` or
  `json.JSONDecodeError` on failure.

If you were catching the return value of these methods (previously always a dict), update
your code to handle the exceptions described above.

---

## Exception Domain Summary

Exception domains, plus programming bugs that propagate unhandled:

| Domain | Exception Types | When Raised |
|--------|----------------|-------------|
| Anthropic API | `APIConnectionError`, `APIStatusError`, `APITimeoutError` | Synthesis, seed identification, Cypher generation |
| Kuzu database | `RuntimeError` | Any `conn.execute()` call |
| Embedding / ML | `RuntimeError`, `OSError` | Vector ops, model loading, pipeline init |
| Seed researcher | `requests.RequestException` | HTTP fetch, DNS, timeout |
| Build scripts (JSON) | `json.JSONDecodeError` | Malformed API response in URL loop |
| Programming bugs | `AttributeError`, `TypeError`, `KeyError` | Always — fix the bug, do not catch |

---

## See Also

- [Exception Types Reference](../reference/exception-types.md) — full list of exception types
  and which module raises them
- [KG Agent API](../reference/kg-agent-api.md) — `query()` return value and `query_type` values
- [Security: Exception Handling](../design/exception-handling.md) — design rationale and
  security implications
