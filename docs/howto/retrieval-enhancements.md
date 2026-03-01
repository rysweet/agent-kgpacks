# Retrieval Enhancements: How-To Guide

Complete guide for Issue 211 Improvements 4 and 5 — multi-query retrieval and content quality scoring.

## Overview

Two complementary retrieval improvements ship as opt-in features of `KnowledgeGraphAgent`:

| Enhancement | Flag / Mechanism | Expected Recall/Precision Impact |
|---|---|---|
| **Multi-Query Retrieval** | `enable_multi_query=True` | +15–25% recall |
| **Content Quality Scoring** | Always active when `question` is propagated | Prevents noise injection from stub sections |

These improvements are orthogonal and stack with the existing Phase 1 enhancements (`use_enhancements`, `enable_reranker`, etc.).

---

## Improvement 4 — Multi-Query Retrieval

### Problem

A single query embedding often misses relevant content that uses different vocabulary. For example, a question about "memory safety in systems programming" may not surface articles that discuss "ownership and borrowing" — even though they are highly relevant.

### Solution

When `enable_multi_query=True`, the agent generates 2 alternative phrasings of the question using Claude Haiku and fans out semantic search across all 3 queries. Results are deduplicated by title (keeping the highest similarity score) before synthesis.

### Quick Start

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/physics-expert/physics.db",
    anthropic_api_key="your-key",
    enable_multi_query=True,   # opt-in
)

result = agent.query("What experiments demonstrate quantum entanglement?")
print(result["answer"])
```

### How It Works

```
User question
     │
     ▼
Claude Haiku (claude-haiku-4-5-20251001)
     │  Generates 2 alternative phrasings
     ▼
┌────────────────────────────────────────────────┐
│  Query 1: original question                    │
│  Query 2: alternative phrasing 1               │
│  Query 3: alternative phrasing 2               │
└────────────────────────────────────────────────┘
     │  semantic_search(query, top_k=max_results)
     │  called for each query independently
     ▼
Deduplication by title
     │  highest similarity wins on title collision
     ▼
Sort descending by similarity → return
```

### Deduplication Example

```
Query 1 results:  Article A (0.70), Article B (0.50)
Query 2 results:  Article A (0.90), Article C (0.40)   ← A appears again with higher score
Query 3 results:  Article B (0.30)

Merged (keep highest per title):
  Article A → 0.90
  Article B → 0.50
  Article C → 0.40

Final (sorted):  [Article A (0.90), Article B (0.50), Article C (0.40)]
```

### Graceful Degradation

If the Haiku expansion call fails (network error, API quota), the agent automatically falls back to searching only with the original question. No exception is raised; a warning is logged.

```
WARNING  Multi-query expansion failed: <error message>
```

### Data-Residency Notice

When `enable_multi_query=True`, the user's question (truncated to 500 characters) is sent to the Anthropic API for query expansion. **Keep `enable_multi_query=False` (the default) for deployments with data-residency requirements, PII, or offline constraints.**

### Performance Characteristics

| Metric | Single-Query (default) | Multi-Query |
|---|---|---|
| API calls per query | 0 extra | +1 Haiku call (~50 ms) |
| semantic_search calls | 1 | 3 |
| Additional DB load | — | ~2× |
| Recall improvement | baseline | +15–25% |

---

## Improvement 5 — Content Quality Scoring

### Problem

Short stub sections (e.g., redirect pages, disambiguation headers) are treated the same as rich explanatory sections during synthesis. They waste Claude's context window and dilute useful content.

### Solution

Before including a section in the synthesis context, the agent scores it on a 0.0–1.0 scale. Sections below `CONTENT_QUALITY_THRESHOLD = 0.3` are filtered out.

**This is always active** whenever a `question` is available during synthesis — no flag required.

### Score Formula

```
score = min(1.0, length_score + keyword_score)

length_score   = min(0.8, 0.2 + (word_count / 200) * 0.6)
                 # 0.2 at 20 words, 0.8 at 200+ words

keyword_score  = min(0.2, overlap_ratio * 0.2)
                 # overlap_ratio = |question_keywords ∩ section_words| / |question_keywords|
                 # stop words excluded from question_keywords
```

**Hard cutoff**: sections with fewer than 20 words always return `0.0` and are filtered regardless of keyword overlap.

### Score Examples

| Section | Words | Score | Included? |
|---|---|---|---|
| "See also." | 2 | 0.0 | No — stub cutoff |
| 19 generic words | 19 | 0.0 | No — stub cutoff |
| 20 generic words (no keyword overlap) | 20 | 0.26 | No — below threshold |
| 50 generic words | 50 | 0.35 | Yes |
| 50 words with 3/3 keywords | 50 | 0.55 | Yes |
| 200 words | 200 | 0.80 | Yes |
| 200 words with full keyword overlap | 200 | 1.0 | Yes |

### Stop Words

Common words are excluded from keyword overlap scoring. The full list is available as `KnowledgeGraphAgent.STOP_WORDS` (a `frozenset`). Includes: `a`, `an`, `the`, `and`, `or`, `is`, `are`, `in`, `of`, `to`, `for`, `with`, `by`, `from`, and ~70 more.

### Fallback Behavior

If all sections across **all retrieved articles** are filtered (e.g., every article is a stub-only page), the agent falls back to querying `article.content` for the full source list. This is a global fallback: if at least one article produces at least one passing section, articles whose sections were entirely filtered below threshold will produce no output rather than falling back individually.

---

## Combining Both Enhancements

```python
agent = KnowledgeGraphAgent(
    db_path="data/packs/physics-expert/physics.db",
    anthropic_api_key="your-key",
    use_enhancements=True,      # Phase 1: reranker, multidoc, few-shot
    enable_multi_query=True,    # Improvement 4: multi-query retrieval
    # Improvement 5 is always active during synthesis
)
```

When combined with Phase 1 enhancements, the retrieval pipeline looks like:

```
Question
  │
  ├─[enable_multi_query=True]──► _multi_query_retrieve (3 queries, dedup)
  │
  └─[enable_multi_query=False]─► semantic_search (1 query)
         │
         ▼
    [enable_reranker]──► GraphReranker (PageRank reranking)
         │
         ▼
    _build_synthesis_context
         │
         ▼
    _fetch_source_text(question=question)
         │
         ├─► _score_section_quality per section
         ├─► filter sections below 0.3 threshold
         └─► article.content fallback if all filtered
         │
         ▼
    Claude synthesis (+ few-shot examples if enable_fewshot)
```

---

## Testing

Unit tests for both features are in `tests/agent/test_retrieval_enhancements.py`. Run with:

```bash
pytest tests/agent/test_retrieval_enhancements.py -v
```

To run against the full test suite and verify no regressions:

```bash
pytest tests/ -v
```

---

## See Also

- [Multi-Query Retrieval and Quality Scoring: Design](../concepts/retrieval-enhancements-design.md) — design rationale and architecture
- [Retrieval Enhancements API Reference](../reference/retrieval-enhancements.md) — complete method signatures
- [Phase 1 Pack Enhancements](./phase1-enhancements.md) — existing reranker, multidoc, few-shot features
