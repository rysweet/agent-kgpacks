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

Biggest gains on niche/rapidly-evolving domains: workiq-mcp (+62pp), fabric-graphql (+23pp), claude-agent-sdk (+18pp).

---

## The Pack Lifecycle

### 1. Describe — Choose a domain and curate URLs

```bash
mkdir -p data/packs/my-framework/eval
cat > data/packs/my-framework/urls.txt << 'EOF'
https://docs.myframework.dev/getting-started
https://docs.myframework.dev/api-reference
https://docs.myframework.dev/tutorials/advanced
https://github.com/myorg/myframework/blob/main/README.md
EOF
```

### 2. Build — Fetch, extract, embed, store

```bash
echo "y" | uv run python scripts/build_my_framework_pack.py
```

The build pipeline fetches each URL, uses Claude Haiku to extract entities/relationships/facts, generates BGE vector embeddings (768-dim), and stores everything in a LadybugDB graph database.

### 3. Evaluate — Prove the pack adds value

```bash
# Generate eval questions from pack content
uv run python scripts/generate_eval_questions.py --pack my-framework

# Run the evaluation (Training baseline vs Pack)
uv run python scripts/eval_single_pack.py my-framework --sample 10
```

### 4. Package — Create a distributable archive

```bash
cd data/packs && tar -czf my-framework.tar.gz my-framework
```

### 5. Install — Register as an agent skill

```bash
wikigr pack install my-framework.tar.gz
```

Packs install to `~/.wikigr/packs/` and auto-register as Claude Code skills via `skill.md`. Once installed, the agent automatically uses the pack when you ask domain questions.

### 6. Query — The skill activates automatically

In Claude Code, just ask a domain question:

```
You: "How do I configure middleware in MyFramework?"
# The my-framework skill activates, retrieves from the knowledge graph,
# and synthesizes a grounded answer with source citations
```

Or query from the command line:

```bash
uv run wikigr query "How do I configure middleware?" --pack my-framework
```

Or from Python:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

with KnowledgeGraphAgent(db_path="data/packs/my-framework/pack.db") as agent:
    result = agent.query("How do I configure middleware?")
    print(result["answer"])
    print("Sources:", result["sources"])
```

---

## How It Works

```
URLs ──> Fetch ──> Extract (Claude Haiku) ──> Embed (BGE) ──> Store (LadybugDB)
                                                                   |
                                                              pack.db + skill.md
                                                                   |
Question ──> Vector Search ──> Confidence Gate ──> Rerank ──> Synthesize ──> Answer
```

The retrieval pipeline includes:
- **Confidence gating** — skips the pack when it has nothing useful (prevents noise)
- **Cross-encoder reranking** — neural pairwise relevance scoring
- **Multi-query retrieval** — generates reformulated queries for better recall
- **Content quality scoring** — filters thin/irrelevant sections
- **Graph reranking** — boosts well-connected articles via degree centrality

## Quick Install

Add the `/kg-pack` skill to any Claude Code project with one command:

```bash
curl -sL https://raw.githubusercontent.com/rysweet/agent-kgpacks/main/scripts/install.sh | bash
```

Or clone the repo for building and querying packs locally:

```bash
git clone https://github.com/rysweet/agent-kgpacks.git
cd agent-kgpacks

# Query packs only (fast, ~50MB)
uv sync --no-extra

# Build new packs (full, ~2GB)
uv sync --extra build
```

Then in Claude Code:

```
/kg-pack list                           # 49 packs available
/kg-pack install rust-expert            # install Rust expertise
/kg-pack build "WebAssembly components" # build a new pack from scratch
/kg-pack query rust-expert "how do lifetimes work?"
```

Each installed pack becomes its own Claude Code skill that auto-activates when
you ask about that domain. See `skills/README.md` for details.

## Pack Management (CLI)

```bash
wikigr pack list                    # List installed packs
wikigr pack info go-expert          # Show pack details
wikigr pack eval go-expert          # Run evaluation
wikigr pack remove go-expert        # Uninstall
wikigr pack validate data/packs/go-expert  # Check structure
```

## Documentation

Full docs: **https://rysweet.github.io/agent-kgpacks/**

| Section | What you'll learn |
|---------|------------------|
| **[Pack Catalog](docs/catalog.md)** | Browse all 49 packs with stats, eval scores, and install commands |
| **[Overview](https://rysweet.github.io/agent-kgpacks/getting-started/overview/)** | What packs are and when to use them |
| **[Tutorial](https://rysweet.github.io/agent-kgpacks/getting-started/tutorial/)** | Build your first pack end-to-end |
| **[Build a Pack](https://rysweet.github.io/agent-kgpacks/howto/build-a-pack/)** | Step-by-step guide |
| **[Evaluation](https://rysweet.github.io/agent-kgpacks/evaluation/results/)** | Full accuracy data for 48 packs |
| **[How Packs Work](https://rysweet.github.io/agent-kgpacks/concepts/how-packs-work/)** | Architecture and retrieval pipeline |
| **[API Reference](https://rysweet.github.io/agent-kgpacks/reference/kg-agent-api/)** | KnowledgeGraphAgent API |

## License

[MIT](LICENSE)

## Repository Notes

**Clone size**: The repository includes ~520 MB of knowledge pack databases (`data/packs/*/pack.db`). For faster clones, use shallow clone:

```bash
git clone --depth 1 https://github.com/rysweet/agent-kgpacks.git
```

Migration to [Git LFS](https://git-lfs.com) for pack databases is planned for a future release.
