# Improving Accuracy

Seven improvements from Issue #211 that collectively raised Pack accuracy from 95.0% to 97.5%. Each addresses a specific failure mode in the retrieval and evaluation pipeline.

## Overview

| # | Improvement | What It Fixes | Accuracy Impact |
|---|------------|--------------|----------------|
| 1 | Confidence-gated context injection | Pack injects irrelevant content | Eliminates negative deltas |
| 2 | Cross-encoder reranking | Bi-encoder misranks nuanced queries | +10-15% retrieval precision |
| 3 | Multi-query retrieval | Vocabulary mismatch misses content | +15-25% recall |
| 4 | Content quality scoring | Stub sections dilute context | -30% context noise |
| 5 | URL list expansion | Thin coverage in source URLs | More content to retrieve |
| 6 | Eval question calibration | Questions test training, not packs | Accurate measurement |
| 7 | Full pack rebuilds | Stale database after URL changes | Fresh content |

## Improvement 1: Confidence-Gated Context Injection

### Problem

Before this improvement, the synthesis prompt always included retrieved pack content regardless of relevance. When a question fell outside the pack's domain, vector search returned low-similarity sections that confused Claude:

- Claude hallucinated connections between irrelevant sections and the question
- Answers incorrectly cited unrelated articles
- Packs with strong training coverage (Go, React) showed accuracy *regressions*

### Solution

After vector search, check whether the best result meets a minimum similarity threshold:

```
max_similarity >= 0.5  →  inject pack context (full pipeline)
max_similarity < 0.5   →  skip pack, let Claude answer from own knowledge
```

### Configuration

The threshold is a class constant on `KnowledgeGraphAgent`:

```python
class KnowledgeGraphAgent:
    CONTEXT_CONFIDENCE_THRESHOLD = 0.5
```

To tune for a specific pack:

```python
class StrictAgent(KnowledgeGraphAgent):
    CONTEXT_CONFIDENCE_THRESHOLD = 0.65  # require higher confidence

class PermissiveAgent(KnowledgeGraphAgent):
    CONTEXT_CONFIDENCE_THRESHOLD = 0.35  # inject more context
```

### Impact

| Pack | Before | After |
|------|--------|-------|
| go-expert | Negative delta (KG noise) | 100% (gate fires on OOD questions) |
| react-expert | Negative delta (KG noise) | 100% (gate fires on OOD questions) |

## Improvement 2: Cross-Encoder Reranking

### Problem

Bi-encoder search (embedding similarity) scores query and document independently. It cannot capture interactions like negations ("not supported"), comparisons ("differs from"), or qualifications ("only when").

### Solution

After vector search returns candidates, a cross-encoder model (`ms-marco-MiniLM-L-12-v2`) rescores each `(query, document)` pair jointly. This enables precise relevance judgments.

### Configuration

```python
agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=True,
    enable_cross_encoder=True,  # opt-in
)
```

**First use downloads a ~33MB model.** Subsequent runs load from `~/.cache/huggingface/`.

### Graceful Degradation

If the model fails to load (no network on first use), the cross-encoder becomes a passthrough -- results are returned unchanged. The agent continues to work with bi-encoder ranking.

### Impact

- +10-15% retrieval precision on nuanced queries
- ~50ms additional latency per query
- ~120MB model RAM (loaded once)

## Improvement 3: Multi-Query Retrieval

### Problem

A single query embedding misses relevant content that uses different vocabulary. "Memory safety in systems programming" may not surface articles about "ownership and borrowing."

### Solution

When enabled, Claude Haiku generates 2 alternative phrasings. Vector search runs for all 3 queries. Results are deduplicated by title (highest similarity wins).

### Configuration

```python
agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    enable_multi_query=True,  # opt-in
)
```

!!! note "Data residency"
    When `enable_multi_query=True`, the question (truncated to 500 chars) is sent to the Anthropic API. Keep `False` for data-sensitive deployments.

### Impact

- +15-25% recall improvement
- ~250ms additional latency (1 Haiku call + 2 extra searches)
- Graceful fallback: if Haiku fails, proceeds with original query only

## Improvement 4: Content Quality Scoring

### Problem

Short stub sections (disambiguation headers, "See also" entries, navigation labels) waste Claude's context window and add noise that causes hallucination.

### Solution

Each section is scored on a 0.0-1.0 scale before inclusion in synthesis context:

```
if word_count < 20:
    score = 0.0  (hard cutoff)
else:
    length_score  = min(0.8, 0.2 + (word_count / 200) * 0.6)
    keyword_score = min(0.2, overlap_ratio * 0.2)
    score = min(1.0, length_score + keyword_score)
```

Sections below `CONTENT_QUALITY_THRESHOLD = 0.3` are filtered out.

### Configuration

This is always active when a question is available -- no flag needed. The threshold is a class constant:

```python
class KnowledgeGraphAgent:
    CONTENT_QUALITY_THRESHOLD = 0.3
```

### Impact

- ~30% reduction in context noise
- No API calls (CPU-only scoring, <1ms per section)
- Global fallback if all sections filtered: raw article content used instead

