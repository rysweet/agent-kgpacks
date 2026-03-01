# Phase 1 Enhancements: API Reference

Complete API reference for the Phase 1 retrieval enhancement modules.

## Overview

Phase 1 enhancements consist of four independent modules:

| Module | Purpose | Accuracy Impact | Default |
|--------|---------|-----------------|---------|
| `GraphReranker` | Rerank results using graph centrality | +5-10% | On |
| `MultiDocSynthesizer` | Multi-document retrieval | +10-15% | On |
| `FewShotManager` | Pack-specific example injection | +5-10% | On |
| `CrossEncoderReranker` | Joint query-document scoring via cross-encoder | +10-15% retrieval precision | **Off (opt-in)** |

**Combined Impact**: 50% baseline → 70-75% accuracy with default enhancements; cross-encoder adds a further +10-15% retrieval precision on top.

## KnowledgeGraphAgent API

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
    enable_cross_encoder: bool = False,  # opt-in: downloads 33MB model on first use
    synthesis_model: str | None = None,
    cypher_pack_path: str | None = None,
)
```

**Parameters**:
- `db_path` (str): Path to Kuzu database file
- `anthropic_api_key` (str, optional): Anthropic API key (or from `ANTHROPIC_API_KEY` env var)
- `read_only` (bool): Open database in read-only mode (default: `True`)
- `use_enhancements` (bool): Master switch — enables all Phase 1 enhancement modules (default: `True`)
- `few_shot_path` (str, optional): Explicit path to few-shot examples JSON; auto-detected from pack directory when `None`
- `enable_reranker` (bool): Enable `GraphReranker` (default: `True`; ignored when `use_enhancements=False`)
- `enable_multidoc` (bool): Enable `MultiDocSynthesizer` (default: `True`; ignored when `use_enhancements=False`)
- `enable_fewshot` (bool): Enable `FewShotManager` (default: `True`; ignored when `use_enhancements=False`)
- `enable_cross_encoder` (bool): Enable `CrossEncoderReranker` (default: `False`; ignored when `use_enhancements=False`). Downloads ~33MB model on first use.
- `synthesis_model` (str, optional): Claude model ID for synthesis and planning (default: `claude-opus-4-6`)
- `cypher_pack_path` (str, optional): Path to OpenCypher expert pack examples for RAG-augmented Cypher generation

**Returns**: `KnowledgeGraphAgent` instance

**Example**:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

# Enhanced mode (70-75% accuracy)
agent = KnowledgeGraphAgent(
    db_path="data/packs/physics-expert/physics.db",
    use_enhancements=True
)

# Baseline mode (50% accuracy)
agent_baseline = KnowledgeGraphAgent(
    db_path="data/packs/physics-expert/physics.db",
    use_enhancements=False
)
```

### query() Method

No API changes - `use_enhancements` flag affects internal retrieval behavior.

```python
result = agent.query(
    question="What is quantum entanglement?",
    max_results=10
)
```

**Behavior Changes with `use_enhancements=True`**:

1. **Retrieval**: 5 articles instead of 1 (MultiDocSynthesizer)
2. **Reranking**: Results reranked by graph centrality (GraphReranker)
3. **Context**: 2-3 few-shot examples prepended (FewShotManager)
4. **Latency**: +350ms average overhead

**Response Format** (unchanged):

```python
{
    "answer": str,           # Natural language answer
    "sources": list[str],    # Article titles (5 instead of 1 when enhanced)
    "entities": list[dict],  # Extracted entities
    "facts": list[str],      # Retrieved facts
    "cypher_query": str,     # Executed Cypher query
    "query_type": str        # Query classification
}
```

## GraphReranker

Reranks vector search results using graph centrality metrics.

### Constructor

```python
from wikigr.agent.reranker import GraphReranker

reranker = GraphReranker(
    conn: kuzu.Connection,
    alpha: float = 0.7,
    beta: float = 0.3,
    cache_ttl: int = 3600
)
```

**Parameters**:
- `conn` (kuzu.Connection): Kuzu database connection
- `alpha` (float): Weight for vector similarity score (default: 0.7)
- `beta` (float): Weight for PageRank score (default: 0.3)
- `cache_ttl` (int): PageRank cache TTL in seconds (default: 3600)

**Note**: `alpha + beta` should equal 1.0 for normalized scoring.

