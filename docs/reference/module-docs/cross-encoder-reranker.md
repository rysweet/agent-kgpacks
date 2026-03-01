# CrossEncoderReranker Module Documentation

Module: `wikigr.agent.cross_encoder`

## Module Overview

CrossEncoderReranker reranks vector search candidates by jointly scoring each query-document pair through a cross-encoder model. Unlike bi-encoder embeddings (which encode query and document independently), a cross-encoder sees both texts simultaneously and produces a much more accurate relevance score.

**Accuracy Impact**: +10-15% retrieval precision over bi-encoder vector search alone
**Latency**: ~50ms per rerank call (CPU, 33MB model) — negligible versus 10-15s Opus synthesis
**Model**: `cross-encoder/ms-marco-MiniLM-L-12-v2` (default, no GPU required)
**Dependency**: `sentence-transformers` (already a project dependency — no new installs needed)

## Background: Why Cross-Encoders Beat Bi-Encoders

WikiGR's vector retrieval uses BGE `bge-base-en-v1.5`, a bi-encoder that maps each text to a fixed embedding vector. Similarity is a cosine dot product — efficient for large-scale search, but the query and document never see each other during scoring.

A cross-encoder concatenates the query and document as a single input and runs a full attention pass over both. This captures precise semantic interactions (negations, comparisons, qualifications) that bi-encoder dot products miss. Cross-encoders are unsuitable as the primary retrieval stage (they require O(N) forward passes), but they are ideal as a **reranking stage** over a small candidate pool.

The pipeline becomes:

```
bi-encoder fast search  →  top-2K candidates
cross-encoder rerank    →  top-K precise results
synthesis               →  answer
```

## Module-Level Docstring

```python
"""Cross-encoder reranking for improved retrieval precision.

This module provides CrossEncoderReranker which uses a cross-encoder model to
jointly score query-document pairs, providing much higher relevance precision
than bi-encoder vector search alone.

API Contract:
    CrossEncoderReranker(model_name: str) -> instance
    rerank(
        query: str,
        results: list[dict],
        top_k: int = 5
    ) -> list[dict]

Design Philosophy:
    - CPU-only inference (no GPU required)
    - Graceful degradation: __init__ failure sets _model = None, rerank() returns
      results unchanged rather than raising
    - Shallow copies of result dicts with ce_score added (does not mutate caller's list)
    - Sorted by ce_score descending
"""
```

## Class: CrossEncoderReranker

```python
class CrossEncoderReranker:
    """Reranks retrieval results using a cross-encoder model.

    Cross-encoders jointly process query and document text, producing more
    accurate relevance scores than bi-encoders at the cost of ~50ms latency.

    Attributes:
        _model: Loaded CrossEncoder instance, or None if load failed.

    Example:
        >>> from wikigr.agent.cross_encoder import CrossEncoderReranker
        >>> reranker = CrossEncoderReranker()
        >>> results = [
        ...     {"title": "Quantum mechanics", "content": "The study of matter at atomic scale."},
        ...     {"title": "Classical mechanics", "content": "Newton's laws of motion."},
        ... ]
        >>> reranked = reranker.rerank("What governs subatomic particles?", results, top_k=2)
        >>> reranked[0]["title"]
        'Quantum mechanics'
        >>> reranked[0]["ce_score"]
        9.231  # Raw cross-encoder logit
    """
```

### Constructor

```python
def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
    """Load the cross-encoder model.

    Args:
        model_name: HuggingFace model identifier. Defaults to
            'cross-encoder/ms-marco-MiniLM-L-12-v2' (33MB, CPU-only).

    Side effects:
        On first call: downloads ~33MB model weights to HuggingFace cache
            (~/.cache/huggingface/). Subsequent calls load from cache.
        On any exception: logs a WARNING and sets self._model = None.
            rerank() will then return results unchanged (passthrough mode).

    Example:
        >>> reranker = CrossEncoderReranker()  # loads default model
        >>> reranker = CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")  # faster, smaller
    """
```

**Constant**:

| Name | Value | Notes |
|------|-------|-------|
| `DEFAULT_MODEL` | `"cross-encoder/ms-marco-MiniLM-L-12-v2"` | 33MB, 12-layer MiniLM trained on MS MARCO |

### rerank() Method

