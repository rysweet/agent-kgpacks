# WikiGR - Wikipedia Knowledge Graph

Build topic-specific knowledge graphs from Wikipedia. Query them with natural language, semantic search, graph traversal, or a web UI.

## What It Does

Give WikiGR a list of topics. It fetches Wikipedia articles, extracts entities and relationships using Claude, generates vector embeddings, and stores everything in an embedded Kuzu graph database. You can then:

- **Ask questions in natural language** via the Knowledge Graph Agent
- **Search by meaning** using vector similarity (not just keywords)
- **Traverse the graph** to discover connections between articles
- **Explore visually** through an interactive web interface with force-directed graph visualization

## When This Is Useful (and When It Isn't)

A knowledge graph adds value over just asking Claude or searching Wikipedia directly in specific cases:

**Where a KG helps:**
- **Structured relationship queries** — "What entities are connected to X within 3 hops?" is trivial for a graph database but hard for an LLM from training data
- **Constrained domains** — Answers come only from your curated article set, preventing hallucination about topics outside the graph
- **Offline/air-gapped** — The Kuzu database works locally with no internet
- **Aggregation** — "How many articles are about biology?" or "What's the most connected entity?" are database queries, not LLM queries
- **Provenance** — Every answer traces back to specific articles, sections, and extracted facts

**Where a KG doesn't help:**
- **General factual recall** — Claude already knows Wikipedia's content from training
- **Coverage** — Your graph has thousands of articles; Wikipedia has 6.8 million
- **Freshness** — The graph is a frozen snapshot
- **Simple questions** — "What is quantum entanglement?" gets a better answer from Claude directly than from synthesizing extracted fragments

## Architecture

- **Database**: Kuzu 0.11.3 (embedded graph database, zero external dependencies)
- **Embeddings**: paraphrase-MiniLM-L3-v2 (384 dimensions)
- **Vector Index**: HNSW with cosine similarity
- **Data Source**: Wikipedia Action API
- **LLM**: Claude (seed generation, entity extraction, query planning, answer synthesis)

## Quick Start

### 1. Install

```bash
uv pip install -e ".[dev]"
```

### 2. Build a Knowledge Graph

```bash
cat > topics.md << 'EOF'
- Quantum Computing
- Marine Biology
- Renaissance Art
EOF

export ANTHROPIC_API_KEY=your-key-here
wikigr create --topics topics.md --db data/ --target 500
```

This generates seed articles using Claude, validates them against Wikipedia, fetches and parses articles, generates embeddings, expands via link discovery, and extracts entities/relationships/facts via LLM.

### 3. Query with Natural Language

```bash
python examples/query_kg_agent.py "What is quantum entanglement?" data/quantum-computing.db
```

Or in Python:

```python
from wikigr.agent import KnowledgeGraphAgent

with KnowledgeGraphAgent(db_path="data/quantum-computing.db") as agent:
    # Natural language Q&A
    result = agent.query("What is quantum entanglement?")
    print(result["answer"])

    # Graph-aware multi-hop retrieval (follows LINKS_TO edges)
    result = agent.graph_query("How are qubits and error correction related?")
    print(result["answer"])

    # Direct entity/fact lookup
    entity = agent.find_entity("Qubit")
    facts = agent.get_entity_facts("Quantum Computing")
```

### 4. Programmatic Search

```python
import kuzu
from bootstrap.src.query.search import semantic_search, graph_traversal

db = kuzu.Database("data/quantum-computing.db", read_only=True)
conn = kuzu.Connection(db)

# Find articles by meaning
results = semantic_search(conn, query_title="Quantum Computing", top_k=10)

# Explore link neighborhood
neighbors = graph_traversal(conn, seed_title="Quantum Computing", max_hops=2)
```

### 5. Web Interface

```bash
# Install backend dependencies
uv pip install -e ".[backend]"

# Terminal 1: Start API server
WIKIGR_DATABASE_PATH=data/quantum-computing.db uvicorn backend.main:app --port 8000

# Terminal 2: Start frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

The web UI provides:
- Force-directed graph visualization (D3.js) with pan, zoom, and node selection
- Semantic search with autocomplete
- Hybrid search combining vector similarity and graph proximity
- Chat panel for natural language Q&A with streaming responses
- Category and depth filters

### 6. Kuzu Explorer (Optional)

Browse the raw graph with [Kuzu Explorer](https://github.com/kuzudb/explorer) (requires Docker):

```bash
wikigr-explore --db data/quantum-computing.db --port 8000
```

## REST API

Start the backend with `uvicorn backend.main:app` and open `http://localhost:8000/docs` for interactive documentation.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service status and database connectivity |
| `/api/v1/search` | GET | Semantic search by vector similarity |
| `/api/v1/autocomplete` | GET | Article title suggestions |
| `/api/v1/graph` | GET | Graph traversal around a seed article |
| `/api/v1/hybrid-search` | GET | Combined semantic + graph proximity search |
| `/api/v1/articles/{title}` | GET | Article details, sections, links, backlinks |
| `/api/v1/categories` | GET | All categories with article counts |
| `/api/v1/stats` | GET | Database statistics |
| `/api/v1/chat` | POST | Natural language Q&A (SSE streaming) |

All endpoints are rate-limited. See [backend/API.md](backend/API.md) for full parameter documentation.

## Project Structure

```
wikigr/
├── wikigr/                 # Python package (CLI + agents)
│   ├── cli.py             # wikigr create / update / status
│   └── agent/
│       ├── kg_agent.py    # Knowledge Graph query agent
│       └── seed_agent.py  # Seed generation agent
├── backend/                # FastAPI REST API
│   ├── api/v1/            # Endpoint routers
│   ├── services/          # Business logic
│   ├── models/            # Pydantic schemas
│   └── db/                # Connection management
├── frontend/               # React + TypeScript PWA
│   └── src/
│       ├── components/    # Graph, Search, Chat, Sidebar
│       ├── store/         # Zustand state management
│       └── services/      # API client
├── bootstrap/              # Data pipeline
│   ├── src/
│   │   ├── wikipedia/     # Wikipedia API client + parser
│   │   ├── embeddings/    # Sentence-transformers embeddings
│   │   ├── expansion/     # Orchestrator, work queue, link discovery
│   │   ├── extraction/    # LLM entity/relationship extraction
│   │   └── query/         # Search functions
│   ├── schema/            # Kuzu graph schema
│   └── tests/             # Integration tests
├── tests/agent/            # KG Agent tests + benchmarks
└── data/                   # Database storage
```

## Performance (30K articles)

| Metric | Value |
|--------|-------|
| Articles | 31,777 |
| Entities | 87,500 |
| Relationships | 54,393 |
| Article links | 6.2M |
| Database size | 3.0 GB |
| P95 query latency | 298ms |
| Semantic precision | 100% |
| Memory usage | ~350 MB |

## Development

```bash
# Run all tests
python3.10 -m pytest

# Lint + format
ruff check . && ruff format .

# Type checking
pyright
```

## Documentation

- [API Reference](backend/API.md)
- [Architecture](bootstrap/docs/architecture-specification.md)
- [Seed Agent & CLI](bootstrap/docs/seed-agent.md)
- [Embedding Model Choice](bootstrap/docs/embedding-model-choice.md)
- [Research Findings](bootstrap/docs/research-findings.md)

## License

MIT
