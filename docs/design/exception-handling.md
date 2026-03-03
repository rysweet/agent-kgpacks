# Design Specification: Exception Handling Narrowing

## Overview

Eliminate silent fallbacks and broad `except Exception` blocks across
`wikigr/agent/`, `wikigr/packs/`, and `scripts/build_*_pack.py`.

**Outcome:** 1121 passed, 45 skipped, 0 failed.

---

## Components Changed

| Component | Change |
|---|---|
| `wikigr/agent/kg_agent.py` | 13 `except Exception` blocks narrowed; 2 fallback methods removed; 2 internal stage names corrected |
| `wikigr/agent/cypher_rag.py` | `_safe_fallback` removed; `generate_cypher` now raises on bad response |
| `wikigr/packs/seed_researcher.py` | `except (RequestException, Exception)` → `except RequestException` |
| `scripts/build_*_pack.py` (45 files) | `process_url()` narrowed to `(requests.RequestException, json.JSONDecodeError)` |

---

## Error Domain Contracts

Four distinct domains; each has its own exception set:

| Domain | Exception Types | Usage |
|---|---|---|
| Anthropic API | `APIConnectionError, APIStatusError, APITimeoutError` | Synthesis, seed identification |
| Kuzu DB | `RuntimeError` | All `conn.execute()` calls |
| Embedding / ML | `RuntimeError, OSError` | Vector ops, pipeline enhancement |
| Initialisation | `RuntimeError, ImportError` | Module / pipeline setup |

Programming bugs (`AttributeError`, `TypeError`, `KeyError`) propagate
unhandled — they indicate incorrect code and must not be swallowed.

---

## Removed Fallbacks

### `_fallback_seed_extraction` (kg_agent.py)

Word-splitting is not an acceptable degradation for semantic seed
identification.  API errors now surface to the caller.

### `_safe_fallback` (cypher_rag.py)

A generic Cypher query is not a valid fallback for a failed generation step.
`ValueError` / `json.JSONDecodeError` now propagate to the caller.

---

## Renamed Internal Pipeline Stages

| Old Name | New Name | Reason |
|---|---|---|
| `"confidence_gated_fallback"` | `"training_only_response"` | Describes what it is, not a fallback |
| `"vector_fallback"` | `"vector_search"` | Not a fallback; primary search path |

---

## Database Design

### Schema Overview

WikiGR uses **Kuzu** (an embedded graph database).  The schema is defined in
`bootstrap/schema/ryugraph_schema.py` and initialised by
`scripts/run_30k_expansion.py`.

#### Node Tables

| Table | Primary Key | Fields |
|---|---|---|
| `Article` | `title` | `title STRING`, `category STRING`, `word_count INT32`, `expansion_state STRING`, `expansion_depth INT32`, `claimed_at TIMESTAMP`, `processed_at TIMESTAMP`, `retry_count INT32` |
| `Section` | `section_id` | `section_id STRING`, `title STRING`, `content STRING`, `word_count INT32`, `level INT32`, `embedding FLOAT[768]` |
| `Category` | `name` | `name STRING`, `article_count INT32` |
| `Entity` | `entity_id` | `entity_id STRING`, `name STRING`, `type STRING`, `description STRING` |
| `Fact` | `fact_id` | `fact_id STRING`, `content STRING` |
| `Chunk` | `chunk_id` | `chunk_id STRING`, `content STRING`, `embedding DOUBLE[768]`, `article_title STRING`, `section_index INT32`, `chunk_index INT32` |

#### Relationship Tables

| Table | Direction | Properties |
|---|---|---|
| `HAS_SECTION` | Article → Section | `section_index INT32` |
| `LINKS_TO` | Article → Article | `link_type STRING` |
| `IN_CATEGORY` | Article → Category | — |
| `HAS_ENTITY` | Article → Entity | — |
| `HAS_FACT` | Article → Fact | — |
| `HAS_CHUNK` | Article → Chunk | `section_index INT32`, `chunk_index INT32` |
| `ENTITY_RELATION` | Entity → Entity | `relation STRING`, `context STRING` |