## Improvement 5: URL List Expansion

### Problem

Initial URL lists were too short (15-30 URLs), leaving coverage gaps in the knowledge graph. The pack database lacked content for many evaluation questions.

### Solution

Expand `urls.txt` for each pack to cover:

- Core documentation and overview pages
- Getting started and quickstart guides
- How-to guides and sub-pages
- Tutorials and sub-pages
- API reference with sub-categories
- GitHub source files and READMEs
- Community resources (where applicable)

### Steps

1. **Audit existing URLs**: Count URLs, check section coverage

    ```bash
    grep -v '^\s*#' data/packs/langchain-expert/urls.txt | grep -v '^\s*$' | wc -l
    ```

2. **Identify gaps**: Compare against the documentation site's table of contents

3. **Add URLs by section**: Group with comment headers

    ```
    # How-To Guides - Additional Sub-Pages
    https://python.langchain.com/docs/how_to/custom_tools/
    https://python.langchain.com/docs/how_to/streaming/
    ```

4. **Validate reachability**:

    ```bash
    python scripts/validate_pack_urls.py data/packs/langchain-expert/urls.txt
    ```

### Recommended URL Counts

| Pack Complexity | Minimum | Recommended |
|-----------------|---------|-------------|
| Focused library | 30 | 45-60 |
| Framework with integrations | 50 | 65-80 |
| Full platform | 50 | 70-90 |

### Impact

More URLs lead to more articles in the graph, which leads to better retrieval coverage.

## Improvement 6: Eval Question Calibration

### Problem

Many initial evaluation questions tested general knowledge that Claude already has from training. When the training baseline is 100%, the pack cannot demonstrate improvement -- the questions are measuring the wrong thing.

### Solution

Replace generic questions with pack-specific ones that target current documentation content.

### Common Fixes

**Replace training-data questions with pack-specific ones:**

| Pack | Old (generic) | New (pack-specific) |
|------|--------------|---------------------|
| go-expert | "What is a goroutine?" | "What does `slices.Contains` do, and what constraint must E satisfy?" |
| react-expert | "What are React hooks?" | "What does the `useActionState` hook return, and when is it used?" |

**Update deprecated API references in ground truth:**

| Pack | Old | New |
|------|-----|-----|
| langchain-expert | LangServe as recommended | LangGraph Platform as successor |
| openai-api-expert | `gpt-4-turbo` | `gpt-4o` |

**Correct factually wrong ground truth:**

| Pack | Correction |
|------|-----------|
| vercel-ai-sdk | Removed incorrect WebSocket streaming claims |
| bicep-infrastructure | Fixed Key Vault reference syntax |

**Remove questions about removed features:**

| Pack | Removed | Replaced With |
|------|---------|--------------|
| zig-expert | Zig async/await (removed in 0.12) | `GeneralPurposeAllocator`, `b.dependency()` |

### Validation After Editing

```bash
# Verify JSONL parses cleanly
python -c "
import json, sys
path = 'data/packs/PACK/eval/questions.jsonl'
lines = open(path).readlines()
for i, line in enumerate(lines, 1):
    obj = json.loads(line)
    required = {'id','domain','difficulty','question','ground_truth','source'}
    missing = required - obj.keys()
    if missing:
        print(f'Line {i}: missing fields {missing}')
        sys.exit(1)
print(f'OK: {len(lines)} questions, all valid')
"
```

### Impact

Calibrated questions accurately measure pack value. Before calibration, some packs showed 0pp delta because questions tested training knowledge. After calibration, the same packs showed meaningful positive deltas.

## Improvement 7: Full Pack Rebuilds

### Problem

After expanding URLs (Improvement 5), the pack database still contains the old, smaller content set. Evaluation runs against the stale database.

### Solution

Rebuild the pack from scratch after URL expansion:

```bash
# Rebuild (uses urls.txt, creates new pack.db)
echo "y" | uv run python scripts/build_go_pack.py

# Re-evaluate
uv run python scripts/eval_single_pack.py go-expert --sample 10
```

### Impact

Fresh builds incorporate all new URLs, providing the expanded coverage needed for improved retrieval.

## Applying All Seven Improvements

The improvements stack and should be applied together for maximum effect:

1. Expand `urls.txt` (Improvement 5)
2. Validate URLs: `python scripts/validate_pack_urls.py data/packs/<name>/urls.txt`
3. Rebuild pack: `python scripts/build_<pack>_pack.py`
4. Calibrate eval questions (Improvement 6)
5. Run evaluation with all enhancements:

```python
agent = KnowledgeGraphAgent(
    db_path="data/packs/<pack>/pack.db",
    use_enhancements=True,         # enables reranker, multidoc, fewshot
    enable_cross_encoder=True,     # improvement 2
    enable_multi_query=True,       # improvement 3
    # improvement 1 (confidence gate) is always active
    # improvement 4 (quality scoring) is always active
)
```

6. Evaluate: `python scripts/eval_single_pack.py <pack> --sample 25`
7. Compare Pack vs Training delta
