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
│  │  │ (centrality) │ │ (LINKS_TO)   │ │  (2 examples)     │   │ │
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
| Embeddings | BAAI/bge-base-en-v1.5 | - | 768-dim sentence embeddings (local, CPU) |
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

### Why BAAI/bge-base-en-v1.5 Embeddings?

The 768-dimensional model provides a good tradeoff between embedding quality and resource usage:

- **Fast**: Embeds a section in ~10ms on CPU
- **Quality**: Strong performance on MTEB semantic similarity benchmarks
- **768 dimensions**: Good quality while keeping the HNSW index manageable
- **Local**: Runs entirely on CPU, no GPU or API call required

## Data Model

### Node Types

```
┌─────────────────┐     HAS_SECTION      ┌──────────────────────┐
│    Article       │────────────────────▶│    Section              │
│                 │  (section_index)     │                        │
│ title: STRING   │                      │ section_id: STRING (PK)│
│ category: STRING│                      │ title: STRING          │
│ word_count: INT │                      │ content: STRING        │
│ ...             │                      │ embedding: DOUBLE[768] │
└────────┬────────┘                      └──────────────────────┘
         │
         │ LINKS_TO (link_type)
         ▼
┌─────────────────┐
│    Article       │
└─────────────────┘

┌─────────────────┐     HAS_ENTITY       ┌─────────────────┐
│    Article       │────────────────────▶│    Entity         │
│                 │                      │                  │
│                 │     HAS_FACT         │ entity_id: STR   │
│                 │────────▶ Fact        │ name: STRING     │
│                 │                      │ type: STRING     │
│                 │     IN_CATEGORY      │ description: STR │
│                 │────────▶ Category    └────────┬────────┘
└─────────────────┘                               │
                                                  │ ENTITY_RELATION
                                                  ▼
                                         ┌─────────────────┐
                                         │    Entity         │
                                         │                  │
                                         │ (relation, context│
                                         │  on edge)         │
                                         └─────────────────┘
```

### Article Node

| Property | Type | Description |
|----------|------|-------------|
| `title` | STRING | Document title (primary key) |
| `category` | STRING | Article category |
| `word_count` | INT32 | Total word count |
| `expansion_state` | STRING | Build pipeline state ("discovered", "expanded", etc.) |
| `expansion_depth` | INT32 | Graph expansion depth from seed |
| `claimed_at` | TIMESTAMP | When article was claimed for processing |
| `processed_at` | TIMESTAMP | When article processing completed |
| `retry_count` | INT32 | Number of processing retries |

### Section Node

| Property | Type | Description |
|----------|------|-------------|
| `section_id` | STRING | Unique section identifier (primary key) |
| `title` | STRING | Section title (h2/h3) |
| `content` | STRING | Section text content |
| `embedding` | DOUBLE[768] | BGE vector embedding |
| `level` | INT32 | Heading level |
| `word_count` | INT32 | Section word count |

### Entity Node

| Property | Type | Description |
|----------|------|-------------|
| `entity_id` | STRING | Unique entity identifier (primary key) |
| `name` | STRING | Entity name (e.g., "goroutine") |
| `type` | STRING | Entity type (e.g., "concept", "api", "type") |
| `description` | STRING | Brief description |

### Fact Node

| Property | Type | Description |
|----------|------|-------------|
| `fact_id` | STRING | Unique fact identifier (primary key) |
| `content` | STRING | Fact text content |

### Chunk Node

| Property | Type | Description |
|----------|------|-------------|
| `chunk_id` | STRING | Unique chunk identifier (primary key) |
| `content` | STRING | Chunk text content |
| `embedding` | DOUBLE[768] | BGE vector embedding |
| `article_title` | STRING | Parent article title |
| `section_index` | INT32 | Parent section index |
| `chunk_index` | INT32 | Position within section |

### Category Node

| Property | Type | Description |
|----------|------|-------------|
| `name` | STRING | Category name (primary key) |
| `article_count` | INT32 | Number of articles in this category |

### Edge Types

| Edge | From | To | Properties |
|------|------|-----|-----------|
| `HAS_SECTION` | Article | Section | section_index (INT32) |
| `LINKS_TO` | Article | Article | link_type (STRING) |
| `IN_CATEGORY` | Article | Category | (none) |
| `HAS_ENTITY` | Article | Entity | (none) |
| `HAS_FACT` | Article | Fact | (none) |
| `ENTITY_RELATION` | Entity | Entity | relation (STRING), context (STRING) |
| `HAS_CHUNK` | Article | Chunk | section_index (INT32), chunk_index (INT32) |

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
              [enable_reranker]──► GraphReranker (degree centrality blend via RRF)
                      │
                      ▼
              [enable_multidoc]──► MultiDocSynthesizer (LINKS_TO expansion)
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
└── eval/
    ├── questions.jsonl    # Evaluation questions (also used for few-shot examples)
    └── results/           # Evaluation output files
```
