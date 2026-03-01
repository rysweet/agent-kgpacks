# Retrieval Enhancements: Design and Rationale

Design decisions and architecture behind Issue 211 Improvements 4 and 5.

## Problem Statement

After Phase 1 enhancements (GraphReranker, MultiDocSynthesizer, FewShotManager), two orthogonal quality gaps remained:

| Problem | Root Cause | Symptom |
|---|---|---|
| **Vocabulary mismatch** | Single query embedding misses synonymous content | Relevant articles absent from results |
| **Stub contamination** | Short sections dilute synthesis context | Hallucination, loss of focus, wasted tokens |

### Problem 4: Vocabulary Mismatch

A single embedding represents only one phrasing of the question. Wikipedia and technical knowledge bases store content using author-specific vocabulary. A question about "garbage collection pauses" may not surface "stop-the-world events" — even though cosine similarity is used and the embedding model is good.

**Target impact**: Enabling multi-query retrieval is expected to improve recall@5 by 15–25% with no false-positive regression (based on design analysis; to be validated via evaluation once deployed).

### Problem 5: Stub Contamination

Section content in Kuzu databases spans a wide quality spectrum: from comprehensive explanations (500+ words) to one-line disambiguation stubs ("See also: ..."). Before quality filtering, all sections entered the synthesis context equally. Short stubs:

- Waste Claude's context window (fixed token budget per query)
- Add noise that can confuse synthesis (hallucination)
- Provide no informational value

**Target impact**: Filtering sections below `CONTENT_QUALITY_THRESHOLD = 0.3` is expected to reduce average context noise by ~30% (measured as proportion of sub-20-word sections in synthesis input; to be validated via evaluation once deployed).

---

## Solution Architecture

### Improvement 4: Multi-Query Retrieval

#### Design Rationale

**Approach chosen**: Query expansion via LLM alternative phrasing.

**Alternatives considered**:

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| **LLM query expansion (chosen)** | High-quality alternatives, semantic diversity | API call cost, latency | ✓ Chosen |
| Synonym expansion (WordNet) | Free, deterministic | Shallow, brittle for technical terms | ✗ |
| Embedding-space perturbation | No API call | Poor semantic diversity | ✗ |
| Back-translation | True semantic diversity | Expensive, high latency | ✗ |

**Why Claude Haiku specifically**: Haiku (`claude-haiku-4-5-20251001`) provides high-quality semantic rewriting at very low cost and latency (~50 ms typical). The synthesis model (Opus) would be wasteful for this lightweight expansion task.

**Why 2 alternatives**: Testing showed diminishing returns beyond 3 total queries. 2 alternatives provide meaningful vocabulary coverage (noun/verb/phrase reformulations) without tripling DB load.

#### Architecture

```
_multi_query_retrieve(question, max_results=5)
│
├── Truncate question to 500 chars (prompt injection defense)
│
├── claude.messages.create(model="claude-haiku-4-5-20251001")
│   └── Prompt: "Generate exactly 2 alternative phrasings as JSON array"
│
├── Parse JSON array, cap each alternative to 300 chars
│
├── for query in [question] + alternatives[:2]:
│   └── semantic_search(query, top_k=max_results)  ← existing method
│
├── Deduplicate by title: keep highest similarity per title
│
└── Sort descending by similarity, return
```

#### Deduplication Strategy

Title-based deduplication (not content-hash or URL) was chosen because:
- Titles are the natural identity of knowledge graph nodes
- Content may differ slightly between query results for the same article
- Highest-similarity-wins ensures the best embedding alignment is preserved

#### Fan-out Cap

`max_results` is clamped to `[1, 20]` before use:
- Lower bound 1: prevents silent no-op from `semantic_search` when called with 0
- Upper bound 20: prevents excessive Kuzu load from adversarial inputs

#### Opt-In Default (`enable_multi_query=False`)

Multi-query is **off by default** because:
1. **Data residency**: questions are sent to the Anthropic API for expansion
2. **Cost**: adds 1 Haiku API call per user query
3. **Latency**: adds ~50 ms + 2 extra DB searches

Teams with strict data residency, PII, or offline requirements can safely use the agent without opting in.

#### Graceful Fallback

If the Haiku call raises any exception, the agent logs a warning and proceeds with only the original query. The fallback is intentionally simple: zero retry, one attempt. This prevents cascading latency on API degradation.

---

### Improvement 5: Content Quality Scoring

#### Design Rationale

**Approach chosen**: Composite score (length + keyword overlap) with hard stub cutoff.

**Alternatives considered**:

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| **Composite score (chosen)** | Captures length + relevance, tunable | Heuristic, not ML | ✓ Chosen |
| Embedding cosine similarity | Semantic quality | Additional embedding calls, cost | ✗ |
| LLM relevance score | High quality | Cost too high per section | ✗ |
| Word count only | Simple | Ignores relevance | ✗ |

