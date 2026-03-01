# Confidence-Gated Context Injection

WikiGR's knowledge graph agent skips pack context entirely when vector similarity is too low, letting Claude answer from its own expertise instead of being misled by irrelevant retrieved content.

## Problem This Solves

Before this feature, the synthesis prompt always injected retrieved knowledge graph sections regardless of how relevant they were. When a question was outside a pack's coverage area, vector search would return sections with low cosine similarity — content that was topically unrelated. Injecting that content into the synthesis prompt actively harmed answer quality:

- Claude would hallucinate connections between the irrelevant sections and the question
- Answers would incorrectly cite unrelated articles as sources
- Packs with strong training-data coverage (Go, React) showed accuracy *regressions* because the irrelevant KG content overrode Claude's reliable built-in knowledge

**Confidence-gated context injection** fixes this by measuring retrieval confidence before injecting anything, and falling back to Claude's own expertise when the pack has nothing relevant to contribute.

## How It Works

After vector search returns results, the agent checks the highest cosine similarity score (`max_similarity`) against `CONTEXT_CONFIDENCE_THRESHOLD = 0.5`:

```
Question
   │
   ▼
Vector Search → max_similarity
   │
   ├─ max_similarity >= 0.5 → inject KG context → full pipeline → answer
   │
   └─ max_similarity < 0.5  → confidence gate fires
                                 │
                                 ▼
                          _synthesize_answer_minimal()
                          (Claude uses own knowledge, no KG sections)
                                 │
                                 ▼
                          query_type = "confidence_gated_fallback"
```

The gate fires only when vector search *succeeded but returned low-similarity results*. If vector search fails entirely (no results at all), the existing `vector_fallback` path handles it — the gate does not interfere.

## Query Response Schema

When the gate fires, `query()` returns the same schema as a normal query, but with empty lists for sources/entities/facts and a distinct `query_type`:

```python
{
    "answer": "...",                         # Claude's answer from own knowledge
    "sources": [],                           # empty — no KG content used
    "entities": [],                          # empty
    "facts": [],                             # empty
    "cypher_query": "CALL QUERY_VECTOR_INDEX(...)",  # vector query that ran
    "query_type": "confidence_gated_fallback",
    "token_usage": {"input_tokens": ..., "output_tokens": ..., "api_calls": ...},
}
```

Normal (high-confidence) queries return `query_type = "vector_search"`.

## Usage

### Basic usage — gate is automatic

No configuration is required. The gate fires automatically when vector similarity is below the threshold:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    anthropic_api_key="your-key",
)

result = agent.query("What is goroutine scheduling?")

if result["query_type"] == "confidence_gated_fallback":
    print("Pack had no relevant content — Claude answered from own expertise")
    print(f"Sources cited: {result['sources']}")  # always []
else:
    print(f"Answered using {len(result['sources'])} pack articles")

print(result["answer"])
```

### Detecting gate activation in bulk evaluation

When running evaluation scripts, track how often the gate fires to understand pack coverage gaps:

```python
results = []
for q in questions:
    r = agent.query(q["question"])
    results.append({
        "question": q["question"],
        "answer": r["answer"],
        "gated": r["query_type"] == "confidence_gated_fallback",
        "sources": r["sources"],
    })

gated_count = sum(1 for r in results if r["gated"])
print(f"Gate fired on {gated_count}/{len(results)} questions ({100*gated_count/len(results):.0f}%)")
```

High gate-fire rates (> 40%) indicate the pack does not cover the evaluation question set well.

### Adjusting the threshold

The threshold is a class constant. To tune it for a specific pack, subclass `KnowledgeGraphAgent`:

```python
class StrictAgent(KnowledgeGraphAgent):
    CONTEXT_CONFIDENCE_THRESHOLD = 0.65  # require higher confidence before injecting

class PermissiveAgent(KnowledgeGraphAgent):
    CONTEXT_CONFIDENCE_THRESHOLD = 0.35  # inject even low-confidence context
```

Use the eval harness to measure accuracy at different thresholds before changing the default.

## Configuration Reference

### `KnowledgeGraphAgent` class constants

| Constant | Default | Description |
|---|---|---|
| `CONTEXT_CONFIDENCE_THRESHOLD` | `0.5` | Minimum cosine similarity required before pack content is injected into synthesis. Below this value, the agent calls `_synthesize_answer_minimal()` instead of the full pipeline. |
| `VECTOR_CONFIDENCE_THRESHOLD` | `0.6` | Pre-existing constant — not used in the confidence gate or `query()` path. Defined for potential retrieval-layer filtering. |

These two constants have distinct roles:

- `CONTEXT_CONFIDENCE_THRESHOLD = 0.5`: Active gate — are results confident enough to inject into the synthesis prompt?
- `VECTOR_CONFIDENCE_THRESHOLD = 0.6`: Not applied in the current `query()` path. If you add a retrieval-layer pre-filter (e.g., suppressing very-low-similarity rows before they reach the gate), use this constant rather than introducing a new magic number.

## API Reference

### `KnowledgeGraphAgent.query(question, max_results=5)`

Returns a dict. The `query_type` field indicates which path was taken:

| `query_type` value | Meaning |
|---|---|
| `"vector_search"` | Normal path — KG content injected, full pipeline ran |
| `"confidence_gated_fallback"` | Gate fired — Claude answered without KG context |
| `"vector_fallback"` | Vector search returned no results at all |

### `KnowledgeGraphAgent._synthesize_answer_minimal(question)`

Called internally when the confidence gate fires. Sends a single prompt to Claude:

```
The knowledge pack for this query contained no relevant content.
Answer the following question using your own expertise:

Question: {question}
```

Uses the same `synthesis_model` and `SYNTHESIS_MAX_TOKENS` as the full `_synthesize_answer()` method. Token usage is tracked via `_track_response()`. On API error, returns the string `"Unable to answer: API error."` rather than raising.

**Note:** This method uses a single-underscore name (`_synthesize_answer_minimal`) indicating it is a protected implementation detail. It is accessible for testing purposes but not part of the public API and may change without notice.

## When to Expect the Gate to Fire

The gate fires on questions that fall outside the pack's knowledge domain:

| Scenario | max_similarity | Gate fires? |
|---|---|---|
| Question directly matches pack content | 0.7 – 0.95 | No |
| Question loosely related to pack content | 0.5 – 0.7 | No |
| Question on adjacent topic | 0.3 – 0.5 | Yes |
| Question completely outside pack domain | 0.0 – 0.3 | Yes |

Packs built from documentation sites (Rust, Go, .NET) have narrower semantic coverage than Wikipedia-sourced packs. Expect higher gate-fire rates on programming language packs when asked general CS questions.

## Impact on Accuracy

Enabling confidence-gated context injection eliminates negative deltas on packs where Claude's training data is already strong. Measured results on the evaluation harness:

| Pack | Before | After |
|---|---|---|
| go-expert | < 100% (KG noise hurts) | 100% |
| react-expert | < 100% (KG noise hurts) | 100% |
| physics-expert | ~84% | ~84% (unchanged — high confidence questions) |

The gate has no effect on accuracy when the pack is relevant (high similarity). It only improves accuracy when the pack would otherwise inject misleading content.

## See Also

- [Vector Search as Primary Retrieval](vector-search-primary-retrieval.md) — full retrieval pipeline overview, including `VECTOR_CONFIDENCE_THRESHOLD`
- [Phase 1 Enhancements](phase1-enhancements.md) — GraphReranker, MultiDocSynthesizer, FewShotManager (run after gate check passes)
- [Generating Evaluation Questions](generating-evaluation-questions.md) — measure gate-fire rates across a full question set
