# Configure Enhancements

How to enable, disable, and tune each enhancement module in the KG Agent retrieval pipeline.

## Enhancement Modules Overview

| Module | Flag | Default | What It Does |
|--------|------|---------|-------------|
| GraphReranker | `enable_reranker` | True | Reranks by PageRank authority |
| MultiDocSynthesizer | `enable_multidoc` | True | Expands retrieval to 5 articles |
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

Reranks search results using graph centrality (PageRank) to promote authoritative articles.

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

**Tuning weights** (requires subclassing or direct module access):

```python
from wikigr.agent.reranker import GraphReranker

reranker = GraphReranker(
    conn=agent.conn,
    alpha=0.7,  # vector similarity weight (default)
    beta=0.3,   # PageRank weight (default)
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `alpha` | 0.7 | Weight for vector similarity score |
| `beta` | 0.3 | Weight for normalized PageRank |

Higher `alpha` favors semantic relevance. Higher `beta` favors authoritative articles. Must sum to 1.0.

### MultiDocSynthesizer

Expands retrieval from 1 article to multiple articles for broader coverage.

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

**Tuning** (via direct module access):

```python
from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer

synthesizer = MultiDocSynthesizer(
    conn=agent.conn,
    num_docs=5,         # articles to retrieve (default)
    max_sections=3,     # sections per article (default)
    min_relevance=0.7,  # minimum similarity threshold (default)
)
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
    few_shot_path="data/packs/go-expert/few_shot_examples.json",
)

# Disable
agent = KnowledgeGraphAgent(
    db_path="pack.db",
    use_enhancements=True,
    enable_fewshot=False,
)
```

**Example file auto-detection**: When `few_shot_path` is not specified, the agent looks for:

1. `few_shot_examples.json` in the same directory as `pack.db`
2. `eval/questions.jsonl` in the same directory as `pack.db`

If neither is found, few-shot is silently disabled with a warning in logs.

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
