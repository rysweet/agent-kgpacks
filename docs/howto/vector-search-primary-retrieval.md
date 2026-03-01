# Vector Search as Primary Retrieval: How-To Guide

Guide to using the improved retrieval pipeline that uses semantic vector search as the primary retrieval path, with A/B testing flags for individual enhancement components.

> **Note**: This guide covers features from [PR #168](https://github.com/rysweet/wikigr/pull/168).

## Overview

**Before (Phase 2)**: LLM-generated Cypher was the primary retrieval. Generated bad Cypher for ~30% of questions.

**After (Phase 3)**: Vector search on `Section.embedding` is the primary and only retrieval path. When vector search returns results, a confidence gate checks `max_similarity` before injecting pack context. When vector search returns no results, hybrid retrieval fills in.

**Impact**: Reduces the "no relevant articles found" failure rate from ~30% to ~5%.

## Quick Start

### Use Vector Search Primary (Default)

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/physics-expert/pack.db",
    anthropic_api_key="your-key",
)

result = agent.query("What is Bernoulli's principle?")
print(result["answer"])
# query_type is one of: "vector_search", "confidence_gated_fallback", "vector_fallback"
print(f"Retrieved via: {result.get('query_type')}")
```

### Sparse Graph Detection (Rust Pack Fix)

The `GraphReranker` now automatically detects sparse graphs and disables centrality scoring:

```python
agent = KnowledgeGraphAgent(
    db_path="data/packs/rust-expert/pack.db",
    use_enhancements=True,
)
# Log will show: "Sparse graph detected (avg 0.2 links/article), disabling centrality component"
# This prevents the -1.2 accuracy regression seen with the Rust pack
```

Wikipedia-sourced packs (physics) have rich `LINKS_TO` edges.
Web/documentation packs (Rust, .NET) have sparse edges — centrality is auto-disabled for these.

## A/B Testing Individual Enhancement Components

Disable specific components to measure their isolated impact:

```python
# Test without graph reranker
agent = KnowledgeGraphAgent(
    db_path="data/packs/physics-expert/pack.db",
    use_enhancements=True,
    enable_reranker=False,   # disable centrality reranking
    enable_multidoc=True,    # keep multi-doc expansion
    enable_fewshot=True,     # keep few-shot examples
)
```

### CLI Flags for Evaluation Scripts

`run_enhancement_evaluation.py` targets the physics pack by default and supports disabling
individual components (A/B testing flags added in PR #168):

```bash
# Full enhancement evaluation (all components enabled)
python scripts/run_enhancement_evaluation.py

# Disable individual components for A/B testing
python scripts/run_enhancement_evaluation.py --disable-multidoc --disable-fewshot
python scripts/run_enhancement_evaluation.py --disable-reranker

# Compare all packs with/without reranker
python scripts/run_all_packs_evaluation.py --sample 10 --disable-reranker
```

## Retrieval Pipeline Flow

```
Question
   │
   ▼
Vector Search (primary)
   │  CALL QUERY_VECTOR_INDEX('Section', 'embedding_idx', $query, K)
   │  → (results, max_similarity)
   │
   ├─ results found
   │    ├─ max_similarity >= 0.5 → inject KG context → full pipeline → answer
   │    │                          (title lookup + hybrid retrieval + enhancements + synthesis)
   │    └─ max_similarity < 0.5  → confidence gate → minimal synthesis → answer
   │                               (Claude answers from own knowledge, no KG sections)
   │
   └─ no results → vector_fallback
         │
         ▼
   Hybrid retrieval fills in (keyword + graph signals)
         │
         ▼
   Enhancements (if use_enhancements=True)
   │  ├─ Graph centrality (disabled if avg_links < 2.0)
   │  ├─ Multi-doc expansion
   │  └─ Few-shot examples
         │
         ▼
   Claude synthesis → answer
```

> **Confidence gate**: Even when vector search returns results, if `max_similarity < 0.5` the agent skips all pack context and calls `_synthesize_answer_minimal()` instead. This prevents low-relevance KG sections from misleading Claude on questions outside the pack's domain. See [Confidence-Gated Context Injection](confidence-gated-context-injection.md).

## When to Use Which Mode

| Pack Type | Source | Recommendation |
|-----------|--------|----------------|
| Physics, Wikipedia packs | Wikipedia | All enhancements ON |
| Rust, .NET, documentation | Web/docs | `enable_reranker` auto-disabled by sparse graph detection |
| Azure Lighthouse, Security Copilot | Microsoft docs | Test with `--disable-reranker` first |

## See Also

- [Confidence-Gated Context Injection](confidence-gated-context-injection.md) — how `CONTEXT_CONFIDENCE_THRESHOLD` prevents low-relevance KG sections from being injected
- [Phase 1 Enhancements](phase1-enhancements.md) — GraphReranker, MultiDocSynthesizer, FewShotManager
- [Evaluation Scripts](../reference/evaluation-scripts.md) — how to run evaluations
- [Pack Content Quality](dotnet-content-quality.md) — improving .NET pack accuracy
