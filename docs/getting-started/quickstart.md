# Quick Start

Build, install, and query a Knowledge Pack in under 5 minutes.

## Prerequisites

- **Python 3.12+**
- **uv** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Anthropic API key**: Set `ANTHROPIC_API_KEY` in your environment

## 1. Install Dependencies

```bash
git clone https://github.com/rysweet/agent-kgpacks.git
cd agent-kgpacks
uv sync
```

## 2. Set Your API Key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## 3. Build a Pack

Build the Go expert pack in test mode (fetches a small subset of URLs for speed):

```bash
echo "y" | uv run python scripts/build_go_pack.py --test-mode
```

This will:

1. Read URLs from `data/packs/go-expert/urls.txt`
2. Fetch each page and extract text content
3. Run LLM extraction to identify entities and relationships
4. Generate BGE embeddings for all sections
5. Store everything in a LadybugDB graph database at `data/packs/go-expert/pack.db`
6. Write `manifest.json` with pack metadata

!!! note "Build time"
    Test mode builds in 5-10 minutes. Full builds fetch all URLs and take 3-5 hours depending on pack size.

## 4. Query the Pack

Ask a question from the command line:

```bash
uv run wikigr query "What is goroutine scheduling?" --pack go-expert
```

Or use the Python API:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=True,
)

result = agent.query("What is goroutine scheduling?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

Or use the context manager form:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=True,
)

result = agent.query("What is goroutine scheduling?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

The agent will:

1. Embed your question using the same model used during ingestion
2. Search the vector index for relevant sections
3. Check confidence -- if similarity is too low, Claude answers from its own knowledge
4. If confidence is sufficient, retrieve multiple documents, rerank by graph authority, and synthesize an answer with source citations

## 5. Run an Evaluation

Evaluate the pack against the training baseline:

```bash
uv run python scripts/eval_single_pack.py go-expert --sample 5
```

This runs 5 questions from the pack's `eval/questions.jsonl` in two conditions:

- **Training**: Claude answers without any pack context
- **Pack**: Claude answers with full KG Agent retrieval pipeline

Output looks like:

```
Pack: go-expert
Questions: 5

Condition     Avg Score  Accuracy
──────────    ─────────  ────────
Training      8.7/10     90%
Pack          9.6/10     100%
Delta                    +10pp
```

!!! tip "Sample size"
    Use `--sample 5` for a quick check (~$0.15). For reliable results, use `--sample 25` or omit the flag to run all questions.

## 6. Install as a Claude Code Skill

Each pack can be installed as a Claude Code skill that auto-activates when you ask about that domain:

```bash
# Install skills for all packs
uv run python scripts/install_pack_skills.py

# Or use the /kg-pack command (if the skill is already installed)
# /kg-pack install go-expert
```

This creates `.claude/skills/go-expert/SKILL.md` which tells Claude how to query the Go knowledge graph whenever you ask Go questions.

## 7. Use the /kg-pack Skill Manager

Install the `/kg-pack` skill in any Claude Code project:

```bash
mkdir -p /your/project/.claude/skills/kg-pack
cp skills/kg-pack/SKILL.md /your/project/.claude/skills/kg-pack/
```

Then in Claude Code:

```
/kg-pack list                              # See all 49 available packs
/kg-pack install rust-expert               # Install Rust expertise
/kg-pack build "WebAssembly components"    # Build a new pack from scratch
/kg-pack query go-expert "how do goroutines work?"
```

## What Just Happened?

1. **Build**: The build script fetched Go documentation pages, extracted structured knowledge (entities, relationships, facts), generated vector embeddings, and stored everything in a LadybugDB graph database.

2. **Query**: The KG Agent embedded your question, searched the graph for relevant content, applied enhancement modules (reranking, multi-doc synthesis), and used Claude to synthesize a grounded answer.

3. **Eval**: The evaluation script asked the same questions to Claude with and without pack context, then used a judge model to score both answers against ground truth.

4. **Skill install**: The installer generated a SKILL.md file that tells Claude how and when to query the pack. Skills auto-activate in future sessions when you mention the domain.

## Next Steps

- [Tutorial](tutorial.md) -- Full lifecycle walkthrough including domain selection, URL curation, and result interpretation
- [Build a Pack](../howto/build-a-pack.md) -- Step-by-step guide for building packs from scratch
- [Run Evaluations](../howto/run-evaluations.md) -- Understanding the evaluation framework