#### Indexes

| Index | Table | Field | Type | Metric |
|---|---|---|---|---|
| `embedding_idx` | `Section` | `embedding` | HNSW vector | cosine |

### Migrations Required

**None.** The exception handling refactoring is purely a Python code change.
No node tables, relationship tables, properties, or indexes were added,
removed, or modified.

### Data Relationships

```
Article ──HAS_SECTION──► Section  (embedding_idx on Section.embedding)
Article ──LINKS_TO──────► Article
Article ──IN_CATEGORY───► Category
Article ──HAS_ENTITY────► Entity
Article ──HAS_FACT──────► Fact
Article ──HAS_CHUNK─────► Chunk
Entity  ──ENTITY_RELATION► Entity
```

The query pipeline in `kg_agent.py` traverses:

1. **Exact match** — `MATCH (a:Article {title: $q})`
2. **Vector search** — `CALL QUERY_VECTOR_INDEX('Section', 'embedding_idx', $emb, $k)`
3. **Graph traversal** — `MATCH (a)-[:LINKS_TO|HAS_SECTION|HAS_ENTITY*1..2]->(n)`
4. **CypherRAG** — LLM-generated Cypher over the full schema

---

## Tests Updated

| File | Change |
|---|---|
| `tests/agent/test_cypher_rag.py` | `TestFallbackOnApiError` expects raised exceptions; `TestSafeFallback` class removed |
| `tests/agent/test_kg_agent_core.py` | `confidence_gated_fallback` → `training_only_response`; API error uses `APIConnectionError` |
| `tests/agent/test_kg_agent_semantic.py` | `confidence_gated_fallback` → `training_only_response`; `Exception("DB error")` → `RuntimeError("DB error")` |

---

## Security Requirements

### Authentication and Authorization

**No HTTP server / no auth layer required.** WikiGR is an embedded library and
CLI tool. All access is local and governed by OS-level file permissions.

| Concern | Status | Notes |
|---|---|---|
| Anthropic API key | **Pass** — env-var only | `ANTHROPIC_API_KEY` never hardcoded; `ConfigurationError` raised if absent |
| Kuzu DB access | **Pass** — local file | No network port; `read_only=True` accepted at construction; OS permissions govern file access |
| Multi-query expansion | **Pass** — opt-in | `enable_multi_query=False` by default; doc note in `from_connection()` warns about PII/data-residency implications |

**Guideline:** When deploying `KnowledgeGraphAgent` from an external entry point
(e.g. FastAPI), open Kuzu with `read_only=True` unless the endpoint is
explicitly a write path.

---

### Input Validation

#### Already implemented

| Location | Validation | What it prevents |
|---|---|---|
| `kg_agent.py:311` `_validate_cypher()` | MATCH/CALL prefix; blocklist (`CREATE DELETE DROP SET MERGE REMOVE DETACH`); unbounded path pattern (`*` without upper bound) | LLM-generated Cypher executing writes or traversing the full graph |
| `kg_agent.py:490` | `max_results` in range 1–1000 | Integer overflow / resource exhaustion |
| `seed_researcher.py:177–184` | Domain non-empty; rejects `\x00 \n \r` | Log injection; path separator injection |
| `seed_researcher.py:341–342` | URL scheme must be `http` or `https` | Local-file (`file://`) and protocol (`ftp://`) access in `validate_url()` |
| `seed_researcher.py:580–583` | Crawl restricted to same `netloc` | Crawl escaping to external or internal hosts |
| `cypher_rag.py:131` | Empty response raises `ValueError` | Silent pass-through of blank Cypher |

#### Gaps identified (no code change required; document only)