### rerank() Method

```python
reranked_results = reranker.rerank(
    results: list[dict],
    top_k: int = 10
) -> list[dict]
```

**Parameters**:
- `results` (list[dict]): Search results with `title` and `score` fields
- `top_k` (int): Number of top results to return (default: 10)

**Returns**: List of reranked results with updated scores

**Example**:

```python
# Original results (from vector search)
results = [
    {"title": "Quantum_fluctuation", "score": 0.95},
    {"title": "Quantum_mechanics", "score": 0.90},
    {"title": "Quantum_field_theory", "score": 0.88}
]

# Rerank using graph centrality
reranked = reranker.rerank(results, top_k=10)
# [
#     {"title": "Quantum_mechanics", "score": 0.92},      # Promoted (high PageRank)
#     {"title": "Quantum_fluctuation", "score": 0.91},
#     {"title": "Quantum_field_theory", "score": 0.87}
# ]
```

### compute_pagerank() Method

```python
pagerank_scores = reranker.compute_pagerank(
    damping: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-6
) -> dict[str, float]
```

**Parameters**:
- `damping` (float): PageRank damping factor (default: 0.85)
- `max_iter` (int): Maximum iterations (default: 100)
- `tol` (float): Convergence tolerance (default: 1e-6)

**Returns**: Dictionary mapping article titles to PageRank scores

**Example**:

```python
pagerank = reranker.compute_pagerank()
# {
#     "Quantum_mechanics": 0.0145,
#     "Quantum_entanglement": 0.0089,
#     "Quantum_computing": 0.0067,
#     ...
# }
```

**Implementation Details**:
- Uses LINKS_TO edges from Kuzu graph
- PageRank cached after first computation (cache cleared every `cache_ttl` seconds)
- Cypher query: `MATCH (a:Article)-[:LINKS_TO]->(b:Article) RETURN a.title, b.title`

## MultiDocSynthesizer

Retrieves and synthesizes information from multiple articles.

### Constructor

```python
from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer

synthesizer = MultiDocSynthesizer(
    conn: kuzu.Connection,
    num_docs: int = 5,
    max_sections: int = 3,
    min_relevance: float = 0.7
)
```

**Parameters**:
- `conn` (kuzu.Connection): Kuzu database connection
- `num_docs` (int): Number of articles to retrieve (default: 5)
- `max_sections` (int): Max sections per article (default: 3)
- `min_relevance` (float): Minimum similarity threshold (default: 0.7)

### retrieve() Method

```python
context = synthesizer.retrieve(
    question: str,
    embedding_generator: EmbeddingGenerator
) -> dict
```

**Parameters**:
- `question` (str): Natural language question
- `embedding_generator` (EmbeddingGenerator): Embedding generator instance

**Returns**: Retrieved context dictionary

**Response Format**:

```python
{
    "articles": [
        {
            "title": str,
            "category": str,
            "word_count": int
        }
    ],
    "sections": [
        {
            "section_id": str,
            "title": str,
            "content": str,
            "article_title": str,
            "relevance_score": float
        }
    ],
    "sources": list[str],  # Unique article titles
    "facts": list[str]     # Extracted facts from all sections
}
```

**Example**:

```python
from bootstrap.src.embeddings.generator import EmbeddingGenerator

gen = EmbeddingGenerator()
context = synthesizer.retrieve(
    question="What is quantum entanglement?",
    embedding_generator=gen
)

print(f"Retrieved {len(context['articles'])} articles")
# Retrieved 5 articles

print(f"Sources: {context['sources']}")
# Sources: ['Quantum_entanglement', 'Quantum_mechanics', 'EPR_paradox',
#           'Quantum_teleportation', 'Bell_test_experiments']

print(f"Total facts: {len(context['facts'])}")
# Total facts: 23
```

**Implementation Details**:
- Generates query embedding using provided generator
- Executes vector search: `CALL QUERY_VECTOR_INDEX('Section', 'embedding_idx', $query_emb, $num_docs * 10)`
- Groups results by article, takes top `num_docs` articles
- Selects top `max_sections` most relevant sections per article
- Deduplicates and formats facts for synthesis

## FewShotManager

Manages and injects pack-specific few-shot examples.

### Constructor

```python
from wikigr.agent.few_shot import FewShotManager

manager = FewShotManager(
    pack_dir: str,
    num_examples: int = 3,
    cache: bool = True
)
```

