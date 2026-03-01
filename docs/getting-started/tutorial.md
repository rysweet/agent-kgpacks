# Tutorial: Full Pack Lifecycle

This tutorial walks through the complete lifecycle of a Knowledge Pack, from choosing a domain through evaluation and improvement. By the end, you will understand how to build, evaluate, and iterate on packs.

## Step 1: Choose a Domain

The best pack domains have these characteristics:

- **Focused scope**: A single framework, library, language, or service -- not "all of programming"
- **Public documentation**: URLs must be accessible without authentication
- **Depth available**: The documentation has enough detail to go beyond what Claude already knows
- **Active development**: The content changes faster than model training cycles

**Good examples**: `go-expert`, `react-expert`, `langchain-expert`, `vercel-ai-sdk`

**Poor examples**: "general CS knowledge" (too broad), internal company docs (not public), Wikipedia articles on well-known topics (Claude already knows them)

## Step 2: Curate Source URLs

Create a `urls.txt` file listing the documentation pages to ingest. This is the most important step -- pack quality depends directly on source quality.

### File Format

One URL per line. Use `#` comments for section headers:

```
# Go Programming Language - Official Documentation
# Covers: stdlib, generics, iterators, slog, error handling, concurrency

# Core Documentation
https://go.dev/doc/
https://go.dev/doc/effective_go
https://go.dev/ref/spec

# Standard Library
https://pkg.go.dev/std
https://pkg.go.dev/slices
https://pkg.go.dev/maps

# Tutorials and Guides
https://gobyexample.com/
https://go.dev/blog/range-over-function
https://go.dev/blog/slog

# GitHub - Source Examples
https://github.com/golang/go/blob/master/src/slices/slices.go
```

### Tips for Good URL Coverage

| Section | What to Include |
|---------|----------------|
| **Overview** | Root documentation page, architecture overview |
| **Concepts** | Core concepts, design philosophy |
| **Getting Started** | Quickstart, installation, first steps |
| **API Reference** | Top-level reference + major sub-categories |
| **How-To Guides** | Task-oriented guides for common problems |
| **Tutorials** | Step-by-step learning material |
| **GitHub** | README, key source files, examples |

!!! warning "URL requirements"
    - All URLs must use `https://` (no plain HTTP)
    - All URLs must be publicly accessible without credentials
    - Never include API keys or tokens in URL parameters

### Recommended URL Counts

| Pack Complexity | Minimum | Recommended |
|-----------------|---------|-------------|
| Focused library (single SDK) | 30 | 45-60 |
| Framework with integrations | 50 | 65-80 |
| Full platform (RAG + agents) | 50 | 70-90 |
| Language reference | 30 | 45-60 |

## Step 3: Build the Pack

Each pack has a build script. For a new domain, you can use an existing script as a template:

```bash
# Build in test mode first (subset of URLs, faster)
echo "y" | uv run python scripts/build_go_pack.py --test-mode

# Full build (all URLs)
echo "y" | uv run python scripts/build_go_pack.py
```

### What Happens During Build

```
urls.txt
  │
  ▼
Fetch HTML/Markdown from each URL
  │
  ▼
Extract text content (strip navigation, headers, footers)
  │
  ▼
LLM extraction (Claude) → entities, relationships, facts
  │
  ▼
Generate BGE embeddings for each section (768-dim vectors)
  │
  ▼
Store in Kuzu graph database:
  - Article nodes (title, category, word_count)
  - Section nodes (title, content, embedding)
  - Entity nodes (name, type, description)
  - Fact nodes (content)
  - Relationship edges (entity → entity)
  - LINKS_TO edges (article → article)
  │
  ▼
Write manifest.json with metadata
```

### Build Output

```
data/packs/go-expert/
├── pack.db/            # Kuzu database directory
├── manifest.json       # Pack metadata (name, version, stats)
├── urls.txt            # Source URLs (input)
├── skill.md            # Claude Code skill description
├── kg_config.json      # KG Agent configuration
└── eval/
    ├── questions.jsonl  # Evaluation questions
    └── results/         # Evaluation output
```

## Step 4: Understand the Manifest

After building, inspect `manifest.json`:

```json
{
  "name": "go-expert",
  "version": "1.0.0",
  "description": "Expert Go programming knowledge covering Go 1.22+ features...",
  "graph_stats": {
    "articles": 16,
    "entities": 106,
    "relationships": 69,
    "size_mb": 2.08
  },
  "source_urls": [
    "https://go.dev/doc/",
    "https://gobyexample.com/",
    "https://go.dev/blog/"
  ],
  "created": "2026-03-01T16:40:06Z",
  "license": "MIT"
}
```

Key fields:

- `graph_stats.articles`: Number of documents ingested -- should match your URL count roughly
- `graph_stats.entities`: Named concepts extracted by the LLM
- `graph_stats.relationships`: Connections between entities
- `graph_stats.size_mb`: Database size on disk

## Step 5: Write Evaluation Questions

Evaluation questions live in `eval/questions.jsonl` (one JSON object per line):