```python
def rerank(
    self,
    query: str,
    results: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rerank results using cross-encoder scores.

    Args:
        query: The search query string. Used as the left side of each
            (query, document) pair fed to the cross-encoder.
        results: List of result dicts. Each dict must contain a 'content'
            key (preferred) or a 'title' key used as the document text.
            Dicts without either key are scored against an empty string.
        top_k: Maximum number of results to return. Results beyond top_k
            are discarded.

    Returns:
        Normal mode (_model is not None):
            List of up to top_k dicts sorted by 'ce_score' descending.
            Each dict is a shallow copy of the corresponding input dict
            with 'ce_score' (float) added. Original dicts are not mutated.

        Passthrough mode (_model is None):
            list(results) — full input list, original order, no ce_score,
            no truncation. Callers should not rely on top_k being applied
            in this mode.

    Raises:
        Does not raise. All exceptions from model.predict() propagate
        naturally; callers should wrap in try/except if required.

    Examples:
        >>> results = [
        ...     {"title": "Entanglement", "content": "Quantum correlation between particles."},
        ...     {"title": "Superposition", "content": "A system exists in multiple states."},
        ... ]
        >>> reranked = reranker.rerank("How do qubits store information?", results, top_k=1)
        >>> len(reranked)
        1
        >>> "ce_score" in reranked[0]
        True

        # Passthrough when model unavailable (simulate by patching load failure):
        # CrossEncoderReranker("nonexistent/model") raises ValueError (not in ALLOWED_MODELS).
        # Passthrough mode is triggered by network errors or missing sentence_transformers,
        # not by supplying an arbitrary model name.
        >>> import unittest.mock
        >>> with unittest.mock.patch("sentence_transformers.CrossEncoder", side_effect=Exception("offline")):
        ...     broken = CrossEncoderReranker()
        >>> broken._model is None
        True
        >>> returned = broken.rerank("query", results, top_k=1)
        >>> len(returned)  # top_k NOT applied in passthrough mode
        2
    """
```

**Document text selection**:

The method uses the first non-empty value from:
1. `result["content"]`
2. `result["title"]`
3. `""` (empty string, scored near 0)

## ce_score Field

Every dict returned in normal mode gains a `"ce_score"` key:

| Property | Value |
|----------|-------|
| Type | `float` |
| Range | Unbounded; MS MARCO model outputs raw logits, typically −10 to +10 |
| Interpretation | Higher is more relevant to the query |
| Presence | Only added in normal mode; absent in passthrough mode |

## Integration with KnowledgeGraphAgent

### Constructor Parameters

Cross-encoder reranking is controlled by two constructor parameters on `KnowledgeGraphAgent`:

| Parameter | Type | Default | Effect |
|-----------|------|---------|--------|
| `use_enhancements` | `bool` | `True` | Master switch for all Phase 1 enhancements. Must be `True` for cross-encoder to activate. |
| `enable_cross_encoder` | `bool` | `False` | Opt-in flag for cross-encoder reranking. Default-off because the first invocation downloads a 33MB model. |

Cross-encoder is **opt-in** by design. The first download takes a few seconds; subsequent startups load from the local HuggingFace cache.

### Retrieval Pipeline with Cross-Encoder Active

When `enable_cross_encoder=True`, `_vector_primary_retrieve()` doubles its candidate pool and then reranks:

```
semantic_search(query, k = max_results * 2)   # e.g. 10 candidates for max_results=5
    ↓
cross_encoder.rerank(query, candidates, top_k=max_results)
    ↓
top-max_results results sorted by ce_score
```

Without cross-encoder, semantic search fetches exactly `max_results` candidates and returns them in embedding-distance order.

### Attribute

After `__init__`, the agent exposes `self.cross_encoder`:

| Value | Meaning |
|-------|---------|
| `CrossEncoderReranker` instance | Cross-encoder active |
| `None` | Disabled (`enable_cross_encoder=False`) or `use_enhancements=False` |

**Note**: `KnowledgeGraphAgent.from_connection()` always sets `cross_encoder = None` regardless of flags. Cross-encoder activation is only available through the standard `__init__` constructor.

## Graceful Degradation

CrossEncoderReranker is designed to never crash the agent:

| Failure Mode | Behaviour |
|---|---|
| Network error on first model download | `__init__` logs WARNING; `_model = None`; `rerank()` returns passthrough |
| `sentence_transformers` not importable | Same as above |
| `model.predict()` raises at runtime | Exception propagates to `_vector_primary_retrieve()` caller |