**Parameters**:
- `pack_dir` (str): Path to knowledge pack directory (containing `few_shot_examples.json`)
- `num_examples` (int): Default number of examples to retrieve (default: 3)
- `cache` (bool): Cache loaded examples in memory (default: `True`)

**Raises**:
- `FileNotFoundError`: If `few_shot_examples.json` not found in `pack_dir`
- `json.JSONDecodeError`: If examples file is invalid JSON

### get_examples() Method

```python
examples = manager.get_examples(
    question: str,
    num_examples: int | None = None
) -> list[dict]
```

**Parameters**:
- `question` (str): Question to find relevant examples for
- `num_examples` (int, optional): Number of examples to return (defaults to constructor value)

**Returns**: List of few-shot examples, ranked by relevance

**Example**:

```python
manager = FewShotManager(pack_dir="data/packs/physics-expert")

examples = manager.get_examples(
    question="What is quantum mechanics?",
    num_examples=2
)

for ex in examples:
    print(f"Q: {ex['question']}")
    print(f"A: {ex['answer'][:100]}...")
    print()
```

### load_examples() Method

```python
all_examples = manager.load_examples() -> list[dict]
```

**Returns**: All examples from `few_shot_examples.json`

**Example File Format**:

```json
{
  "examples": [
    {
      "question": "What is quantum entanglement?",
      "context": {
        "articles": ["Quantum_entanglement", "EPR_paradox"],
        "facts": [
          "Quantum entanglement is a phenomenon...",
          "EPR paradox demonstrates quantum nonlocality..."
        ]
      },
      "answer": "Quantum entanglement is...",
      "reasoning": "Answer synthesizes information from both articles..."
    }
  ]
}
```

**Example Fields**:
- `question` (str, required): Example question
- `context` (dict, required): Retrieved context (articles, facts)
- `answer` (str, required): Expected answer with proper citations
- `reasoning` (str, optional): Explanation of answer quality

### format_for_prompt() Method

```python
formatted = manager.format_for_prompt(
    examples: list[dict]
) -> str
```

**Parameters**:
- `examples` (list[dict]): Examples to format

**Returns**: Formatted string for Claude prompt injection

**Example**:

```python
examples = manager.get_examples("What is quantum mechanics?", num_examples=2)
formatted = manager.format_for_prompt(examples)

print(formatted)
# === Example 1 ===
# Question: What is quantum entanglement?
# Context: [...]
# Answer: Quantum entanglement is...
#
# === Example 2 ===
# Question: What is the EPR paradox?
# Context: [...]
# Answer: The EPR paradox...
```

**Usage in Synthesis**:

```python
# Inject examples into Claude prompt
examples_text = manager.format_for_prompt(
    manager.get_examples(question, num_examples=3)
)

prompt = f"""
{examples_text}

Now answer this question following the same pattern:
Question: {question}
Context: {context}
Answer:
"""
```

## CrossEncoderReranker

Reranks vector search candidates by jointly scoring query-document pairs through a cross-encoder model, yielding +10-15% retrieval precision over bi-encoder search alone.

### Constructor

```python
from wikigr.agent.cross_encoder import CrossEncoderReranker

reranker = CrossEncoderReranker(
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
)
```

**Parameters**:
- `model_name` (str): HuggingFace cross-encoder model identifier. Defaults to `cross-encoder/ms-marco-MiniLM-L-12-v2` (33MB, CPU-only).

**Side effects**:
- First instantiation downloads ~33MB model weights to `~/.cache/huggingface/`.
- On any load failure: logs `WARNING` and sets `_model = None`; `rerank()` becomes a no-op passthrough.

**Attributes**:
- `_model`: Loaded `sentence_transformers.CrossEncoder` instance, or `None` if load failed.

### rerank() Method

```python
reranked_results = reranker.rerank(
    query: str,
    results: list[dict],
    top_k: int = 5
) -> list[dict]
```

**Parameters**:
- `query` (str): The search query.
- `results` (list[dict]): Candidate result dicts. Each dict should contain a `"content"` key (preferred) or `"title"` key used as the document text.
- `top_k` (int): Maximum results to return (default: 5).

**Returns**:

