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
query_embedding = embed(question)  # 768-dim vector
results = hnsw_index.search(query_embedding, top_k=10)
# Returns: [(section_title, similarity_score), ...]
```

**Configuration:**

- `max_results`: Number of results per query (default 10, clamped to [1, 1000])
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

Degree centrality (in-degree + out-degree) is computed over the LINKS_TO edge graph. Articles with many connections are considered authoritative. In practice, the reranker is called via Reciprocal Rank Fusion (RRF) with k=60, combining the original vector ranking with the centrality ranking:

```
rrf_score = 1/(k + vector_rank) + 0.5/(k + centrality_rank)
```

The `GraphReranker.rerank()` method also supports direct weighted combination:

```
combined_score = vector_weight * vector_similarity + graph_weight * normalized_centrality
```

Default weights: `vector_weight=0.6`, `graph_weight=0.4`

**Example:**

```
Before reranking:
  1. Quantum_fluctuation  (similarity=0.95, centrality=0.02)  → combined=0.57 + 0.01 = 0.58
  2. Quantum_mechanics    (similarity=0.90, centrality=0.85)  → combined=0.54 + 0.34 = 0.88

After reranking:
  1. Quantum_mechanics    (combined=0.88)  ← promoted (authoritative)
  2. Quantum_fluctuation  (combined=0.58)
```

**Performance:**

- Degree centrality computation: O(V+E), computed per query
- Sparse graph detection: automatically disables centrality for graphs with < 2 avg links/article
- Reranking: O(N log N) where N = result count
- Adds ~50ms per query

## Step 6: Multi-Document Expansion

**Flag**: `enable_multidoc=True` (default True)

Instead of using a single article, the synthesizer traverses LINKS_TO edges from the top result to find related articles.

**How it works:**

1. Take the top result from the reranked list as the seed
2. Follow LINKS_TO edges from the seed article
3. Add up to 2 neighbor articles
4. Cap the total source list at 7 articles
5. Assemble unified context for synthesis

**Constructor:** `MultiDocSynthesizer(kuzu_conn)` -- takes only the Kuzu connection. No additional configuration parameters.

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

**Example source:**

The FewShotManager auto-detects examples from `eval/questions.jsonl` adjacent to `pack.db`. If not found, few-shot is silently disabled.

**Selection:** The 2 most semantically similar examples to the current question are chosen via cosine similarity over example question embeddings (called with `k=2` in the query pipeline).

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
| `enable_reranker` | True | GraphReranker (degree centrality via RRF) |
| `enable_multidoc` | True | MultiDocSynthesizer (LINKS_TO expansion) |
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
  GraphReranker:       ~50ms   (degree centrality)
  MultiDocSynthesizer: ~300ms  (LINKS_TO traversal)
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
