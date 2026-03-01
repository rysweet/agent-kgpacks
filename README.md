# Agent Knowledge Packs

**Domain-specific knowledge graph databases that make AI coding assistants smarter.**

## The Problem: LLMs Have Blind Spots

Large language models like Claude are remarkably capable, but they have three fundamental limitations:

1. **Training cutoff** — Claude's knowledge has a fixed date. New frameworks, API changes, and version updates after that date are invisible.
2. **Depth gaps** — While Claude knows the basics of most technologies, it lacks the deep, expert-level detail found in official documentation, tutorials, and API references.
3. **Hallucination on niche topics** — Without grounding in authoritative sources, Claude may generate plausible-sounding but incorrect details about less common technologies.

**Knowledge Packs solve all three.** They are curated, domain-specific knowledge graph databases that provide up-to-date, deeply sourced content retrieved at query time. The KG Agent retrieves relevant sections from the pack and synthesizes answers grounded in actual documentation.

## Evaluation Results — 48 Packs, 2,716 Questions

| Metric | Training (Claude alone) | With Knowledge Pack |
|--------|:-----------------------:|:-------------------:|
| **Accuracy** | 91.7% | **99%** |
| **Delta** | — | **+7.3pp** |
| **Pack wins** | — | **38 of 48 (79%)** |

Packs are most impactful for niche or rapidly-evolving domains: workiq-mcp (+62pp), fabric-graphql (+23pp), claude-agent-sdk (+18pp). See [full results](https://rysweet.github.io/agent-kgpacks/evaluation/results/).

---

## Use a Pack with Claude Code

```bash
# Install
git clone https://github.com/rysweet/agent-kgpacks.git && cd agent-kgpacks
uv sync

# Build a pack
echo "y" | uv run python scripts/build_go_pack.py
```

Add the pack server to your Claude Code MCP config (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "knowledge-packs": {
      "command": "uv",
      "args": ["run", "python", "-m", "wikigr.mcp_server"],
      "env": { "PACK_DIR": "/path/to/agent-kgpacks/data/packs" }
    }
  }
}
```

Then just ask Claude Code domain questions — it automatically retrieves from the relevant pack.

## Use a Pack with GitHub Copilot

Start the pack API server and use it as a Copilot Chat skill:

```bash
# Start the server
uv run uvicorn backend.main:app --port 8000

# In VS Code with Copilot Chat:
# @knowledge-packs How do I configure Azure Bicep modules?
```

Or query the REST API directly:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I use Go generics with type constraints?", "pack": "go-expert"}'
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

### 1. Curate URLs

Create `data/packs/my-pack/urls.txt` with 50-80 documentation URLs:

```
# Official documentation
https://docs.example.com/guide/getting-started
https://docs.example.com/api/reference
https://docs.example.com/tutorials/advanced

# GitHub source (for JS-heavy sites that block scrapers)
https://github.com/example/repo/blob/main/README.md
https://raw.githubusercontent.com/example/repo/main/docs/guide.md
```

**Tips:**
- 50-80 URLs is ideal. More content = better retrieval.
- Prefer server-rendered pages over JS-heavy SPAs
- Add GitHub raw URLs as fallback for sites that block automated fetchers
- Cover: getting started, core concepts, API reference, tutorials, advanced topics

### 2. Build

```bash
echo "y" | uv run python scripts/build_my_pack.py
```

Expected runtime: 3-5 hours for 50-80 URLs with LLM extraction.

### 3. Evaluate

```bash
uv run python scripts/eval_single_pack.py my-pack --sample 10
```

See the **[full tutorial](https://rysweet.github.io/agent-kgpacks/getting-started/tutorial/)** for a complete walkthrough.

---

## When to Build a Knowledge Pack

Build a pack when:

- **The domain changes faster than training** — LangChain, Vercel AI SDK, OpenAI API
- **Claude's training coverage is thin** — Niche tools, internal frameworks, new projects
- **Expert-level depth matters** — Precise API signatures, configuration options, patterns
- **Grounding is critical** — Answers must be traceable to authoritative sources

Do NOT build a pack when:

- **Claude already knows the topic perfectly** — Stable technologies like Go, React, Python
- **The content is static** — Topics unchanged in years
- **The domain is too broad** — "All of computer science" is too broad; "Azure Bicep" is right

## How It Works

```
URLs (urls.txt)
    |
    v
[Fetch] ──> Web content scraper (requests/BeautifulSoup)
    |
    v
[Extract] ──> Claude Haiku extracts entities, relationships, facts
    |
    v
[Embed] ──> BGE bge-base-en-v1.5 generates 768-dim vectors
    |
    v
[Store] ──> Kuzu graph database with HNSW vector index
    |
    v
pack.db (distributable knowledge graph)
```

At query time:

```
Question ──> Vector Search ──> Confidence Gate ──> Cross-Encoder Rerank
    ──> Hybrid Retrieval ──> Quality Filter ──> Claude Synthesis ──> Answer
```

| Module | What it does |
|--------|-------------|
| **Confidence Gating** | Skips pack context when similarity < 0.5 (prevents noise) |
| **Cross-Encoder Reranking** | Neural pairwise relevance scoring (+10-15% precision) |
| **Multi-Query Retrieval** | Generates query reformulations (+15-25% recall) |
| **Content Quality Scoring** | Filters thin/irrelevant sections |
| **Graph Reranking** | Degree centrality boosts well-connected articles |
| **Multi-Doc Synthesis** | Follows graph edges for related context |

## Documentation

Full docs: **https://rysweet.github.io/agent-kgpacks/**

- [Getting Started](https://rysweet.github.io/agent-kgpacks/getting-started/overview/) — What packs are and when to use them
- [Tutorial](https://rysweet.github.io/agent-kgpacks/getting-started/tutorial/) — Build your first pack end-to-end
- [How to Build a Pack](https://rysweet.github.io/agent-kgpacks/howto/build-a-pack/) — Step-by-step guide
- [Evaluation Results](https://rysweet.github.io/agent-kgpacks/evaluation/results/) — Full accuracy data for all 48 packs
- [Evaluation Methodology](https://rysweet.github.io/agent-kgpacks/evaluation/methodology/) — How we measure pack quality
- [API Reference](https://rysweet.github.io/agent-kgpacks/reference/kg-agent-api/) — KnowledgeGraphAgent API

## License

MIT