**Why a hard cutoff at 20 words**: Sections under 20 words are almost universally metadata (category lines, "See also" entries, navbox labels). They are never useful synthesis inputs. The hard `return 0.0` is cheaper and more reliable than letting them pass the composite formula.

#### Score Formula Design

```
length_score  = min(0.8, 0.2 + (word_count / 200) * 0.6)
```

- Floor of 0.2 at exactly 20 words: sections just above the stub cutoff get a small nonzero base
- Ceiling of 0.8 at 200 words: prevents very long sections from dominating by length alone (leaves room for keyword contribution)
- 200 words ≈ a well-developed Wikipedia paragraph; longer sections are usually redundant

```
keyword_score = min(0.2, overlap_ratio * 0.2)
```

- Max 0.2: keyword overlap is a secondary signal, never the dominant one
- Stop words excluded: avoids score inflation from ubiquitous function words
- Overlap ratio: fraction of question keywords (excluding stop words) found in section

```
score = min(1.0, length_score + keyword_score)
```

- Combined max of 1.0 to keep the range well-defined

**Threshold of 0.3**: Calibrated to exclude sub-20-word sections and very short (~20-30 word) stubs with no keyword overlap, while passing any section with 50+ words or strong keyword relevance.

#### STOP_WORDS Design

`STOP_WORDS` is a `frozenset[str]` class attribute (not instance attribute) because:
- Immutable: no risk of mutation per-instance
- Shared: zero memory overhead for multi-agent scenarios
- `frozenset` membership test is O(1)

The set covers ~80 common English function words (determiners, prepositions, pronouns, auxiliaries, conjunctions). It does not attempt to cover domain-specific stop words, which would require per-pack configuration.

#### Integration Point

Quality filtering happens inside `_fetch_source_text` (not `_build_synthesis_context` directly), because:
- `_fetch_source_text` already iterates over individual sections row-by-row
- The filter is applied per-section at the point content is assembled, keeping the logic collocated with the content
- `_build_synthesis_context` passes `question=question` through to `_fetch_source_text`

When `question=None` (called without a question context), filtering is skipped entirely — preserving backwards compatibility for callers that don't supply a question.

#### Fallback: Global Content Fallback

If all sections across **all retrieved articles** are filtered (resulting in an empty assembled text), the agent runs a second query fetching `article.content` for all source titles. This is a **global** fallback: it activates only when the entire assembled output is empty. An individual article whose sections all fall below the threshold receives no per-article fallback if at least one other article contributes passing sections.

---

## Security Considerations

Both improvements were hardened against adversarial inputs at design time:

| Risk | Mitigation |
|---|---|
| Prompt injection via long question | `question[:500]` before Haiku prompt |
| Adversarial Haiku response with huge strings | `str(p)[:300]` cap per alternative |
| Excessive DB load via large `max_results` | `max(1, min(max_results, 20))` clamp |
| PII in log lines on search failure | `query[:100] + '...'` in warning |
| Data residency / Anthropic API exposure | `enable_multi_query=False` default + docstring notice |
| Cypher injection | All queries already parameterized — no changes needed |

---

## Performance Characteristics

### Multi-Query Retrieval

```
Single-query (default):
  semantic_search:   1 call  (~100 ms per call)
  Haiku expansion:   0 calls
  ─────────────────────────
  Total extra cost:  0 ms

Multi-query (opt-in):
  Haiku expansion:   1 call  (~50 ms)
  semantic_search:   3 calls (~300 ms)
  Deduplication:     O(N) where N = total results
  ─────────────────────────
  Total extra cost:  ~350 ms + 1 Haiku call
```

### Content Quality Scoring

```
_score_section_quality per section:
  word split:        O(W) where W = word count
  frozenset lookup:  O(1) per word
  ─────────────────────────
  Cost per section:  negligible (<1 ms for typical 50-500 word section)
  Total overhead:    O(S * W) where S = sections per article
```

Quality scoring is CPU-only, requires no API calls, and has effectively zero latency impact on end-to-end query time.

---

## Target Impact

Design targets pending validation after deployment:

| Feature | Metric | Target Change |
|---|---|---|
| Multi-Query | recall@5 | +15–25% |
| Content Quality | synthesis context noise | −30% |
| Content Quality | synthesis focus / accuracy | +5–10% |

---

## See Also

- [How-To: Retrieval Enhancements](../howto/retrieval-enhancements.md) — usage guide with examples
- [API Reference: Retrieval Enhancements](../reference/retrieval-enhancements.md) — complete method signatures
- [Phase 1 Enhancements Design](./phase1-enhancements-design.md) — design for GraphReranker, MultiDocSynthesizer, FewShotManager
