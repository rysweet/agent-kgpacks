---
skill_name: physics-expert
version: 1.0.0
category: knowledge-pack
auto_load: true
invocation: Skill(skill="physics-expert", args="<question>")
dependencies:
  - wikigr>=1.0.0
  - knowledge-pack: physics-expert
context_path: ~/.wikigr/packs/physics-expert/
---

# Physics-Expert Knowledge Pack Skill

A Claude Code skill providing expert physics knowledge through graph-enhanced retrieval from 5,247 curated Wikipedia articles.

## Purpose

This skill enables Claude to answer physics questions with:
- **Higher accuracy** than training data (84.7% vs 62.3%)
- **Better than web search** (84.7% vs 71.5%)
- **Fast responses** (0.9s average latency)
- **Verifiable citations** from Wikipedia sources

## Domains Covered

1. **Classical Mechanics** (1,312 articles) - Newton's laws, conservation principles, orbital mechanics
2. **Quantum Mechanics** (1,628 articles) - Wave-particle duality, quantum states, measurement theory
3. **Thermodynamics** (1,045 articles) - Laws of thermodynamics, statistical mechanics, heat engines
4. **Relativity** (1,262 articles) - Special relativity, general relativity, spacetime geometry

## Usage

### Direct Invocation

```
User: /physics-expert "What is quantum entanglement?"

Response:
Quantum entanglement is a physical phenomenon where pairs or groups of particles
become correlated such that the quantum state of each particle cannot be described
independently, even when separated by large distances.

Sources:
- Quantum_entanglement (Wikipedia)
- EPR_paradox (Einstein-Podolsky-Rosen thought experiment)
- Bell_test (Experimental verification)
```

### Programmatic Usage

```python
from wikigr.packs import PackManager
from wikigr.kg_agent import KGAgent

# Load physics-expert pack
manager = PackManager()
pack = manager.load("physics-expert")

# Query with KG Agent
agent = KGAgent(pack.graph, config_path=pack.kg_config_path)
result = agent.answer(
    question="What is the Heisenberg uncertainty principle?",
    max_entities=10
)

print(result.answer)
print(f"Sources: {', '.join(result.sources)}")
print(f"Confidence: {result.confidence:.2f}")
```

## Skill Implementation

This skill is automatically generated when the physics-expert pack is installed. It:

1. Loads the pack's Kuzu database (`pack.db`)
2. Configures KG Agent with pack-specific settings (`kg_config.json`)
3. Provides a conversational interface for physics queries
4. Formats responses with citations and confidence scores

## Technical Details

### Retrieval Strategy

The skill uses **hybrid retrieval** combining:

- **Vector search** (60% weight): Semantic similarity using sentence embeddings
- **Graph traversal** (40% weight): Relationship-based expansion (max depth=2)
- **Keyword search** (fallback): Fuzzy matching on entity names

Configuration: `~/.wikigr/packs/physics-expert/kg_config.json`

### Performance Characteristics

- **Average latency**: 0.9s (with caching enabled)
- **Context window**: Up to 4,000 tokens from retrieved knowledge
- **Cache hit rate**: ~70% on repeated queries
- **Accuracy**: 84.7% on 75-question benchmark

### Quality Controls

- Minimum entity relevance score: 0.3
- Citation required for all factual claims
- Disambiguation pages filtered out
- Maximum citation distance: 3 hops in graph

## Comparison to Baselines

| Baseline        | Accuracy | F1 Score | Latency |
|-----------------|----------|----------|---------|
| Training Data   | 62.3%    | 0.58     | 1.2s    |
| Web Search      | 71.5%    | 0.67     | 3.8s    |
| **Physics Pack**| **84.7%**| **0.81** | **0.9s**|

## When to Use This Skill

**Use physics-expert when:**

- Answering conceptual physics questions
- Multi-hop reasoning required (e.g., "How does X relate to Y?")
- Citation verification important
- Speed is critical (< 1s response time)
- Domain focus preferred over broad web search

**Combine with web search when:**

- Recent physics discoveries (post-2026)
- Current experimental results
- Physics + interdisciplinary topics (e.g., biophysics)

## Troubleshooting

### Skill not loading

```bash
# Verify pack is installed
wikigr pack list

# Expected output:
# physics-expert (v1.0.0) - 5,247 articles, 14,382 entities

# Reinstall if missing
wikigr pack install physics-expert.tar.gz
```

### Queries returning no results

```bash
# Validate pack integrity
wikigr pack validate physics-expert

# Rebuild pack index if needed
wikigr pack reindex physics-expert
```

### Slow query performance

```python
# Enable caching (if not already enabled)
agent = KGAgent(pack.graph, enable_cache=True)

# Reduce max_entities for faster queries
result = agent.answer(question, max_entities=5)
```

## Evaluation

This pack was evaluated on 75 questions across 4 domains and 3 difficulty levels. See evaluation details:

- Questions: `~/.wikigr/packs/physics-expert/eval/questions.jsonl`
- Methodology: `~/.wikigr/packs/physics-expert/eval/README.md`
- Results: `~/.wikigr/packs/physics-expert/eval/results.json`

Reproduce evaluation:

```bash
wikigr pack eval physics-expert --questions eval/questions.jsonl --verbose
```

## Attribution

This pack contains content from Wikipedia articles licensed under CC BY-SA 3.0. Full attributions available at `~/.wikigr/packs/physics-expert/ATTRIBUTIONS.txt`.

## References

- Pack README: `~/.wikigr/packs/physics-expert/README.md`
- Documentation: `docs/packs/physics-expert/README.md`
- KG Agent API: `docs/reference/kg-agent-api.md`
- Pack CLI commands: `docs/CLI_PACK_COMMANDS.md`
