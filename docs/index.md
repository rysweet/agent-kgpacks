# Agent Knowledge Packs

**Turn any documentation into an AI agent skill.**

Knowledge Packs are self-contained, domain-specific knowledge graphs that install as agent skills in Claude Code. Each pack bundles curated content from documentation into a local graph database with vector search — when the agent needs domain expertise, it retrieves grounded context from the pack instead of relying on training data.

```bash
# Build a pack from documentation URLs
echo "y" | uv run python scripts/build_go_pack.py

# Package and install as a skill
cd data/packs && tar -czf go-expert.tar.gz go-expert
wikigr pack install go-expert.tar.gz

# Now just ask Claude Code about Go — the skill activates automatically
```

---

## Why Knowledge Packs?

LLMs have three limitations that packs solve:

| Limitation | The Pack Fix |
|------------|-------------|
| **Training cutoff** — can't know about new APIs and versions | Packs ingest current documentation |
| **Depth gaps** — knows basics but misses implementation details | Packs contain full docs with section-level granularity |
| **Hallucination** — plausible but wrong answers on niche topics | Pack answers trace back to specific source articles |

## Evaluation: 99% Accuracy

48 packs evaluated across 2,716 questions (judged by Claude Opus):

| Metric | Training (Claude alone) | With Knowledge Pack |
|--------|:-----------------------:|:-------------------:|
| **Accuracy** | 91.7% | **99%** |
| **Pack wins** | — | **38 of 48 (79%)** |

See [full results](evaluation/results.md).

---

## The Pack Lifecycle

### 1. Describe — Choose a domain and curate URLs

Create `data/packs/my-pack/urls.txt` with 50-80 documentation URLs.

### 2. Build — Fetch, extract, embed, store

```bash
echo "y" | uv run python scripts/build_my_pack.py
```

### 3. Evaluate — Prove the pack adds value

```bash
uv run python scripts/eval_single_pack.py my-pack --sample 10
```

### 4. Package and Install — Register as an agent skill

```bash
cd data/packs && tar -czf my-pack.tar.gz my-pack
wikigr pack install my-pack.tar.gz
```

Packs install to `~/.wikigr/packs/` and auto-register as Claude Code skills. The agent automatically uses the pack when you ask domain questions.

### 5. Query — The skill activates automatically

In Claude Code, just ask. Or use the CLI:

```bash
uv run wikigr query "How does X work?" --pack my-pack
```

For the full walkthrough, see the **[Tutorial](getting-started/tutorial.md)**.

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

- **[Methodology](evaluation/methodology.md)** — How we measure pack quality
- **[Results](evaluation/results.md)** — Full accuracy data for all 48 packs
- **[Improving Accuracy](evaluation/improving-accuracy.md)** — Techniques that brought accuracy to 99%

### How-To Guides

- **[Build a Pack](howto/build-a-pack.md)** — Step-by-step from URLs to installed skill
- **[Run Evaluations](howto/run-evaluations.md)** — Single-pack and cross-pack evaluation
- **[Configure the Retrieval Pipeline](howto/configure-enhancements.md)** — Tuning retrieval modules

### Reference

- **[KG Agent API](reference/kg-agent-api.md)** — Constructor, query(), response format
- **[CLI Commands](reference/cli-commands.md)** — All `wikigr` commands
- **[Pack Manifest](reference/pack-manifest.md)** — manifest.json format
