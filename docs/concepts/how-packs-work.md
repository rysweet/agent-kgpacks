# How Packs Work

This page explains the two core pipelines that power Knowledge Packs: the **content pipeline** (building a pack) and the **query pipeline** (answering questions from a pack).

## Content Pipeline: Building a Pack

The content pipeline transforms a list of URLs into a queryable knowledge graph.

```
urls.txt
  │
  ▼
┌──────────────────────────────────────────────────────┐
│  1. FETCH                                            │
│  HTTP GET each URL → extract HTML/Markdown content   │
│  Strip navigation, footers, sidebars                 │
│  Parse into title + sections                         │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  2. LLM EXTRACTION                                   │
│  Claude analyzes each section and extracts:           │
│  • Entities (named concepts, APIs, types)             │
│  • Relationships (entity → entity with label)         │
│  • Facts (key statements about each entity)           │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  3. EMBED                                            │
│  BGE / paraphrase-MiniLM-L3-v2 generates             │
│  384-dimension vectors for each section              │
│  Vectors enable cosine similarity search             │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  4. STORE                                            │
│  Kuzu embedded graph database:                        │
│  • Article nodes (title, url, content)                │
│  • Section nodes (heading, content, embedding)        │
│  • Entity nodes (name, type, description)             │
│  • Relationship edges (entity→entity with label)      │
│  • LINKS_TO edges (article→article)                   │
│  • HNSW vector index on section embeddings            │
└──────────────────────────────────────────────────────┘
```

### Fetch Stage

The fetcher downloads each URL and extracts text content. It handles:

- HTML pages (strips scripts, styles, navigation)
- Markdown files (parsed directly)
- GitHub blob URLs (extracts rendered content)
- Raw GitHub URLs (downloads raw text)

Each URL becomes one **Article** node in the graph. Articles are split into **Section** nodes based on heading structure (h2/h3 in HTML, ## / ### in Markdown).

### LLM Extraction Stage

Claude analyzes each section's content and extracts structured knowledge:

- **Entities**: Named concepts like "goroutine", "channel", "sync.WaitGroup"
- **Relationships**: Connections like "goroutine COMMUNICATES_VIA channel"
- **Facts**: Key statements like "goroutines are multiplexed onto OS threads"

This creates the graph structure that enables graph-based retrieval and reranking.

### Embedding Stage

Each section's text content is passed through the embedding model to produce a 384-dimensional vector. These vectors are stored alongside the section nodes and indexed using an HNSW (Hierarchical Navigable Small World) index for fast approximate nearest-neighbor search.

### Storage Stage

All data is written to a Kuzu embedded graph database. Kuzu is a column-oriented graph database that requires no external server -- the database is a directory on disk that can be opened directly by the application.

## Query Pipeline: Answering Questions

When a user asks a question, the query pipeline retrieves relevant content from the pack and synthesizes an answer.

```
User Question: "What is goroutine scheduling?"
  │
  ▼
┌──────────────────────────────────────────────────────┐
│  1. VECTOR SEARCH                                    │
│  Embed question → HNSW index search → top-K sections │
│  Returns sections ranked by cosine similarity         │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  2. CONFIDENCE GATE                                  │
│  Check max_similarity against threshold (0.5)         │
│  If too low → skip pack, let Claude answer alone      │
│  If sufficient → proceed with pack context            │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  3. HYBRID RETRIEVAL                                 │
│  Graph reranking (PageRank authority)                  │
│  Multi-document expansion (5 articles)                │
│  Content quality filtering (remove stubs)             │
│  Cross-encoder reranking (optional)                   │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│  4. SYNTHESIS                                        │
│  Few-shot examples → format guidance                  │
│  Retrieved context → Claude Opus synthesis             │
│  Answer with source citations                         │
└──────────────────────────────────────────────────────┘
```

### Vector Search

The question is embedded using the same model used during ingestion. The HNSW index returns the top-K most similar sections by cosine similarity. Default K=5.

### Confidence Gate

Before injecting retrieved content into the synthesis prompt, the agent checks whether the best result is actually relevant. If `max_similarity < 0.5`, the retrieved content is likely off-topic -- injecting it would confuse Claude. In this case, the agent skips pack context entirely and lets Claude answer from its own training.

This prevents accuracy regressions on questions outside the pack's domain.

### Hybrid Retrieval

When confidence is sufficient, multiple enhancement modules process the results:

| Module | What It Does | Impact |
|--------|-------------|--------|
| **GraphReranker** | Reranks by `0.7 * similarity + 0.3 * PageRank` to promote authoritative articles | +5-10% accuracy |
| **MultiDocSynthesizer** | Expands from 1 article to 5, extracting top 3 sections each | +10-15% accuracy |
| **Content Quality Scoring** | Filters sections < 20 words or below quality threshold (0.3) | Reduces noise ~30% |
| **CrossEncoderReranker** | Joint query-document scoring for precise relevance ranking (opt-in) | +10-15% retrieval precision |
| **Multi-Query Retrieval** | Generates 2 alternative phrasings via Haiku, fans out search (opt-in) | +15-25% recall |

### Synthesis

The retrieved context, optional few-shot examples, and the user's question are assembled into a prompt for Claude Opus. The model generates a natural language answer grounded in the retrieved content, with source citations.

## Enhancement Modules in Detail

### Confidence-Gated Context Injection

```
max_similarity >= 0.5  →  full pipeline (pack context injected)
max_similarity < 0.5   →  _synthesize_answer_minimal() (Claude alone)
```

The gate fires on questions outside the pack's coverage area. When it fires, the response includes `query_type: "confidence_gated_fallback"` and empty source lists.

### Cross-Encoder Reranking

Bi-encoder search (embedding similarity) scores query and document independently. Cross-encoders score the pair jointly, enabling them to handle negations, comparisons, and nuanced phrasing.

When enabled, vector search fetches 2x candidates, the cross-encoder rescores them, and only the top-K survive.

### Multi-Query Retrieval

A single query embedding may miss content that uses different vocabulary. Multi-query generates 2 alternative phrasings using Claude Haiku, then runs semantic search for all 3 queries. Results are deduplicated by title (highest similarity wins).

### Content Quality Scoring

Sections are scored on a 0.0-1.0 scale combining length and keyword overlap:

```
score = min(1.0, length_score + keyword_score)
length_score  = min(0.8, 0.2 + (word_count / 200) * 0.6)
keyword_score = min(0.2, overlap_ratio * 0.2)
```

Sections below 20 words always score 0.0. Sections below the threshold (0.3) are filtered from synthesis context.

### Graph Reranking

PageRank is computed over the LINKS_TO edge graph. Articles with many incoming links are considered more authoritative. The combined score balances semantic relevance and authority:

```
combined_score = 0.7 * vector_similarity + 0.3 * normalized_pagerank
```

### Multi-Document Synthesis

Instead of synthesizing from a single article, the agent retrieves the top 5 articles and extracts the 3 most relevant sections from each. This provides broader coverage and reduces the chance of missing important information.

### Few-Shot Examples

Pack-specific examples (from `few_shot_examples.json` or `eval/questions.jsonl`) are injected into the synthesis prompt. These guide Claude to follow the pack's preferred answer format, citation style, and reasoning structure.
