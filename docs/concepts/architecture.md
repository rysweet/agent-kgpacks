# Architecture

This page describes the system architecture of Knowledge Packs, including the data model, component interactions, and technology choices.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Interface Layer                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Python API   │  │  CLI (wikigr) │  │  Claude Code Skill   │  │
│  │  KG Agent     │  │  pack/query   │  │  Auto-discovered     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼──────────────────────┼──────────────┘
          │                 │                      │
          ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KnowledgeGraphAgent                            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Enhancement Layer                         │ │
│  │                                                             │ │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐   │ │
│  │  │ GraphReranker│ │MultiDocSynth.│ │  FewShotManager   │   │ │
│  │  │ (PageRank)   │ │ (5 articles) │ │  (3 examples)     │   │ │
│  │  └─────────────┘ └──────────────┘ └───────────────────┘   │ │
│  │                                                             │ │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐   │ │
│  │  │CrossEncoder  │ │ Multi-Query  │ │ Confidence Gate   │   │ │
│  │  │ Reranker     │ │ Retrieval    │ │ (threshold 0.5)   │   │ │
│  │  └─────────────┘ └──────────────┘ └───────────────────┘   │ │
│  │                                                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │           Content Quality Scoring                     │  │ │
│  │  │           (length + keyword filter)                    │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   Data Access Layer                         │ │
│  │                                                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │ │
│  │  │  Kuzu DB     │  │  Vector Index │  │  Anthropic API  │ │ │
│  │  │  (graph)     │  │  (HNSW)      │  │  (Claude)       │ │ │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Graph Database | Kuzu | 0.11.3+ | Embedded graph storage, Cypher queries |
| Embeddings | paraphrase-MiniLM-L3-v2 | - | 384-dim sentence embeddings |
| Vector Index | HNSW (via Kuzu) | - | Approximate nearest neighbor search |
| Synthesis Model | Claude Opus | claude-opus-4-6 | Answer generation, entity extraction |
| Query Expansion | Claude Haiku | claude-haiku-4-5 | Alternative query phrasing |
| Judge Model | Claude Haiku | claude-haiku-4-5 | Evaluation scoring (0-10) |
| Cross-Encoder | ms-marco-MiniLM-L-12-v2 | - | Joint query-document scoring |
| Runtime | Python | 3.10+ | Application language |
| Package Manager | uv | - | Dependency management |

### Why Kuzu?

Kuzu is an embedded, column-oriented graph database:

- **No server**: The database is a directory on disk, opened directly by the application
- **Cypher support**: Uses the openCypher query language
- **Vector index**: Built-in HNSW index for approximate nearest-neighbor search
- **Concurrent reads**: Multiple processes can read the same database simultaneously
- **Small footprint**: Typical pack databases are 1-50 MB

### Why BGE / MiniLM Embeddings?

The 384-dimensional model provides a good tradeoff between embedding quality and resource usage:

- **Fast**: Embeds a section in ~10ms on CPU
- **Small**: 384 dimensions keeps the HNSW index compact
- **Good quality**: Strong performance on semantic similarity benchmarks
- **Local**: Runs entirely on CPU, no GPU or API call required

## Data Model

### Node Types

```
┌─────────────────┐     HAS_SECTION      ┌─────────────────┐
│    Article       │────────────────────▶│    Section        │
│                 │                      │                  │
│ title: STRING   │                      │ heading: STRING  │
│ url: STRING     │                      │ content: STRING  │
│ content: STRING │                      │ embedding: FLOAT[]│
│ source: STRING  │                      └─────────────────┘
└────────┬────────┘
         │
         │ LINKS_TO
         ▼
┌─────────────────┐
│    Article       │
└─────────────────┘

┌─────────────────┐     HAS_ENTITY       ┌─────────────────┐
│    Article       │────────────────────▶│    Entity         │
│                 │                      │                  │
│                 │                      │ name: STRING     │
│                 │                      │ type: STRING     │
│                 │                      │ description: STR │
│                 │                      └────────┬────────┘
└─────────────────┘                               │
                                                  │ RELATES_TO
                                                  ▼
                                         ┌─────────────────┐
                                         │    Entity         │
                                         │                  │
                                         │ (label on edge)  │
                                         └─────────────────┘
```

### Article Node

| Property | Type | Description |
|----------|------|-------------|
| `title` | STRING | Document title (unique identifier) |
| `url` | STRING | Source URL |
| `content` | STRING | Full text content |
| `source` | STRING | Content source type ("web", "wikipedia") |

### Section Node

| Property | Type | Description |
|----------|------|-------------|
| `heading` | STRING | Section heading (h2/h3) |
| `content` | STRING | Section text content |
| `embedding` | FLOAT[384] | BGE vector embedding |

### Entity Node

| Property | Type | Description |
|----------|------|-------------|
| `name` | STRING | Entity name (e.g., "goroutine") |
| `type` | STRING | Entity type (e.g., "concept", "api", "type") |
| `description` | STRING | Brief description |

### Edge Types

| Edge | From | To | Properties |
|------|------|-----|-----------|
| `HAS_SECTION` | Article | Section | ordinal (section position) |
| `LINKS_TO` | Article | Article | (none) |
| `HAS_ENTITY` | Article | Entity | (none) |
| `RELATES_TO` | Entity | Entity | label (relationship type) |

## The Retrieval Pipeline

The full retrieval pipeline, with all enhancements enabled:

```
Question
  │
  ├──[enable_multi_query=True]──► Haiku generates 2 alternatives
  │                                │
  │                                ▼
  │                          3 queries instead of 1
  │
  └──[enable_multi_query=False]─► 1 query
         │
         ▼
  Vector Search (HNSW, top-K per query)
         │
         ▼
  Deduplication (title-based, keep highest similarity)
         │
         ▼
  Confidence Gate (max_similarity >= 0.5?)
         │
         ├── NO  ──► _synthesize_answer_minimal() (Claude alone)
         │
         └── YES ──► Continue pipeline
                      │
                      ▼
              [enable_cross_encoder]──► CrossEncoder rescoring
                      │
                      ▼
              [enable_reranker]──► GraphReranker (PageRank blend)
                      │
                      ▼
              [enable_multidoc]──► MultiDocSynthesizer (5 articles)
                      │
                      ▼
              Content Quality Filtering (score >= 0.3)
                      │
                      ▼
              [enable_fewshot]──► FewShotManager (inject examples)
                      │
                      ▼
              Claude Opus Synthesis
                      │
                      ▼
              Answer + Sources + Facts
```

## Configuration Profiles

| Setting | Baseline | Balanced (default) | Maximum Quality |
|---------|----------|-------------------|-----------------|
| `use_enhancements` | False | True | True |
| `enable_reranker` | - | True | True |
| `enable_multidoc` | - | True | True |
| `enable_fewshot` | - | True | True |
| `enable_cross_encoder` | - | False | True |
| `enable_multi_query` | - | False | True |
| Typical latency | ~300ms | ~670ms | ~750ms |
| Accuracy (evaluated) | 96.2% | 95.0% | 97.5% |

## Pack File Layout

Every pack follows a consistent directory structure:

```
data/packs/<pack-name>/
├── pack.db/              # Kuzu database directory (multiple files inside)
├── manifest.json         # Pack metadata, version, graph statistics
├── urls.txt              # Source URLs used to build the pack
├── skill.md              # Claude Code skill description
├── kg_config.json        # KG Agent configuration overrides
├── few_shot_examples.json # (optional) Curated examples for few-shot
└── eval/
    ├── questions.jsonl    # Evaluation questions with ground truth
    └── results/           # Evaluation output files
```
