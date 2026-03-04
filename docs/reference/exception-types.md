# Exception Types Reference

Complete reference for all exceptions that WikiGR components raise or let propagate.

## Design Principle

WikiGR uses **domain-specific exception types** rather than broad `except Exception` handlers.
Each error domain has its own exception set. Programming bugs (`AttributeError`, `TypeError`,
`KeyError`) are never caught — they propagate immediately so they are visible and fixable.

---

## `wikigr.agent.kg_agent` — KnowledgeGraphAgent

### Exceptions from `query()`

| Exception | Source | Description |
|-----------|--------|-------------|
| `anthropic.APIConnectionError` | Synthesis API call | Network failure connecting to Anthropic API |
| `anthropic.APIStatusError` | Synthesis API call | HTTP error response (4xx/5xx) from Anthropic API |
| `anthropic.APITimeoutError` | Synthesis API call | Anthropic API call timed out |
| `RuntimeError` | `conn.execute()` | LadybugDB database error during query execution |
| `RuntimeError` or `OSError` | Vector pipeline | Embedding model or vector index failure |

### Exceptions from `_identify_seed_articles()`

| Exception | Description |
|-----------|-------------|
| `anthropic.APIConnectionError` | Network failure reaching Anthropic API |
| `anthropic.APIStatusError` | HTTP error from Anthropic API |
| `anthropic.APITimeoutError` | API call timed out |
| `ValueError` | Claude returned an empty response, or the response could not be parsed into a list of article titles |

### Exceptions from `__init__()` / `from_connection()`

| Exception | Description |
|-----------|-------------|
| `RuntimeError` | LadybugDB database could not be opened (missing path, permission denied) |
| `ImportError` | Optional enhancement module not installed |

### Exceptions that propagate as programming bugs

These are **not caught** and indicate a code defect:

| Exception | Typical cause |
|-----------|---------------|
| `AttributeError` | Result dict missing expected key; wrong type passed to internal method |
| `TypeError` | Wrong argument type passed to API or pipeline method |
| `KeyError` | Missing key in query plan dict or database result row |

---

## `wikigr.agent.cypher_rag` — CypherRAG

### Exceptions from `generate_cypher()`

| Exception | Description |
|-----------|-------------|
| `anthropic.APIConnectionError` | Network failure reaching Anthropic API |
| `anthropic.APIStatusError` | HTTP error from Anthropic API |
| `anthropic.APITimeoutError` | API call timed out |
| `ValueError` | Claude returned an empty response |
| `json.JSONDecodeError` | Claude response contained malformed JSON (could not be parsed as a query plan) |

### Pattern retrieval (internal — not raised to caller)

`generate_cypher()` calls `pattern_manager.find_similar_examples()` internally. If that
call raises `RuntimeError` or `OSError`, `generate_cypher()` logs the error at `DEBUG` level
and proceeds with no patterns. The caller only sees the generation-level exceptions above.

### `build_schema_string(conn)`

| Exception | Description |
|-----------|-------------|
| `RuntimeError` | LadybugDB `show_tables()` failed. Returns `"(schema unavailable)"` string instead of raising. |

---

## `wikigr.packs.seed_researcher` — LLMSeedResearcher

### Exception hierarchy

```
SeedResearcherError          # base class for all seed researcher errors
├── LLMAPIError              # Anthropic API failures
├── ExtractionError          # URL extraction failures
├── ValidationError          # URL validation failures
└── ConfigurationError       # Missing ANTHROPIC_API_KEY or bad config
```

Import path:

```python
from wikigr.packs.seed_researcher import (
    SeedResearcherError,
    LLMAPIError,
    ExtractionError,
    ValidationError,
    ConfigurationError,
)
```

### Exceptions from URL fetch loop

The per-URL fetch loops (`_extract_from_sitemap`, `_extract_from_rss`, `_extract_by_crawl`) catch
only `requests.RequestException` per URL and continue to the next. All other exceptions propagate:

| Exception | Description |
|-----------|-------------|
| `requests.RequestException` | Network error (timeout, DNS, connection refused). Caught per-URL; fetch loop continues. |
| `LLMAPIError` | Anthropic API failure during LLM-based URL extraction |
| `ExtractionError` | Could not extract any URLs from a source |
| `ValidationError` | Discovered URL failed scheme or domain validation |
| `ConfigurationError` | `ANTHROPIC_API_KEY` is absent or empty |

### LLM API call translation (`_call_llm_with_retry`)

`_call_llm_with_retry` uses a broad `except Exception` handler internally to implement
exponential backoff. After `max_retries` exhausted, it re-raises as `LLMAPIError`. This is
**intentional exception translation** — Anthropic SDK types become the domain-specific
`LLMAPIError` hierarchy — not a silent swallow. Any exception that escapes the retry budget
propagates as `LLMAPIError`.

### Input validation

`LLMSeedResearcher` validates inputs at construction:

| Check | Error raised |
|-------|-------------|
| `domain` is empty string | `ValidationError` |
| `domain` contains `\x00`, `\n`, or `\r` | `ValidationError` |
| Discovered URL scheme is not `http` or `https` | `ValidationError` (per-URL) |

---

## `scripts/build_*_pack.py` — Build Scripts

### Exceptions from `process_url()`

`process_url()` catches per-URL, non-fatal errors and returns `False` for that URL. All
other errors terminate the build immediately with a traceback.

| Exception | Handling |
|-----------|----------|
| `requests.RequestException` | Caught per-URL; build continues with next URL |
| `json.JSONDecodeError` | Caught per-URL; build continues with next URL |
| `RuntimeError` (LadybugDB) | **Not caught** — terminates build immediately |
| `OSError` (embedding) | **Not caught** — terminates build immediately |
| `AttributeError`, `TypeError` | **Not caught** — terminates build immediately |

If a build terminates with a LadybugDB `RuntimeError`, the `pack.db` file may be corrupt.
Delete it before re-running the build.

---

## Anthropic Exception Types

WikiGR imports Anthropic exception types directly from the `anthropic` package:

```python
from anthropic import APIConnectionError, APIStatusError, APITimeoutError
```

| Type | HTTP equivalent | When to retry |
|------|----------------|---------------|
| `APIConnectionError` | N/A (network layer) | Yes — transient network failure |
| `APITimeoutError` | N/A (timeout) | Yes — transient; apply exponential backoff |
| `APIStatusError` | 4xx / 5xx | Depends on `status_code`: retry 429/503; raise 400/401/403 |

---

## LadybugDB Exception Type

LadybugDB raises plain `RuntimeError` for all database errors. WikiGR does not subclass or wrap
these. Check the error message for details (schema mismatch, missing table, index corrupt, etc.).

---

## Removed Exceptions / Fallbacks

Two internal error-handling paths were removed. If you find code that catches their return
values or relies on their behaviour, update it:

### `_fallback_seed_extraction` (removed from `kg_agent.py`)

Previously returned a list of word-split tokens when `_identify_seed_articles` failed.
Now, API errors from `_identify_seed_articles` propagate directly.

### `_safe_fallback` (removed from `cypher_rag.py`)

Previously returned a generic `MATCH (a:Article) RETURN a LIMIT 10` dict when Cypher
generation failed. Now, `generate_cypher()` raises `ValueError` or `json.JSONDecodeError`
on failure.

---

## See Also

- [Handle Exceptions how-to](../howto/handle-exceptions.md) — practical patterns for callers
- [KG Agent API](../reference/kg-agent-api.md) — full `query()` return value reference
- [Exception Handling Design](../design/exception-handling.md) — design rationale and
  security impact