*Normal mode* (`_model` is not `None`):
List of up to `top_k` dicts sorted by `"ce_score"` descending. Each dict is a **shallow copy** of the input with `"ce_score": float` added. Input dicts are not mutated.

*Passthrough mode* (`_model` is `None`):
`list(results)` — full input, original order, no `ce_score`, no truncation.

**Example**:

```python
results = [
    {"title": "Quantum mechanics",  "content": "The study of matter at atomic scale."},
    {"title": "Classical mechanics","content": "Newton's laws of motion."},
    {"title": "Thermodynamics",     "content": "The study of heat and energy transfer."},
]

reranked = reranker.rerank(
    query="What governs the behaviour of subatomic particles?",
    results=results,
    top_k=2,
)

# [
#   {"title": "Quantum mechanics",  "content": "...", "ce_score": 9.14},
#   {"title": "Classical mechanics","content": "...", "ce_score": 1.83},
# ]
```

### Integration with KnowledgeGraphAgent

Enable via constructor flags:

```python
agent = KnowledgeGraphAgent(
    db_path="physics.db",
    use_enhancements=True,     # required
    enable_cross_encoder=True, # opt-in
)
```

When active, `_vector_primary_retrieve()` doubles the semantic search candidate pool
(`2 * max_results`) then calls `cross_encoder.rerank()` to reduce back to `max_results`:

```
semantic_search(query, k = max_results * 2)
    ↓
cross_encoder.rerank(query, candidates, top_k = max_results)
    ↓
top-max_results results ordered by ce_score
```

Check state at runtime:

```python
agent.cross_encoder          # CrossEncoderReranker | None
agent.cross_encoder._model   # sentence_transformers.CrossEncoder | None
```

## Integration Pattern

Recommended integration pattern for all three enhancements:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
from wikigr.agent.reranker import GraphReranker
from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer
from wikigr.agent.few_shot import FewShotManager

class EnhancedKGAgent(KnowledgeGraphAgent):
    """KG Agent with Phase 1 enhancements."""

    def __init__(self, db_path: str, pack_dir: str, **kwargs):
        super().__init__(db_path, **kwargs)

        if self.use_enhancements:
            # Initialize enhancement modules
            self.reranker = GraphReranker(self.conn)
            self.synthesizer = MultiDocSynthesizer(self.conn)
            self.few_shot = FewShotManager(pack_dir)

    def _enhanced_retrieve(self, question: str) -> dict:
        """Multi-doc retrieval with reranking."""
        # 1. Multi-doc retrieval
        context = self.synthesizer.retrieve(
            question,
            self._get_embedding_generator()
        )

        # 2. Rerank results
        reranked = self.reranker.rerank(
            [{"title": a["title"], "score": 1.0} for a in context["articles"]],
            top_k=5
        )

        # 3. Update context with reranked order
        title_order = [r["title"] for r in reranked]
        context["articles"] = sorted(
            context["articles"],
            key=lambda a: title_order.index(a["title"])
        )

        return context

    def _enhanced_synthesis(self, question: str, context: dict) -> str:
        """Synthesis with few-shot examples."""
        # Get relevant examples
        examples = self.few_shot.get_examples(question, num_examples=3)
        examples_text = self.few_shot.format_for_prompt(examples)

        # Build prompt with examples
        prompt = f"""
{examples_text}

Now answer this question following the same pattern:
Question: {question}
Context: {json.dumps(context, indent=2)}
Answer:
"""

        # Call Claude
        response = self.claude.messages.create(
            model="claude-opus-4-6",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )

        return response.content[0].text