```json
{"id": "ge_001", "domain": "go_expert", "difficulty": "easy", "question": "What does slices.Contains do, and what constraint must E satisfy?", "ground_truth": "slices.Contains reports whether v is present in s. E must satisfy the comparable constraint.", "source": "slices_stdlib"}
{"id": "ge_002", "domain": "go_expert", "difficulty": "medium", "question": "What is iter.Seq[V any] and what is its underlying function signature?", "ground_truth": "iter.Seq[V any] is a type alias for func(yield func(V) bool). It represents a sequence that yields values one at a time.", "source": "iterators"}
{"id": "ge_003", "domain": "go_expert", "difficulty": "hard", "question": "How does the Go runtime schedule goroutines across OS threads?", "ground_truth": "Go uses an M:N scheduling model with M goroutines multiplexed onto N OS threads, managed by the runtime scheduler using work-stealing.", "source": "runtime_scheduling"}
```

### Question Format

| Field | Description |
|-------|-------------|
| `id` | Unique identifier with pack prefix (e.g., `ge_001`) |
| `domain` | Snake-case domain name (e.g., `go_expert`) |
| `difficulty` | One of `easy`, `medium`, `hard` |
| `question` | The question text |
| `ground_truth` | Expected correct answer (used for judge scoring) |
| `source` | Topic slug within the pack |

### Question Design Guidelines

- **Test pack-specific knowledge**, not general knowledge Claude already has
- **Use exact terminology** from the documentation (e.g., `VectorStoreIndex` not "vector store index")
- **Target current versions** -- do not ask about deprecated or removed features
- **Distribute difficulty**: 20 easy / 20 medium / 10 hard (for a 50-question set)

!!! tip "Auto-generation"
    Use the generation script to create initial questions, then manually review and improve:
    ```bash
    python scripts/generate_eval_questions.py --pack go-expert --count 50
    ```

## Step 6: Run Evaluation

### Single Pack

```bash
# Quick check (5 questions)
uv run python scripts/eval_single_pack.py go-expert --sample 5

# Full evaluation (all questions)
uv run python scripts/eval_single_pack.py go-expert
```

### All Packs

```bash
# Sample across all packs
uv run python scripts/run_all_packs_evaluation.py --sample 10
```

### Understanding the Two Conditions

| Condition | What It Tests |
|-----------|--------------|
| **Training** | Claude answers with no pack context (pure training data) |
| **Pack** | KG Agent retrieves from pack and synthesizes with the full retrieval pipeline |

## Step 7: Interpret Results

After running evaluation, you will see output like:

```
Pack: go-expert  (10 questions)

Condition     Avg Score  Accuracy
──────────    ─────────  ────────
Training      8.7/10     90.0%
Pack          9.6/10     100.0%
```

### What the Numbers Mean

- **Avg Score**: Mean judge score across all questions (0-10 scale)
- **Accuracy**: Percentage of questions scored >= 7 by the judge
- **Delta** (Pack - Training): Positive means the pack adds value

### Interpreting Deltas

| Delta | Interpretation |
|-------|----------------|
| +5pp or more | Strong improvement -- pack clearly adds value |
| +1pp to +5pp | Moderate improvement -- pack helps on some questions |
| 0pp | Neutral -- pack matches training quality |
| Negative | Pack hurts accuracy -- investigate question quality or retrieval issues |

!!! warning "Negative deltas"
    A negative delta usually means one of:

    - **Bad retrieval**: The pack returns irrelevant content that confuses synthesis
    - **Bad questions**: Questions test general knowledge, not pack-specific content
    - **Content quality**: Source URLs have thin or noisy content

    See [Improving Accuracy](../evaluation/improving-accuracy.md) for solutions.

## Step 8: Improve the Pack

If results are unsatisfactory, apply these improvements (from Issue #211):

1. **Confidence-gated context injection** -- Skip pack content when similarity is low, letting Claude use its own knowledge
2. **Cross-encoder reranking** -- Replace bi-encoder similarity with joint query-document scoring
3. **Multi-query retrieval** -- Generate alternative phrasings to catch vocabulary mismatches
4. **Content quality scoring** -- Filter out stub sections that add noise
5. **URL list expansion** -- Add more source URLs to improve coverage
6. **Eval question calibration** -- Replace generic questions with pack-specific ones
7. **Full pack rebuilds** -- Re-ingest after URL expansion

See [Improving Accuracy](../evaluation/improving-accuracy.md) for detailed instructions on each.

## Step 9: Deploy for Use

Once a pack meets your accuracy targets, it is ready for use:

### In Python Code

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/go-expert/pack.db",
    use_enhancements=True,
)

result = agent.query("How do Go iterators work in 1.23?")
print(result["answer"])
```

### Via Python (Context Manager)

```python
with KnowledgeGraphAgent(db_path="data/packs/go-expert/pack.db") as agent:
    result = agent.query("How do Go iterators work?")
    print(result["answer"])
```

### As a Claude Code Skill

Packs include a `skill.md` file that Claude Code auto-discovers when installed to `~/.wikigr/packs/`. The skill enhances Claude's responses with graph-retrieved context whenever questions match the pack's domain.

## Summary

| Step | Action | Output |
|------|--------|--------|
| 1 | Choose domain | Decision on scope |
| 2 | Curate URLs | `urls.txt` with 30-90 source URLs |
| 3 | Build pack | `pack.db`, `manifest.json` |
| 4 | Review manifest | Verify article/entity counts |
| 5 | Write eval questions | `eval/questions.jsonl` |
| 6 | Run evaluation | Accuracy scores per condition |
| 7 | Interpret results | Identify improvement areas |
| 8 | Improve | Apply enhancements, rebuild |
| 9 | Deploy | Use via Python, CLI, or Claude Code |
