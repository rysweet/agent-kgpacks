# Test Infrastructure Reference

Reference documentation for shared test helpers used in the WikiGR agent test suite.

---

## `_make_agent` — KnowledgeGraphAgent Test Factory

**Location**: `tests/agent/test_retrieval_enhancements.py`

```python
def _make_agent(enable_multi_query: bool = False) -> KnowledgeGraphAgent:
```

Constructs a fully stubbed `KnowledgeGraphAgent` instance without invoking `__init__`, making it suitable for fast, isolated unit tests that do not need a real Kuzu database or Anthropic API connection.

### Why `__new__` instead of `__init__`

`KnowledgeGraphAgent.__init__` opens a Kuzu database connection, optionally downloads a cross-encoder model, and may hit the Anthropic API to load few-shot examples. All of these have side effects incompatible with unit tests. By calling `__new__` directly and populating attributes manually, tests get a deterministic, zero-latency stub with no external dependencies.

### Required Attribute Initialization

Every attribute that `KnowledgeGraphAgent` methods read must be present on the stub. Missing attributes cause `AttributeError`, which in some retrieval paths is silently caught — masking real failures and producing false passing tests.

The following table lists all attributes set by `_make_agent` and their purpose:

| Attribute | Value in stub | Why it must be set |
|---|---|---|
| `db` | `None` | Read by several database helper methods; `None` is the "no DB" sentinel |
| `conn` | `MagicMock()` | Kuzu connection; methods call `.execute()` on it — must be a mock, not `None` |
| `claude` | `MagicMock()` | Anthropic client; synthesis and query-expansion calls go through this |
| `synthesis_model` | `"mock-model"` | Model string passed to Claude API calls |
| `_embedding_generator` | `None` | Lazy-initialised embedding generator; `None` means "not loaded" |
| `_plan_cache` | `{}` | Mutable dict; must be a fresh instance per test to avoid cross-test pollution |
| `use_enhancements` | `False` | Master enhancement switch; disabling avoids Phase 1 code paths in basic tests |
| `enable_reranker` | `False` | Phase 1 graph reranker flag |
| `enable_multidoc` | `False` | Phase 1 multi-document synthesis flag |
| `enable_fewshot` | `False` | Phase 1 few-shot injection flag |
| `enable_multi_query` | `enable_multi_query` (param) | Controls whether `_vector_primary_retrieve` fans out via `_multi_query_retrieve` |
| `reranker` | `None` | `GraphReranker` instance or `None`; read by `_apply_reranking` |
| `synthesizer` | `None` | `MultiDocSynthesizer` instance or `None`; read by synthesis path |
| `few_shot` | `None` | `FewShotManager` instance or `None`; read by prompt-building code |
| `cross_encoder` | `None` | `CrossEncoderReranker` instance or `None`; read by `_vector_primary_retrieve` |
| `cypher_rag` | `None` | Cypher pack agent or `None`; read by query planning |
| `token_usage` | `{"input_tokens": 0, "output_tokens": 0, "api_calls": 0}` | Mutable counter dict; must be a fresh instance per test |

### The `cross_encoder` Attribute

`_vector_primary_retrieve` unconditionally reads `self.cross_encoder` to determine whether to apply reranking:

```python
# Simplified from kg_agent.py
if self.cross_encoder is not None:
    candidates = self.cross_encoder.rerank(question, candidates, top_k=max_results)
```

If `cross_encoder` is absent from the stub, Python raises `AttributeError`. Historically, `_vector_primary_retrieve` wrapped its body in a broad `except Exception` block, so this error was swallowed and the method appeared to succeed. Tests that relied on this code path were silently not exercising reranking logic.

Setting `agent.cross_encoder = None` in `_make_agent` ensures:

1. No `AttributeError` is raised during retrieval.
2. The reranking branch is correctly skipped (same behaviour as a production agent with `enable_cross_encoder=False`).
3. If the silent-catch is ever tightened or removed, existing tests remain correct without modification.

### Usage

```python
from tests.agent.test_retrieval_enhancements import _make_agent

# Basic stub — multi-query disabled
agent = _make_agent()

# Stub with multi-query enabled
agent = _make_agent(enable_multi_query=True)
```

Both variants return a `KnowledgeGraphAgent` instance with all optional component attributes initialised to `None` and all boolean flags set to `False` (except `enable_multi_query` which follows the parameter).

### Adding New Attributes

When `KnowledgeGraphAgent.__init__` gains a new instance attribute that is read by any method under test, add a corresponding line to `_make_agent`. Follow the pattern established by the four optional component attributes:

```python
# Pattern: optional component attributes
agent.reranker = None
agent.synthesizer = None
agent.few_shot = None
agent.cross_encoder = None
```

This mirrors how `KnowledgeGraphAgent.__init__` itself sets these attributes when the corresponding `enable_*` flag is `False`.

### Relation to `KnowledgeGraphAgent.__init__`

The stub mirrors the following section of the real constructor (from `wikigr/agent/kg_agent.py`):

```python
# Real __init__ (relevant excerpt)
self.reranker = (
    GraphReranker(self.conn) if use_enhancements and enable_reranker else None
)
self.synthesizer = (
    MultiDocSynthesizer() if use_enhancements and enable_multidoc else None
)
self.few_shot = (
    FewShotManager(few_shot_path or ...) if use_enhancements and enable_fewshot else None
)
self.cross_encoder = (
    CrossEncoderReranker() if use_enhancements and enable_cross_encoder else None
)
```

When all enhancement flags are `False` (as they are in the stub), all four attributes are `None` — exactly what `_make_agent` sets. Any divergence between `__init__` and `_make_agent` is a test infrastructure bug.

---

## Related Documentation

- [Retrieval Enhancements API](./retrieval-enhancements.md) — `_multi_query_retrieve`, `_score_section_quality`, and related methods tested by `test_retrieval_enhancements.py`
- [Cross-Encoder Reranker](./module-docs/cross-encoder-reranker.md) — the `CrossEncoderReranker` class that `cross_encoder` holds in production
- [Phase 1 Enhancements API](./phase1-enhancements.md) — `reranker`, `synthesizer`, and `few_shot` component APIs
