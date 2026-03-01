# Overview

Knowledge Packs are self-contained, domain-specific knowledge graph databases that augment LLMs with curated, structured information. Each pack packages a Kuzu graph database, vector embeddings, retrieval configuration, and evaluation questions into a portable unit.

## What Problem Packs Solve

LLMs have three specific limitations that packs address:

### 1. Training Data Cutoff

Models are trained on data up to a fixed date. APIs change, frameworks release new versions, and documentation evolves. A pack built from current documentation gives the model access to information it has never seen during training.

**Example:** React 19 introduced `useActionState`, `useOptimistic`, and the `"use server"` directive. A model trained before React 19's release cannot answer questions about these features accurately. The `react-expert` pack contains the current React documentation and enables correct answers.

### 2. Depth Gaps

Training data covers topics broadly -- models know *about* most technologies. But they often lack the implementation-level detail needed for expert questions: specific API parameters, edge cases, version-specific behavior, and integration patterns.

**Example:** Claude knows what Go goroutines are, but may not know the exact behavior of `iter.Seq[V any]` introduced in Go 1.23. The `go-expert` pack contains the full Go standard library documentation with section-level detail.

### 3. Grounding and Provenance

When models answer from training data, there is no way to trace the answer back to a specific source. Pack-augmented answers include article titles and section references, making it possible to verify claims against the original documentation.

## When to Build a Pack

Use this decision framework to determine whether a pack will add value for a given domain:

| Question | If Yes | If No |
|----------|--------|-------|
| Does Claude already answer domain questions correctly? | Pack may not add value -- test first with eval | Good candidate for a pack |
| Is the content changing faster than training updates? | Strong candidate (APIs, framework docs, SDKs) | Lower priority |
| Is implementation-level depth important? | Pack adds section-level retrieval | General knowledge may suffice |
| Do you need source attribution? | Pack provides article-level provenance | Training-based answers are fine |
| Is the domain covered by public documentation? | Build from URLs | May need custom content sources |

**Strong pack candidates:**

- Framework SDKs with frequent releases (Vercel AI SDK, LangChain, LlamaIndex)
- Cloud platform services with evolving APIs (Azure, AWS)
- Programming languages with recent feature additions (Go 1.23, Zig 0.13)
- Specialized protocols and standards (MCP, OpenCypher)

## When NOT to Build a Pack

Packs add complexity. Do not build one when:

- **Claude already knows the topic well.** Stable, well-known topics like "what is TCP" or "explain binary search" get excellent answers from training alone. A pack would add latency without improving quality.
- **The topic is too broad.** A "general computer science" pack would need thousands of articles and still have gaps. Packs work best for focused domains.
- **The documentation is behind authentication.** Pack URLs must be publicly accessible. Private docs require custom content source implementations.

## Architecture at a Glance

```
┌──────────────────────────────────────────────────────────┐
│                    Knowledge Pack                         │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Kuzu Graph  │  │ BGE Vectors  │  │  Enhancement  │  │
│  │   Database   │  │  (HNSW idx)  │  │   Modules     │  │
│  │             │  │              │  │               │  │
│  │ Articles    │  │ Section      │  │ Reranker      │  │
│  │ Sections    │  │ embeddings   │  │ MultiDoc      │  │
│  │ Entities    │  │ 768-dim      │  │ FewShot       │  │
│  │ Relations   │  │ cosine sim   │  │ CrossEncoder  │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Retrieval Pipeline                    │   │
│  │  query -> vector search -> confidence gate ->     │   │
│  │  rerank -> multi-doc expand -> synthesize         │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Evaluation Framework                 │   │
│  │  questions.jsonl -> training | pack               │   │
│  │  -> judge scoring -> accuracy metrics             │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Technology | Role |
|-----------|-----------|------|
| **Graph Database** | Kuzu (embedded) | Stores articles, sections, entities, relationships as graph nodes and edges |
| **Vector Embeddings** | BAAI/bge-base-en-v1.5 (768-dim) | Enables semantic search over section content via HNSW index |
| **Synthesis** | Claude (Opus) | Generates natural language answers from retrieved context |
| **Query Expansion** | Claude (Haiku) | Generates alternative phrasings for multi-query retrieval |
| **Enhancement Modules** | Python classes | Confidence gating, cross-encoder reranking, graph reranking, multi-doc synthesis, few-shot examples, content quality scoring |

## Next Steps

- [Quick Start](quickstart.md) -- Build and query your first pack in 5 minutes
- [Tutorial](tutorial.md) -- Full lifecycle walkthrough from domain selection to deployment
- [How Packs Work](../concepts/how-packs-work.md) -- Deep dive into the content and retrieval pipelines