| Risk | Severity | Location | Mitigation |
|---|---|---|---|
| **SSRF via LLM-suggested URLs** (`_extract_via_llm`) | Low | `seed_researcher.py` | LLM-returned URLs are not checked for private/metadata IP ranges (e.g. `169.254.169.254`). Acceptable for a local CLI tool; document if ever exposed as a service. |
| **`except Exception` in strategy loop** | Low | `seed_researcher.py:310` | Broad handler wraps per-strategy failures (`sitemap`, `rss`, `crawl`, `llm`). Could mask SSRF-related `ConnectionError`. Risk is low (the loop is building a URL list, not executing user queries) but flagged for completeness. |
| **URL scheme not validated in build scripts** | Low | `scripts/build_*_pack.py` `load_urls()` | URLs read from `urls.txt` are passed to `WebContentSource.fetch_article()` without a prior scheme check. Mitigation: `urls.txt` files are committed to the repo and reviewed before use. |

---

### Data Protection

| Data | Location | Sensitivity | Controls |
|---|---|---|---|
| Anthropic API key | Environment variable | High | Never logged; `ConfigurationError` message does not echo the key value |
| Knowledge graph content | Kuzu DB files (`data/packs/**/*.db`) | Low — public article text | OS file permissions; no encryption needed |
| Source discovery cache | `~/.wikigr/cache/sources/*.json` | Low — public URL lists | OS file permissions; cache key is MD5 hex (no path traversal risk) |
| User questions | In-memory only | Medium — may contain PII | Not persisted; not sent to API when `enable_multi_query=False` |

**Guideline:** If `KnowledgeGraphAgent` is embedded in a multi-user service, set
`enable_multi_query=False` (the default) unless consent for API-side query
expansion is obtained.

---

### Security Impact of Exception Handling Changes

The narrowing of exception types is a **net security improvement**:

| Before | After | Security effect |
|---|---|---|
| `except Exception` in `kg_agent.py` (×13) | Specific API / DB / ML types | Uncaught `AttributeError` / `TypeError` from bad inputs now propagates visibly instead of being swallowed |
| `_safe_fallback` in `cypher_rag.py` | Removed; callers receive `ValueError` / `json.JSONDecodeError` | Eliminates silent use of a default MATCH query that could bypass intended pipeline logic |
| `_fallback_seed_extraction` in `kg_agent.py` | Removed; API errors surface | Word-splitting cannot be exploited as an alternative input path for seed injection |
| `except (RequestException, Exception)` in `seed_researcher.py` | `except RequestException` | Network errors from adversarial URLs no longer silently suppressed alongside arbitrary exceptions |
| `except Exception` in build scripts | `except (RequestException, json.JSONDecodeError)` | Kuzu / embedding errors now terminate the build with a visible traceback; corrupt partial writes are prevented |

**Key invariant preserved:** `_validate_cypher()` runs on every LLM-generated
query before `conn.execute()` is called. This guard was not touched by the
refactoring and remains the primary defence against prompt-injection → Cypher
injection.

---

### Security Guidelines for Implementation

1. **Always open Kuzu in read-only mode** from web-facing code paths:
   ```python
   KnowledgeGraphAgent(db_path=path, read_only=True)
   ```

2. **Never bypass `_validate_cypher()`** when executing LLM-generated queries.
   Any code path that calls `conn.execute()` with a string derived from LLM
   output must pass through this guard first.

3. **Log at `DEBUG`, not `INFO`, for query content** that may contain user input
   (question text). Avoid f-strings that embed full question text at `INFO`
   level in production deployments.

4. **Treat `urls.txt` as a trusted-input surface.** Because `load_urls()` in
   build scripts does not validate URL schemes, review these files in code
   review the same way you would review SQL query strings.

5. **Do not cache LLM API keys** in process-visible memory longer than
   necessary. The current pattern (instantiating `Anthropic(api_key=...)` once
   per `LLMSeedResearcher`) is correct.

6. **Cache directory permissions** for `~/.wikigr/cache/sources/` are set to
   `700` (owner only). The `mkdir` call uses `mode=0o700` to prevent other
   users on a shared system from reading cached URL lists:
   ```python
   self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
   ```