```

## Performance Characteristics

### Latency Breakdown

| Operation | Baseline | Enhanced (default) | + Cross-Encoder | Overhead vs. baseline |
|-----------|----------|--------------------|-----------------|----------------------|
| Query Planning | 50ms | 50ms | 50ms | 0ms |
| Retrieval | 100ms | 400ms | 400ms | +300ms |
| Graph Reranking | — | 50ms | 50ms | +50ms |
| Cross-Encoder Rerank | — | — | 50ms | +50ms |
| Example Retrieval | — | 20ms | 20ms | +20ms |
| Synthesis | 150ms | 150ms | 150ms | 0ms |
| **Total** | **300ms** | **670ms** | **~720ms** | **+370ms / +420ms** |

Cross-encoder adds ~50ms on top of the default-enhanced pipeline — negligible versus 10-15s Opus synthesis.

### Memory Usage

| Component | Memory |
|-----------|--------|
| PageRank Cache | ~1 MB (for 500 articles) |
| Few-Shot Examples | ~10 KB (for 10 examples) |
| Multi-Doc Context | ~50 KB (5 articles × 3 sections) |
| **Total Overhead** | **~1-2 MB** |

### Memory Usage (with CrossEncoderReranker)

| Component | Memory |
|-----------|--------|
| PageRank Cache | ~1 MB (for 500 articles) |
| Few-Shot Examples | ~10 KB (for 10 examples) |
| Multi-Doc Context | ~50 KB (5 articles × 3 sections) |
| CrossEncoder model weights | ~120 MB RAM (33MB on disk) |
| **Total Overhead** | **~120-125 MB** |

### Scalability

- **GraphReranker**: O(V + E) for PageRank computation, O(N log N) for reranking
- **MultiDocSynthesizer**: O(K * log V) for K-NN search, scales linearly with `num_docs`
- **FewShotManager**: O(E) for example retrieval, where E = number of examples (typically 5-10)
- **CrossEncoderReranker**: O(C) per query where C = candidate pool size (`2 * max_results`); linear with candidate count

**Recommended Limits**:
- Pack size: Up to 1000 articles (larger packs increase PageRank computation time)
- `num_docs`: 3-7 (higher values increase latency and context size)
- `num_examples`: 2-5 (more examples increase prompt size)
- `max_results` with cross-encoder: up to 20 (40 candidate forward passes, ~180ms)

## Error Handling

All enhancement modules raise standard exceptions:

```python
# FileNotFoundError
manager = FewShotManager(pack_dir="nonexistent/")
# FileNotFoundError: few_shot_examples.json not found

# ValueError
reranker = GraphReranker(conn, alpha=0.5, beta=0.6)
# ValueError: alpha + beta must equal 1.0

# RuntimeError (Kuzu errors)
context = synthesizer.retrieve(question="test", embedding_generator=None)
# RuntimeError: Connection error or query execution failure
```

**Graceful Degradation**:

When enhancements fail, the KG Agent falls back to baseline retrieval:

```python
try:
    context = self._enhanced_retrieve(question)
except Exception as e:
    logger.warning(f"Enhanced retrieval failed: {e}. Using baseline.")
    context = self._baseline_retrieve(question)
```

## Testing

Test each enhancement module independently:

```python
# Test GraphReranker
from wikigr.agent.reranker import GraphReranker

def test_reranker():
    conn = kuzu.Connection(kuzu.Database("test.db"))
    reranker = GraphReranker(conn)

    results = [
        {"title": "Article_A", "score": 0.9},
        {"title": "Article_B", "score": 0.8}
    ]

    reranked = reranker.rerank(results, top_k=10)
    assert len(reranked) == 2
    assert all("score" in r for r in reranked)

# Test MultiDocSynthesizer
from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer

def test_synthesizer():
    conn = kuzu.Connection(kuzu.Database("test.db"))
    synthesizer = MultiDocSynthesizer(conn, num_docs=3)

    gen = EmbeddingGenerator()
    context = synthesizer.retrieve("What is X?", gen)

    assert "articles" in context
    assert "sections" in context
    assert len(context["articles"]) <= 3

# Test FewShotManager
from wikigr.agent.few_shot import FewShotManager

def test_few_shot():
    manager = FewShotManager(pack_dir="data/packs/test-pack")

    examples = manager.get_examples("What is X?", num_examples=2)
    assert len(examples) <= 2
    assert all("question" in ex for ex in examples)
```

## See Also

- [Phase 1 How-To Guide](../howto/phase1-enhancements.md) - Usage examples and troubleshooting
- [Knowledge Pack Evaluation](../howto/evaluate-pack-accuracy.md) - Measure accuracy improvements
- [KG Agent Documentation](./kg-agent.md) - Core agent API reference
- [CrossEncoderReranker Module](./module-docs/cross-encoder-reranker.md) - Detailed cross-encoder API reference
- [GraphReranker Module](./module-docs/graph-reranker.md) - Graph-based reranking reference
- [MultiDocSynthesizer Module](./module-docs/multidoc-synthesizer.md) - Multi-document retrieval reference
- [FewShotManager Module](./module-docs/few-shot-manager.md) - Few-shot example injection reference
