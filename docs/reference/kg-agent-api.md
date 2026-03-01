# KG Agent API Reference

Complete API reference for `KnowledgeGraphAgent`, the core class for querying Knowledge Packs.

## KnowledgeGraphAgent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
```

### Constructor

```python
KnowledgeGraphAgent(
    db_path: str,
    anthropic_api_key: str | None = None,
    read_only: bool = True,
    use_enhancements: bool = True,
    few_shot_path: str | None = None,
    enable_reranker: bool = True,
    enable_multidoc: bool = True,
    enable_fewshot: bool = True,
    enable_cross_encoder: bool = False,
    synthesis_model: str | None = None,
    cypher_pack_path: str | None = None,
    enable_multi_query: bool = False,
)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db_path` | `str` | (required) | Path to the Kuzu database directory (e.g., `data/packs/go-expert/pack.db`) |
| `anthropic_api_key` | `str \| None` | `None` | Anthropic API key. If `None`, reads from `ANTHROPIC_API_KEY` environment variable |
| `read_only` | `bool` | `True` | Open database in read-only mode. Enables concurrent access during expansion |
| `use_enhancements` | `bool` | `True` | Master switch for Phase 1 enhancements (reranking, multi-doc, few-shot). When `False`, all `enable_*` flags are ignored |
| `few_shot_path` | `str \| None` | `None` | Path to few-shot examples JSON. When `None`, auto-detected from pack directory |
| `enable_reranker` | `bool` | `True` | Enable GraphReranker (PageRank-based authority blending). Only active when `use_enhancements=True` |
| `enable_multidoc` | `bool` | `True` | Enable MultiDocSynthesizer (multi-article retrieval). Only active when `use_enhancements=True` |
| `enable_fewshot` | `bool` | `True` | Enable FewShotManager (example injection). Only active when `use_enhancements=True` |
| `enable_cross_encoder` | `bool` | `False` | Enable CrossEncoderReranker (joint query-document scoring). Opt-in. Only active when `use_enhancements=True` |
| `synthesis_model` | `str \| None` | `None` | Claude model for synthesis. Defaults to `claude-opus-4-6` |
| `cypher_pack_path` | `str \| None` | `None` | Path to OpenCypher expert pack for RAG-augmented Cypher generation |
| `enable_multi_query` | `bool` | `False` | Generate alternative query phrasings via Claude Haiku. Opt-in. **When True, questions are sent to the Anthropic API** |

#### Example

```python
# Default configuration (balanced)
agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
)

# Maximum quality
agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=True,
    enable_cross_encoder=True,
    enable_multi_query=True,
)

# Baseline (no enhancements)
agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=False,
)
```

### query()

```python
def query(
    self,
    question: str,
    max_results: int = 5,
) -> dict
```

Query the knowledge graph and synthesize an answer.

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | `str` | (required) | The natural language question |
| `max_results` | `int` | `5` | Maximum number of vector search results. Clamped to [1, 20] |

#### Returns

A dictionary with the following structure:

```python
{
    "answer": str,          # Synthesized answer text
    "sources": list[str],   # Article titles used as sources
    "entities": list[str],  # Entities mentioned in the answer
    "facts": list[str],     # Key facts from retrieved content
    "cypher_query": str,    # The vector search query executed
    "query_type": str,      # "vector_search" | "confidence_gated_fallback" | "vector_fallback"
    "token_usage": {
        "input_tokens": int,
        "output_tokens": int,
        "api_calls": int,
    },
}
```

#### query_type Values

| Value | Meaning |
|-------|---------|
| `"vector_search"` | Normal path -- pack content retrieved and used for synthesis |
| `"confidence_gated_fallback"` | Confidence gate fired -- Claude answered without pack context (similarity below threshold) |
| `"vector_fallback"` | Vector search returned no results at all |

#### Example

```python
result = agent.query("What is goroutine scheduling?")

print(result["answer"])
# "Go uses an M:N scheduling model where..."

print(result["sources"])
# ["runtime_scheduling", "goroutines"]

print(result["query_type"])
# "vector_search"