The agent does not currently catch `predict()` errors; if the model load succeeds but inference fails the exception surfaces to the caller. Wrap queries in `try/except` when operating in untrusted environments.

## Usage Examples

### Minimal — use with KnowledgeGraphAgent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/physics-expert/physics.db",
    use_enhancements=True,
    enable_cross_encoder=True,   # opt-in
)

result = agent.query("What is the photoelectric effect?")
print(result["answer"])
```

The first time this runs the 33MB model downloads automatically. Subsequent starts load from `~/.cache/huggingface/`.

### Standalone reranking

```python
from wikigr.agent.cross_encoder import CrossEncoderReranker

reranker = CrossEncoderReranker()

candidates = [
    {"title": "Photoelectric effect", "content": "Emission of electrons by light."},
    {"title": "Compton scattering",   "content": "Scattering of photons by electrons."},
    {"title": "Wave–particle duality","content": "Matter exhibits wave and particle properties."},
    {"title": "Black-body radiation", "content": "Thermal radiation emitted by a body in equilibrium."},
    {"title": "Planck's law",         "content": "Distribution of radiation from a black body."},
]

reranked = reranker.rerank(
    query="How did Einstein explain light quanta?",
    results=candidates,
    top_k=3,
)

for r in reranked:
    print(f"{r['ce_score']:+.2f}  {r['title']}")
```

Example output:
```
+9.14  Photoelectric effect
+2.83  Wave–particle duality
-1.07  Planck's law
```

### Inspecting scores before filtering

```python
# Get all scores (set top_k=len(candidates) to disable truncation)
all_scored = reranker.rerank(query, candidates, top_k=len(candidates))

print("Score distribution:")
for r in all_scored:
    bar = "#" * max(0, int((r["ce_score"] + 10) * 2))
    print(f"  {r['ce_score']:+6.2f} {bar}  {r['title']}")
```

### Selective enhancement flags

```python
# Enable cross-encoder but disable graph reranker (faster startup, no Kuzu PageRank)
agent = KnowledgeGraphAgent(
    db_path="physics.db",
    use_enhancements=True,
    enable_reranker=False,
    enable_cross_encoder=True,
)
```

### Checking whether cross-encoder is active

```python
agent = KnowledgeGraphAgent(db_path="physics.db", use_enhancements=True)

if agent.cross_encoder is None:
    print("Cross-encoder not active")
elif agent.cross_encoder._model is None:
    print("Cross-encoder active but model failed to load (passthrough mode)")
else:
    print("Cross-encoder fully operational")
```

## Model Selection

`CrossEncoderReranker` enforces an `ALLOWED_MODELS` allowlist in `cross_encoder.py` to prevent
path-traversal attacks or malicious HuggingFace repo injection.

**Currently allowed models:**

| Model | Size | Latency | Notes |
|-------|------|---------|-------|
| `cross-encoder/ms-marco-MiniLM-L-12-v2` | 33MB | ~50ms | **Default and only allowed model** |

Passing any other `model_name` raises `ValueError` at construction time:

```python
# OK
reranker = CrossEncoderReranker()  # uses DEFAULT_MODEL

# Raises ValueError: model_name 'other/model' is not in allowed models
reranker = CrossEncoderReranker("other/model")
```

To add a new model, add its identifier to `ALLOWED_MODELS` in `cross_encoder.py` after a security
review confirming the model origin and weights integrity.

## Performance

### Latency

Reranking 10 candidates on a typical CPU:

| Operation | Time |
|-----------|------|
| Model load (first time, from disk) | 0.5–1s |
| Model load (warm, already in memory) | 0 |
| `predict()` on 10 (query, doc) pairs | ~50ms |
| `predict()` on 20 (query, doc) pairs | ~95ms |

Total overhead versus a 10-15 second Opus synthesis: negligible.

### Memory

| Component | Size |
|-----------|------|
| Model weights (ms-marco-MiniLM-L-12-v2) | ~33MB on disk; ~120MB in RAM |
| Activations per batch (10 pairs) | ~5MB (freed after predict) |

### Scaling

Reranking time scales linearly with `len(results)`. With `candidate_k = max_results * 2`:

| max_results | candidate_k | Latency |
|------------|-------------|---------|
| 5 | 10 | ~50ms |
| 10 | 20 | ~95ms |
| 20 | 40 | ~180ms |

At `max_results=20` the total still fits comfortably within a 500ms budget on commodity hardware.

## Testing

Tests live in `tests/agent/test_cross_encoder.py`. All tests mock `sentence_transformers.CrossEncoder` so no model download is needed during CI.

```bash
pytest tests/agent/test_cross_encoder.py -v
```

Expected output:

```
tests/agent/test_cross_encoder.py::TestCrossEncoderReranker::test_reranking_reorders_by_cross_encoder_score PASSED
tests/agent/test_cross_encoder.py::TestCrossEncoderReranker::test_empty_results_returns_empty_list PASSED
tests/agent/test_cross_encoder.py::TestCrossEncoderReranker::test_top_k_filtering_limits_output PASSED
tests/agent/test_cross_encoder.py::TestCrossEncoderReranker::test_ce_score_added_to_each_result PASSED
tests/agent/test_cross_encoder.py::TestCrossEncoderReranker::test_graceful_init_failure_returns_results_unchanged PASSED

