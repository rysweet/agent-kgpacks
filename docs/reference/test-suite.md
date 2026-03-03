# KG Agent Test Suite Reference

Reference for the unit and integration tests covering `KnowledgeGraphAgent` in `tests/agent/`.

## Quick Start

```bash
# Run all agent tests (no database required)
pytest tests/agent/ -v

# Expected output (without data/wikigr_30k.db present):
# 44 passed, 27 skipped
```

All unit tests run offline — no LadybugDB database, no Anthropic API calls. The 27 skipped tests require an optional integration database (`data/wikigr_30k.db`) and are silently skipped when it is absent.

---

## Test Files

### `test_kg_agent_core.py` — Core method unit tests

Tests five `KnowledgeGraphAgent` methods using fully mocked LadybugDB connections and Claude API. No real database or network I/O.

> **Note:** The module docstring at the top of this file still lists `_execute_query` and `_execute_fallback_query` as targets — this is stale comment-only technical debt from a dead code cleanup. Those methods no longer exist in production; see [Removed test targets](#removed-test-targets) below.

**Test classes:**

| Class | Method Under Test | Coverage |
|-------|------------------|----------|
| `TestSafeJsonLoads` | `_safe_json_loads` (module-level) | Valid JSON, invalid JSON, dict passthrough, non-string types, empty string |
| `TestFetchSourceText` | `_fetch_source_text` | Returns section text, empty titles, article content fallback, DB errors, truncation at 3000 chars, `max_articles` slicing |
| `TestBuildSynthesisContext` | `_build_synthesis_context` | Sources/entities/facts inclusion, few-shot example injection, empty results |
| `TestHybridRetrieve` | `_hybrid_retrieve` | Combined vector + keyword signals, vector failure fallback, all-DB-failure graceful return, `keyword_weight` affects ranking |
| `TestConfidenceGatedContextInjection` | `query()`, `_synthesize_answer_minimal()` | Low similarity triggers confidence gate, high similarity runs normal pipeline, minimal synthesis calls Claude without KG context, API error returns fallback string, exact threshold boundary (0.5 is NOT below threshold), empty Claude response returns dedicated fallback string |

**Fixture pattern:**

```python
from unittest.mock import MagicMock, patch
from wikigr.agent.kg_agent import KnowledgeGraphAgent, _safe_json_loads

def _make_agent() -> KnowledgeGraphAgent:
    """Build a KnowledgeGraphAgent with fully mocked internals."""
    agent = KnowledgeGraphAgent.__new__(KnowledgeGraphAgent)
    agent.db = None
    agent.conn = MagicMock()
    agent.claude = MagicMock()
    # ... other required attrs
    return agent
```

The `_make_agent()` helper bypasses `__init__` using `__new__`, then manually assigns mock attributes. This avoids LadybugDB import-time side effects and keeps tests deterministic.

---

### `test_kg_agent_semantic.py` — Semantic search and retrieval pipeline tests

Tests `semantic_search`, `_vector_primary_retrieve`, and the `query()` retrieval pipeline. Uses the pytest `agent` fixture which patches `real_ladybug` and `Anthropic` at import time.

**Test classes:**

| Class | Focus |
|-------|-------|
| `TestSemanticSearchFastPath` | Article title matches an existing node — reuses stored embedding, no `EmbeddingGenerator` instantiated |
| `TestSemanticSearchFreeText` | Non-title query generates an on-the-fly embedding, lazy initialization, deduplication of multiple sections from the same article |
| `TestSemanticSearchValidation` | Rejects invalid `top_k` (0, >500, non-int), raises `RuntimeError` after `close()`, `close()` clears `_embedding_generator` |
| `TestVectorPrimaryRetrieval` | High confidence returns results, empty vector returns `(None, 0.0)`, DB exception returns `(None, 0.0)`, low distance returns results with `max_sim < 0.6` |
| `TestABTestingFlags` | `enable_reranker/multidoc/fewshot` constructor flags, `from_connection()` defaults |

**Behavioral contract assertions:**

The two tests `test_query_skips_llm_when_high_confidence` and `test_query_never_calls_llm_cypher` assert on the observable output field `result["query_type"]`, not on whether internal private methods were or were not called:

```python
def test_query_skips_llm_when_high_confidence(self, agent):
    # ... set up high-similarity vector results ...
    result = agent.query("physics question")
    assert result["query_type"] == "vector_search"   # output contract

def test_query_never_calls_llm_cypher(self, agent):
    # ... set up low-similarity vector results (distance=0.9, similarity=0.1) ...
    result = agent.query("obscure query")
    assert result["query_type"] == "confidence_gated_fallback"  # output contract
```

This approach tests the *behavior contract* (what the API returns) rather than the *implementation detail* (which internal method ran), making the tests robust to future refactoring.

---

### `test_kg_agent_queries.py` — Integration tests (DB-dependent)

End-to-end tests that query a live `KnowledgeGraphAgent` against the 30K Wikipedia article database. These tests verify the full pipeline from question to synthesized answer.

**Skip guard:**

```python
pytestmark = pytest.mark.skipif(
    not os.path.exists("data/wikigr_30k.db"),
    reason="data/wikigr_30k.db not found — skipping DB-dependent tests",
)
```

All tests in this file skip automatically when `data/wikigr_30k.db` is absent. This prevents `kuzu.Error` (via `real_ladybug`) and `FileNotFoundError` in CI environments where the database is not available.

**Test levels:**

| Level | Class | Focus |
|-------|-------|-------|
| 1 | `TestLevel1_SimpleRetrieval` | Entity lookup, article existence, fact retrieval |
| 2 | `TestLevel2_SemanticSearch` | Concept proximity, category search |
| 3 | `TestLevel3_RelationshipTraversal` | Entity paths, founder queries, indirect connections |
| 4 | `TestLevel4_MultiHopReasoning` | Transitive relationships, concept comparison |
| 5 | `TestLevel5_TemporalAndCausal` | Cause/effect, prerequisite knowledge |
| 6 | `TestLevel6_ConstraintSatisfaction` | Multi-constraint search, negation |
| 7 | `TestLevel7_Reasoning` | Contradiction detection, knowledge gap identification, analogical reasoning |
| 8 | `TestLevel8_Compositional` | Filter+rank chaining, aggregate+compare, nested sub-queries |
| — | `TestPerformance` | Simple query < 5s, complex query < 15s, semantic search < 3s |

Four tests within this file are individually marked `@pytest.mark.skip(reason=...)` — unconditionally, not conditionally — because they require data not present even in the full 30K DB (e.g., vector index, temporal/historical data). These are separate from the 27-skip count above: the 27 skips come entirely from the module-level `pytestmark` guard when the database is absent; these 4 would additionally skip even when the database is present.

---

### Other test files

| File | Focus |
|------|-------|
| `test_cypher_rag.py` | Cypher RAG pack retrieval augmentation |
| `test_cross_encoder.py` | `CrossEncoderReranker` joint query-document scoring |
| `test_retrieval_enhancements.py` | `GraphReranker`, `MultiDocSynthesizer`, `FewShotManager` |
| `test_kg_agent_benchmark.py` | Benchmark/eval harness |
| `test_kg_agent_gold.py` | Gold standard accuracy tests |
| `test_seed_agent.py` | LLM seed researcher agent |

---

## Expected Test Output

### Without `data/wikigr_30k.db` (CI / local dev)

```
pytest tests/agent/ -q

...
44 passed, 27 skipped in X.XXs
```

- **44 passed**: All unit tests and mock-based tests (24 from `test_kg_agent_core.py`, 20 from `test_kg_agent_semantic.py`)
- **27 skipped**: All 27 tests in `test_kg_agent_queries.py` — the module-level `pytestmark` guard skips the entire file when `data/wikigr_30k.db` is absent
- **0 failed**: No test should fail in a clean environment without the DB

### With `data/wikigr_30k.db` present

Integration tests in `test_kg_agent_queries.py` execute against the live database. Results depend on database content and Anthropic API availability.

---

## Design Notes

### Removed test targets

The following methods were removed from production code during a dead code cleanup and are no longer tested:

| Removed method | Former test location |
|---------------|---------------------|
| `_validate_cypher` | `test_validate_cypher.py` (deleted) |
| `_execute_query` | `TestExecuteQuery` in `test_kg_agent_core.py` (removed) |
| `_execute_fallback_query` | `TestExecuteFallbackQuery` in `test_kg_agent_core.py` (removed) |
| `_plan_query` | Previously asserted as "not called" in `test_kg_agent_semantic.py` (assertions replaced with output contracts) |

These test classes and files were removed when their production targets were deleted. Re-introducing these methods would require writing new tests.

### Mock strategy

Unit tests in `test_kg_agent_core.py` use `KnowledgeGraphAgent.__new__` to bypass `__init__` and assign mock attributes directly. This is intentional:

- Avoids LadybugDB database file requirements
- Eliminates Anthropic API key requirements
- Keeps tests fast (no I/O)
- Tests individual methods in full isolation

Tests in `test_kg_agent_semantic.py` use the `agent` pytest fixture, which patches `real_ladybug` and `Anthropic` at module level during construction. This tests the constructor path and the interaction between `__init__` and the mocked dependencies.

### Security

- All test data uses synthetic/anonymized article titles and content (e.g., "Quantum Mechanics", "Deep Learning")
- No real API keys are used in any test
- `data/wikigr_30k.db` is covered by `data/**/*.db` in `.gitignore` — no accidental commit of the database file

---

## See Also

- [KG Agent API Reference](kg-agent-api.md) — full `KnowledgeGraphAgent` API
- [Confidence-Gated Context Injection](../howto/confidence-gated-context-injection.md) — how `CONTEXT_CONFIDENCE_THRESHOLD` works
- [Vector Search as Primary Retrieval](../howto/vector-search-primary-retrieval.md) — full retrieval pipeline
- [Phase 1 Enhancements](../howto/phase1-enhancements.md) — GraphReranker, MultiDocSynthesizer, FewShotManager
