# Configure Enhancements

How to enable, disable, and tune each enhancement module in the KG Agent retrieval pipeline.

## Enhancement Modules Overview

| Module | Flag | Default | What It Does |
|--------|------|---------|-------------|
| GraphReranker | `enable_reranker` | True | Reranks by degree centrality authority |
| MultiDocSynthesizer | `enable_multidoc` | True | Traverses LINKS_TO edges for related articles |
| FewShotManager | `enable_fewshot` | True | Injects pack-specific examples |
| CrossEncoderReranker | `enable_cross_encoder` | False | Joint query-document scoring |
| Multi-Query Retrieval | `enable_multi_query` | False | Haiku-generated query alternatives |
| Confidence Gate | (always active) | - | Skips pack when similarity is low |
| Content Quality Scoring | (always active) | - | Filters stub sections |

## Basic Configuration

### Default (Balanced)

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=True,  # enables reranker, multidoc, fewshot
)
```

### Maximum Quality

```python
agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=True,
    enable_cross_encoder=True,   # +10-15% retrieval precision
    enable_multi_query=True,     # +15-25% recall
)
```

### Baseline (No Enhancements)

```python
agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=False,  # disables ALL enhancement modules
)
```

!!! warning "Flag interaction"
    All `enable_*` flags are ignored when `use_enhancements=False`. The confidence gate and content quality scoring remain active regardless.

## Per-Module Configuration

### GraphReranker

Reranks search results using graph degree centrality to promote authoritative articles. In actual use, the reranker is called via Reciprocal Rank Fusion (RRF) with k=60.

```python
# Enable (default)
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_reranker=True,
)

# Disable
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_reranker=False,
)
```

**Direct module access** (for standalone use outside the KG Agent pipeline):

```python
from wikigr.agent.reranker import GraphReranker

reranker = GraphReranker(kuzu_conn)  # constructor takes only a Kuzu connection

reranked = reranker.rerank(
    vector_results,
    vector_weight=0.6,   # vector similarity weight (default)
    graph_weight=0.4,    # degree centrality weight (default)
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `vector_weight` | 0.6 | Weight for vector similarity score |
| `graph_weight` | 0.4 | Weight for normalized degree centrality |

Higher `vector_weight` favors semantic relevance. Higher `graph_weight` favors authoritative articles. Must sum to 1.0.

### MultiDocSynthesizer

Expands retrieval by traversing LINKS_TO edges from the top result, adding up to 2 neighbors and capping at 7 total sources.

```python
# Enable (default)
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_multidoc=True,
)

# Disable (single-article retrieval)
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_multidoc=False,
)
```

**Direct module access** (for standalone use):

```python
from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer

synthesizer = MultiDocSynthesizer(kuzu_conn)  # constructor takes only a Kuzu connection

# Expand seed articles by traversing LINKS_TO edges
expanded = synthesizer.expand_to_related_articles(seed_articles=[1, 2], max_hops=1)

# Create synthesis text with citations
text = synthesizer.synthesize_with_citations(expanded, query="your question")
```

### FewShotManager

Injects pack-specific examples into the synthesis prompt.

```python
# Enable (default) - auto-detects examples from pack directory
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_fewshot=True,
)

# Enable with explicit path
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_fewshot=True,
    few_shot_path="data/packs/go-expert/eval/questions.jsonl",
)

# Disable
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_fewshot=False,
)
```

**Example file auto-detection**: When `few_shot_path` is not specified, the agent looks for `eval/questions.jsonl` adjacent to `pack.db`.

If the file is not found, few-shot is silently disabled with a warning in logs.

### CrossEncoderReranker

Joint query-document scoring for more precise relevance ranking.

```python
# Enable (opt-in)
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_cross_encoder=True,
)
```

**First-time setup**: The cross-encoder model (`ms-marco-MiniLM-L-12-v2`, ~33MB) is downloaded on first use and cached at `~/.cache/huggingface/`.

**Graceful degradation**: If the model fails to load, the cross-encoder becomes a passthrough -- results are returned unchanged.

### Multi-Query Retrieval

Generates alternative query phrasings to improve recall.

```python
# Enable (opt-in)
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    enable_multi_query=True,
)
```

!!! note "Data residency"
    When enabled, the user's question (truncated to 500 characters) is sent to the Anthropic API for expansion. Keep `False` for deployments with data-residency or PII constraints.

**Graceful degradation**: If the Haiku expansion call fails, the agent falls back to searching with only the original query.

## Confidence Gate

The confidence gate is always active and cannot be disabled via a flag. It prevents pack content from being injected when vector similarity is below the threshold.

**Tuning the threshold** (requires subclassing):

```python
class CustomAgent(KnowledgeGraphAgent):
    CONTEXT_CONFIDENCE_THRESHOLD = 0.65  # stricter (default is 0.5)
```

| Threshold | Behavior |
|-----------|----------|
| 0.35 | Permissive -- injects context even with loose relevance |
| 0.50 | Default -- balanced between coverage and precision |
| 0.65 | Strict -- only injects highly relevant content |

## Content Quality Scoring

Content quality scoring is always active when a question is available. It filters stub sections (< 20 words) and low-quality sections (score < 0.3) from synthesis context.

**Tuning the threshold** (requires subclassing):

```python
class CustomAgent(KnowledgeGraphAgent):
    CONTENT_QUALITY_THRESHOLD = 0.4  # stricter (default is 0.3)
```

## Configuration Profiles

| Setting | Baseline | Balanced | Low Latency | Max Quality |
|---------|----------|----------|-------------|-------------|
| `use_enhancements` | False | True | True | True |
| `enable_reranker` | - | True | True | True |
| `enable_multidoc` | - | True | False | True |
| `enable_fewshot` | - | True | True | True |
| `enable_cross_encoder` | - | False | False | True |
| `enable_multi_query` | - | False | False | True |
| Typical latency | ~250ms | ~670ms | ~400ms | ~870ms |

## Synthesis Model

The model used for answer synthesis can be customized:

```python
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    synthesis_model="claude-sonnet-4-20250514",  # faster, cheaper
)
```

Default is `claude-opus-4-6` for best quality. Use Sonnet for lower latency and cost.

## See Also

- [Retrieval Pipeline](../concepts/retrieval-pipeline.md) -- How each module fits in the pipeline
- [Architecture](../concepts/architecture.md) -- System architecture overview
- [KG Agent API](../reference/kg-agent-api.md) -- Complete constructor parameters