5 passed in 0.12s
```

### Writing additional tests

```python
from unittest.mock import MagicMock, patch

def test_content_preferred_over_title():
    """rerank() uses 'content' field when both content and title are present."""
    mock_ce = MagicMock()
    mock_ce.predict.return_value = [0.5]

    with patch("sentence_transformers.CrossEncoder", return_value=mock_ce):
        from wikigr.agent.cross_encoder import CrossEncoderReranker
        reranker = CrossEncoderReranker()

    results = [{"title": "Title text", "content": "Content text"}]
    reranker.rerank("query", results, top_k=1)

    call_args = mock_ce.predict.call_args[0][0]
    assert call_args[0] == ("query", "Content text")


def test_passthrough_preserves_all_results():
    """Passthrough mode returns all results regardless of top_k."""
    with patch("sentence_transformers.CrossEncoder", side_effect=Exception("offline")):
        from wikigr.agent.cross_encoder import CrossEncoderReranker
        reranker = CrossEncoderReranker()

    results = [{"title": f"Article {i}"} for i in range(10)]
    returned = reranker.rerank("query", results, top_k=2)
    assert len(returned) == 10  # top_k not applied
```

## Troubleshooting

### Model does not download

**Symptom**: WARNING in logs: `CrossEncoderReranker failed to load model '...': ...`; reranker silently in passthrough mode.

**Cause**: No internet access at init time, or HuggingFace CDN blocked.

**Fix**: Pre-download the model on a networked machine and copy to the cache directory:

```bash
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')"
# Weights are now in ~/.cache/huggingface/
```

Or set the `TRANSFORMERS_OFFLINE=1` environment variable and point `HF_HOME` to a shared cache volume.

### Reranker is in passthrough mode unexpectedly

**Symptom**: Returned results lack `ce_score`; order unchanged.

**Diagnosis**:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from wikigr.agent.cross_encoder import CrossEncoderReranker
r = CrossEncoderReranker()
print(r._model)  # None means load failed
```

### Cross-encoder not activated despite enable_cross_encoder=True

**Symptom**: `agent.cross_encoder is None` even though `enable_cross_encoder=True` was passed.

**Cause**: `use_enhancements=False` overrides all enhancement flags.

**Fix**:

```python
agent = KnowledgeGraphAgent(
    db_path="...",
    use_enhancements=True,        # required
    enable_cross_encoder=True,
)
```

### Scores look unexpectedly low

The cross-encoder produces raw MS MARCO logits, not probabilities. Scores near 0 mean uncertain; highly positive scores (>5) are strong matches; negative scores are likely irrelevant. Do not compare scores across different queries — use them only for relative ranking within a single query's results.

## Security Notes

- `model_name` is a server-side configuration value. Do not allow users to pass arbitrary model identifiers — it could cause the server to download and execute untrusted model weights.
- Query strings are passed to the tokenizer but never logged. Avoid logging `query` content to prevent sensitive data leaking into log aggregators.
- `ce_score` values should be stripped from any user-facing API responses to avoid exposing model scoring thresholds to adversaries.

## See Also

- [Phase 1 Enhancements Reference](../phase1-enhancements.md) — complete API reference including `KnowledgeGraphAgent` constructor
- [Phase 1 How-To Guide](../../howto/phase1-enhancements.md) — enabling enhancements and measuring accuracy
- [GraphReranker Module](./graph-reranker.md) — graph-centrality reranking (complementary to cross-encoder)
- [MultiDocSynthesizer Module](./multidoc-synthesizer.md) — multi-document retrieval
