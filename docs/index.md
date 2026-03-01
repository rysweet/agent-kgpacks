# Agent Knowledge Packs

**Domain-specific knowledge graph databases that make AI coding assistants smarter.**

Knowledge Packs are curated, domain-specific knowledge graph databases that provide up-to-date, deeply sourced content retrieved at query time. They solve three LLM limitations:

1. **Training cutoff** — Models can't know about APIs, frameworks, or features released after training. Packs ingest current documentation and make it queryable.
2. **Depth gaps** — Training covers topics broadly but misses implementation details, edge cases, and advanced patterns. Packs contain full documentation with section-level granularity.
3. **Hallucination on niche topics** — Without grounding in authoritative sources, models generate plausible-sounding but incorrect details. Every pack answer traces back to specific articles and sections.

---

## Key Metrics

48 domain-specific packs evaluated across 2,716 questions:

| Metric | Training (Claude alone) | With Knowledge Pack |
|--------|:-----------------------:|:-------------------:|
| **Accuracy** | 91.7% | **99%** |
| **Avg Score** | 9.3/10 | **9.7/10** |
| **Pack wins** | — | **38 of 48 (79%)** |

Packs are most impactful for niche or rapidly-evolving domains. See [full results](evaluation/results.md).

---

## Use a Pack with Claude Code

```bash
# Install
git clone https://github.com/rysweet/agent-kgpacks.git && cd agent-kgpacks
uv sync

# Build a pack (e.g., Go expert)
echo "y" | uv run python scripts/build_go_pack.py

# Install the pack (registers as a Claude Code skill)
cd data/packs && tar -czf go-expert.tar.gz go-expert
wikigr pack install go-expert.tar.gz
```

Packs install to `~/.wikigr/packs/` and auto-register as Claude Code skills. Once installed, just ask domain questions -- the skill activates automatically:

```
You: "Explain how Go 1.23 range-over-func iterators work"
# Claude Code loads the go-expert skill, retrieves from the pack's
# knowledge graph, and synthesizes a grounded answer with citations
```

## Use a Pack with GitHub Copilot

Start the pack API server for use with Copilot Chat or any HTTP client:

```bash
uv run uvicorn backend.main:app --port 8000
```

Query via the REST API:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I use Go generics?", "max_results": 10}'
```

## Use a Pack with Python

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

with KnowledgeGraphAgent(db_path="data/packs/go-expert/pack.db") as agent:
    result = agent.query("What changed in Go 1.23 iterators?")
    print(result["answer"])
    print("Sources:", result["sources"])
```

---

## Build a New Pack

Full tutorial: **[How to Build a Pack](howto/build-a-pack.md)**

Quick version:

1. **Curate 50-80 documentation URLs** in `data/packs/my-pack/urls.txt`
2. **Build**: `echo "y" | uv run python scripts/build_my_pack.py`
3. **Evaluate**: `uv run python scripts/eval_single_pack.py my-pack --sample 10`

For a complete end-to-end walkthrough, see the **[Tutorial](getting-started/tutorial.md)**.

---

## Documentation

### Getting Started

- **[Overview](getting-started/overview.md)** — What packs are and when to use them
- **[Quick Start](getting-started/quickstart.md)** — Build and query your first pack in 5 minutes
- **[Tutorial](getting-started/tutorial.md)** — Complete walkthrough from domain selection to deployment

### Concepts

- **[How Packs Work](concepts/how-packs-work.md)** — Content pipeline, query pipeline, retrieval modules
- **[Architecture](concepts/architecture.md)** — System design, data model, technology stack
- **[Retrieval Pipeline](concepts/retrieval-pipeline.md)** — Each stage explained in detail

### Evaluation

- **[Methodology](evaluation/methodology.md)** — How we measure pack quality (scoring, conditions, judge model)
- **[Results](evaluation/results.md)** — Full accuracy data for all 48 packs
- **[Improving Accuracy](evaluation/improving-accuracy.md)** — The 7 techniques that brought accuracy to 99%

### How-To Guides

- **[Build a Pack](howto/build-a-pack.md)** — Step-by-step from URLs to evaluation
- **[Run Evaluations](howto/run-evaluations.md)** — Single-pack and cross-pack evaluation
- **[Configure the Retrieval Pipeline](howto/configure-enhancements.md)** — Tuning retrieval modules

### Reference

- **[KG Agent API](reference/kg-agent-api.md)** — Constructor, query(), response format
- **[CLI Commands](reference/cli-commands.md)** — All `wikigr` commands
- **[Pack Manifest](reference/pack-manifest.md)** — manifest.json format