print(result["token_usage"])
# {"input_tokens": 2847, "output_tokens": 312, "api_calls": 2}
```

## Class Constants

| Constant | Type | Default | Description |
|----------|------|---------|-------------|
| `DEFAULT_MODEL` | `str` | `"claude-opus-4-6"` | Default synthesis model |
| `VECTOR_CONFIDENCE_THRESHOLD` | `float` | `0.6` | Pre-defined constant for retrieval-layer filtering (not used in `query()` path) |
| `CONTEXT_CONFIDENCE_THRESHOLD` | `float` | `0.5` | Minimum cosine similarity required before pack content is injected into synthesis |
| `PLAN_CACHE_MAX_SIZE` | `int` | `128` | Maximum entries in the query plan cache |
| `MAX_ARTICLE_CHARS` | `int` | `3000` | Maximum characters per article in synthesis context |
| `PLAN_MAX_TOKENS` | `int` | `512` | Maximum tokens for query planning |
| `SYNTHESIS_MAX_TOKENS` | `int` | `1024` | Maximum tokens for answer synthesis |
| `SEED_EXTRACT_MAX_TOKENS` | `int` | `256` | Maximum tokens for seed extraction |
| `CONTENT_QUALITY_THRESHOLD` | `float` | `0.3` | Minimum quality score for section inclusion in synthesis context |
| `STOP_WORDS` | `frozenset[str]` | ~80 words | Common English function words excluded from keyword overlap scoring |

## Enhancement Module Classes

### GraphReranker

```python
from wikigr.agent.reranker import GraphReranker

reranker = GraphReranker(
    conn: kuzu.Connection,
    alpha: float = 0.7,  # vector similarity weight
    beta: float = 0.3,   # PageRank weight
)

reranked = reranker.rerank(
    results: list[dict],  # [{"title": str, "score": float}, ...]
    top_k: int = 10,
) -> list[dict]
```

### MultiDocSynthesizer

```python
from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer

synthesizer = MultiDocSynthesizer(
    conn: kuzu.Connection,
    num_docs: int = 5,
    max_sections: int = 3,
    min_relevance: float = 0.7,
)

context = synthesizer.retrieve(
    question: str,
    embedding_generator,  # callable that generates embeddings
) -> dict
```

### FewShotManager

```python
from wikigr.agent.few_shot import FewShotManager

manager = FewShotManager(
    examples_path: str,  # path to JSON or JSONL file
)

examples = manager.get_examples(
    question: str,
    num_examples: int = 3,
) -> list[dict]
```

### CrossEncoderReranker

```python
from wikigr.agent.cross_encoder import CrossEncoderReranker

reranker = CrossEncoderReranker()
# Downloads ms-marco-MiniLM-L-12-v2 (~33MB) on first use

reranked = reranker.rerank(
    query: str,
    results: list[dict],  # must have "content" or "title" key
    top_k: int = 5,
) -> list[dict]
# Each result gains a "ce_score" key (float, higher = more relevant)
```

If the model fails to load, `rerank()` returns results unchanged (passthrough).

## Token Usage Tracking

The agent tracks cumulative token usage across all API calls:

```python
agent = KnowledgeGraphAgent(db_path="pack.db")

result1 = agent.query("First question")
result2 = agent.query("Second question")

# Cumulative usage
print(agent.token_usage)
# {"input_tokens": 5694, "output_tokens": 624, "api_calls": 4}

# Per-query usage
print(result2["token_usage"])
# {"input_tokens": 2847, "output_tokens": 312, "api_calls": 2}
```

## Error Handling

The agent handles errors gracefully:

- **API connection errors**: Returns `"Unable to answer: API error."` instead of raising
- **Empty vector results**: Falls back to `query_type: "vector_fallback"`
- **Low confidence**: Falls back to `query_type: "confidence_gated_fallback"`
- **Cross-encoder load failure**: Becomes passthrough (no `ce_score` in results)
- **Multi-query Haiku failure**: Proceeds with original query only
- **All sections filtered**: Falls back to raw article content
