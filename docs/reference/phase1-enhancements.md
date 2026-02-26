# Phase 1 Enhancements: API Reference

Complete API reference for the Phase 1 retrieval enhancement modules.

## Overview

Phase 1 enhancements consist of three independent modules:

| Module | Purpose | Accuracy Impact |
|--------|---------|-----------------|
| `GraphReranker` | Rerank results using graph centrality | +5-10% |
| `MultiDocSynthesizer` | Multi-document retrieval | +10-15% |
| `FewShotManager` | Pack-specific example injection | +5-10% |

**Combined Impact**: 50% baseline → 70-75% accuracy

## KnowledgeGraphAgent API

### Constructor

```python
KnowledgeGraphAgent(
    db_path: str,
    anthropic_api_key: str | None = None,
    read_only: bool = True,
    use_enhancements: bool = False  # NEW: Enable Phase 1 enhancements
)
```

**Parameters**:
- `db_path` (str): Path to Kuzu database file
- `anthropic_api_key` (str, optional): Anthropic API key (or from `ANTHROPIC_API_KEY` env var)
- `read_only` (bool): Open database in read-only mode (default: `True`)
- `use_enhancements` (bool): Enable Phase 1 retrieval enhancements (default: `False`)

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
from wikigr.agent.enhancements.graph_reranker import GraphReranker

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
from wikigr.agent.enhancements.multidoc_synthesizer import MultiDocSynthesizer

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
from wikigr.agent.enhancements.few_shot_manager import FewShotManager

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

## Integration Pattern

Recommended integration pattern for all three enhancements:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
from wikigr.agent.enhancements import (
    GraphReranker,
    MultiDocSynthesizer,
    FewShotManager
)

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
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )

        return response.content[0].text
```

## Performance Characteristics

### Latency Breakdown

| Operation | Baseline | Enhanced | Overhead |
|-----------|----------|----------|----------|
| Query Planning | 50ms | 50ms | 0ms |
| Retrieval | 100ms | 400ms | +300ms |
| Reranking | - | 50ms | +50ms |
| Example Retrieval | - | 20ms | +20ms |
| Synthesis | 150ms | 150ms | 0ms |
| **Total** | **300ms** | **670ms** | **+370ms** |

### Memory Usage

| Component | Memory |
|-----------|--------|
| PageRank Cache | ~1 MB (for 500 articles) |
| Few-Shot Examples | ~10 KB (for 10 examples) |
| Multi-Doc Context | ~50 KB (5 articles × 3 sections) |
| **Total Overhead** | **~1-2 MB** |

### Scalability

- **GraphReranker**: O(V + E) for PageRank computation, O(N log N) for reranking
- **MultiDocSynthesizer**: O(K * log V) for K-NN search, scales linearly with `num_docs`
- **FewShotManager**: O(E) for example retrieval, where E = number of examples (typically 5-10)

**Recommended Limits**:
- Pack size: Up to 1000 articles (larger packs increase PageRank computation time)
- `num_docs`: 3-7 (higher values increase latency and context size)
- `num_examples`: 2-5 (more examples increase prompt size)

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
from wikigr.agent.enhancements.graph_reranker import GraphReranker

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
from wikigr.agent.enhancements.multidoc_synthesizer import MultiDocSynthesizer

def test_synthesizer():
    conn = kuzu.Connection(kuzu.Database("test.db"))
    synthesizer = MultiDocSynthesizer(conn, num_docs=3)

    gen = EmbeddingGenerator()
    context = synthesizer.retrieve("What is X?", gen)

    assert "articles" in context
    assert "sections" in context
    assert len(context["articles"]) <= 3

# Test FewShotManager
from wikigr.agent.enhancements.few_shot_manager import FewShotManager

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
