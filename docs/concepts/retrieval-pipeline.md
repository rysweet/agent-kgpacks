# Retrieval Pipeline

This page provides a detailed step-by-step walkthrough of the retrieval pipeline, from the moment a question enters the system to the final synthesized answer.

## Pipeline Overview

```
Question
  │
  ▼
1. Query Expansion (optional)
  │
  ▼
2. Vector Search
  │
  ▼
3. Confidence Gate
  │
  ▼
4. Cross-Encoder Reranking (optional)
  │
  ▼
5. Graph Reranking
  │
  ▼
6. Multi-Document Expansion
  │
  ▼
7. Content Quality Filtering
  │
  ▼
8. Few-Shot Example Injection
  │
  ▼
9. Claude Synthesis
  │
  ▼
Answer + Sources
```

## Step 1: Query Expansion (Multi-Query Retrieval)

**Flag**: `enable_multi_query=True` (opt-in, default False)

A single query embedding may miss content that uses different vocabulary. When enabled, Claude Haiku generates 2 alternative phrasings of the question.

**Example:**

```
Original:  "What experiments demonstrate quantum entanglement?"
Alt 1:     "Which laboratory tests have proven entangled particle behavior?"
Alt 2:     "How has quantum correlation been experimentally verified?"
```

All 3 queries proceed to vector search independently. Results are deduplicated by article title, keeping the highest similarity score for each title.

**Technical details:**

- Question truncated to 500 characters before sending to Haiku (prompt injection defense)
- Each alternative capped at 300 characters
- If the Haiku call fails, the pipeline proceeds with only the original query (graceful degradation)
- Adds ~50ms latency (1 Haiku call) + ~200ms (2 extra vector searches)

!!! note "Data residency"
    When `enable_multi_query=True`, the user's question is sent to the Anthropic API for expansion. Keep this `False` for deployments with data-residency or PII constraints.

## Step 2: Vector Search

The question (and any alternatives from Step 1) is embedded using the same model that generated section embeddings during pack building. The HNSW index returns the top-K most similar sections by cosine similarity.

```python
# Pseudocode
query_embedding = embed(question)  # 384-dim vector
results = hnsw_index.search(query_embedding, top_k=5)
# Returns: [(section_title, similarity_score), ...]
```

**Configuration:**

- `max_results`: Number of results per query (default 5, clamped to [1, 20])
- When cross-encoder is enabled, fetches 2x candidates to give the cross-encoder a larger pool

## Step 3: Confidence Gate

The confidence gate prevents the pack from injecting irrelevant content when it has nothing useful for the question.

```
max_similarity = max(score for _, score in results)

if max_similarity >= CONTEXT_CONFIDENCE_THRESHOLD (0.5):
    → proceed with pack context
else:
    → skip pack, call _synthesize_answer_minimal()
      (Claude answers from own knowledge, no KG context)
```

**When the gate fires:**

- Response includes `query_type: "confidence_gated_fallback"`
- `sources`, `entities`, and `facts` are empty lists
- Claude still provides a useful answer from training data

**When the gate does NOT fire:**

- Response includes `query_type: "vector_search"`
- Full pipeline continues

**Impact:** Eliminates accuracy regressions on questions outside the pack's domain. Without this gate, packs like `go-expert` showed negative deltas because irrelevant content confused Claude.

| Scenario | max_similarity | Gate fires? |
|----------|---------------|-------------|
| Question directly matches pack content | 0.7-0.95 | No |
| Question loosely related | 0.5-0.7 | No |
| Question on adjacent topic | 0.3-0.5 | Yes |
| Question completely outside domain | 0.0-0.3 | Yes |

## Step 4: Cross-Encoder Reranking (Optional)

**Flag**: `enable_cross_encoder=True` (opt-in, default False)

Bi-encoder search scores query and document independently -- it cannot capture interactions between the two texts. Cross-encoders see both texts simultaneously, enabling precise relevance judgments for negations, comparisons, and qualifications.

**How it works:**

1. Vector search fetches `2 * max_results` candidates (expanded pool)
2. Cross-encoder (`ms-marco-MiniLM-L-12-v2`) scores each `(query, document)` pair
3. Results sorted by `ce_score`, truncated to `max_results`

**Performance:**

- ~50ms per query on CPU (10-candidate pool)
- ~120MB model RAM (loaded once, shared across queries)
- If model fails to load, becomes a passthrough (results unchanged)

## Step 5: Graph Reranking

**Flag**: `enable_reranker=True` (default True)

PageRank is computed over the LINKS_TO edge graph. Articles with many incoming links are considered authoritative. Search results are reranked by a weighted combination:

```
combined_score = alpha * vector_similarity + beta * normalized_pagerank
```

Default weights: `alpha=0.7`, `beta=0.3`

**Example:**

```
Before reranking:
  1. Quantum_fluctuation  (similarity=0.95, pagerank=0.02)  → combined=0.67 + 0.01 = 0.68
  2. Quantum_mechanics    (similarity=0.90, pagerank=0.85)  → combined=0.63 + 0.26 = 0.89

After reranking:
  1. Quantum_mechanics    (combined=0.89)  ← promoted (authoritative)
  2. Quantum_fluctuation  (combined=0.68)
```

**Performance:**

- PageRank computation: O(V+E), cached for 1 hour
- Reranking: O(N log N) where N = result count
- Adds ~50ms per query (with cached PageRank)

