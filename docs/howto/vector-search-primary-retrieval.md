# Vector Search as Primary Retrieval: How-To Guide

Guide to using the improved retrieval pipeline that uses semantic vector search as the primary retrieval path, with A/B testing flags for individual enhancement components.

## Overview

**Before (Phase 2)**: LLM-generated Cypher was the primary retrieval. Generated bad Cypher for ~30% of questions.

**After (Phase 3)**: Vector search on `Section.embedding` is primary. LLM Cypher is a fallback only when vector similarity is low (< 0.6).

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
print(f"Retrieved via: {result.get('query_type')}")  # "vector_search" or "llm_cypher_fallback"
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

```bash
# Baseline (no enhancements)
python scripts/run_enhancement_evaluation.py --pack physics-expert

# With all enhancements
python scripts/run_enhancement_evaluation.py --pack physics-expert --use-enhancements

# Test reranker in isolation
python scripts/run_enhancement_evaluation.py --pack physics-expert \
    --use-enhancements --disable-multidoc --disable-fewshot

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
   │  → max_similarity
   │
   ├─ similarity >= 0.6 → use vector results
   │
   └─ similarity < 0.6 → LLM Cypher fallback
         │
         ▼
     Claude generates Cypher → execute → results
         │
         ▼
   Adaptive RRF (if use_enhancements=True)
   │  ├─ Graph centrality (disabled if avg_links < 2.0)
   │  ├─ Multi-doc expansion
   │  └─ Few-shot examples
         │
         ▼
   Claude synthesis → answer
```

## When to Use Which Mode

| Pack Type | Source | Recommendation |
|-----------|--------|----------------|
| Physics, Wikipedia packs | Wikipedia | All enhancements ON |
| Rust, .NET, documentation | Web/docs | `enable_reranker` auto-disabled by sparse graph detection |
| Azure Lighthouse, Security Copilot | Microsoft docs | Test with `--disable-reranker` first |

## See Also

- [Phase 1 Enhancements](phase1-enhancements.md) — GraphReranker, MultiDocSynthesizer, FewShotManager
- [Evaluation Scripts](../reference/evaluation-scripts.md) — how to run evaluations
- [Pack Content Quality](dotnet-content-quality.md) — improving .NET pack accuracy