## Step 6: Multi-Document Expansion

**Flag**: `enable_multidoc=True` (default True)

Instead of using a single article, the synthesizer retrieves the top 5 articles and extracts the 3 most relevant sections from each. This provides 15 sections of context instead of 3.

**How it works:**

1. Take the reranked result list
2. Group results by article
3. Select top 5 articles by cumulative section relevance
4. Extract top 3 sections per article
5. Assemble unified context for synthesis

**Configuration:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_docs` | 5 | Articles to retrieve |
| `max_sections` | 3 | Sections per article |
| `min_relevance` | 0.7 | Minimum similarity threshold |

## Step 7: Content Quality Filtering

**Always active** when a question is provided (no flag needed).

Each section is scored on a 0.0-1.0 scale:

```
if word_count < 20:
    score = 0.0  (hard stub cutoff)
else:
    length_score  = min(0.8, 0.2 + (word_count / 200) * 0.6)
    keyword_score = min(0.2, overlap_ratio * 0.2)
    score = min(1.0, length_score + keyword_score)
```

Sections below `CONTENT_QUALITY_THRESHOLD = 0.3` are excluded from the synthesis context.

**Score examples:**

| Section | Words | Keyword Overlap | Score | Included? |
|---------|-------|----------------|-------|-----------|
| "See also." | 2 | - | 0.0 | No |
| Short stub, no keywords | 20 | 0% | 0.26 | No |
| Medium paragraph | 50 | 0% | 0.35 | Yes |
| Medium with keywords | 50 | 100% | 0.55 | Yes |
| Full paragraph | 200 | 0% | 0.80 | Yes |
| Full with keywords | 200 | 100% | 1.0 | Yes |

**Fallback:** If ALL sections across ALL retrieved articles are filtered, the agent falls back to using raw `article.content` for the source titles. This is a global fallback -- it only activates when the entire output is empty.

## Step 8: Few-Shot Example Injection

**Flag**: `enable_fewshot=True` (default True)

Pack-specific examples are injected into the synthesis prompt before the question. These guide Claude to follow the pack's preferred answer format, citation style, and reasoning structure.

**Example sources:**

1. `few_shot_examples.json` in the pack directory (curated examples)
2. `eval/questions.jsonl` (evaluation questions repurposed as examples)

**Selection:** The 3 most semantically similar examples to the current question are chosen via cosine similarity over example question embeddings.

**Prompt structure:**

```
Here are examples of high-quality answers:

=== Example 1 ===
Question: What does slices.Contains do?
Answer: slices.Contains reports whether v is present in s.
        E must satisfy the comparable constraint. [Source: slices_stdlib]

=== Example 2 ===
[...]

Now answer this question following the same pattern:
Question: [user's question]
Context: [retrieved sections]
Answer:
```

## Step 9: Claude Synthesis

The assembled prompt -- containing retrieved context, few-shot examples, and the user's question -- is sent to Claude Opus for synthesis.

**Model configuration:**

| Parameter | Value |
|-----------|-------|
| Model | `claude-opus-4-6` (configurable via `synthesis_model`) |
| Max tokens | 1024 (`SYNTHESIS_MAX_TOKENS`) |
| Temperature | Default (not overridden) |

**Response format:**

```python
{
    "answer": "Goroutine scheduling uses an M:N model where...",
    "sources": ["runtime_scheduling", "goroutines_overview"],
    "entities": ["goroutine", "OS thread", "work-stealing"],
    "facts": ["goroutines are multiplexed onto OS threads"],
    "cypher_query": "CALL QUERY_VECTOR_INDEX(...)",
    "query_type": "vector_search",
    "token_usage": {
        "input_tokens": 2847,
        "output_tokens": 312,
        "api_calls": 2
    }
}
```

## Configuration Flags Summary

| Flag | Default | What It Controls |
|------|---------|-----------------|
| `use_enhancements` | True | Master switch for all enhancement modules |
| `enable_reranker` | True | GraphReranker (PageRank blending) |
| `enable_multidoc` | True | MultiDocSynthesizer (5-article expansion) |
| `enable_fewshot` | True | FewShotManager (example injection) |
| `enable_cross_encoder` | False | CrossEncoderReranker (joint scoring) |
| `enable_multi_query` | False | Multi-query retrieval (Haiku expansion) |

!!! warning "Flag interaction"
    All `enable_*` flags are ignored when `use_enhancements=False`. The confidence gate and content quality scoring are always active regardless of `use_enhancements`.

## Latency Breakdown

```
Baseline (use_enhancements=False):
  Vector search:       ~100ms
  Synthesis:           ~150ms
  ─────────────────────────
  Total:               ~250ms

Balanced (default):
  Vector search:       ~100ms
  GraphReranker:       ~50ms   (PageRank cached)
  MultiDocSynthesizer: ~300ms  (5x vector searches)
  FewShotManager:      ~20ms   (example retrieval)
  Synthesis:           ~200ms  (larger context)
  ─────────────────────────
  Total:               ~670ms

Maximum Quality:
  Multi-query:         ~250ms  (1 Haiku + 2 extra searches)
  Cross-encoder:       ~50ms   (10 candidates on CPU)
  GraphReranker:       ~50ms
  MultiDocSynthesizer: ~300ms
  FewShotManager:      ~20ms
  Synthesis:           ~200ms
  ─────────────────────────
  Total:               ~870ms
```

All configurations remain well under 1 second for typical queries.
