# WikiGR - Knowledge Pack Platform

**Build reusable, graph-enhanced Claude Code skills that provably surpass baseline performance on specialized domains.**

## What It Does

WikiGR creates **Knowledge Packs** - distributable domain-specific skills that package expertise into self-contained archives:

- **Build packs** from Wikipedia or web documentation (Microsoft Learn, MDN, etc.)
- **Proven cost savings**: 70% cheaper than Claude + web search with comparable accuracy
- **Better attribution**: 20% citation quality vs 0% for web search
- **Auto-discovery**: Packs load as Claude Code skills with trigger keywords
- **Distribute**: Package as tarballs, share with others, install anywhere

**Example**: The `physics-expert` pack (451 articles, 4,607 entities) costs **$0.63** per 75 questions vs **$2.13** for Claude Opus 4.6 + web search, while providing better source citations.

## Why Knowledge Packs Win

**Proven advantages over Claude + web search:**

✅ **70% cost savings** - Graph retrieval is much cheaper than web search + LLM processing
✅ **Better citations** - 20% citation quality vs 0% for web search baseline
✅ **Offline capable** - Works without internet once installed
✅ **No hallucination** - Answers constrained to curated knowledge
✅ **Distributable** - Share expertise as packaged skills

**Evaluation Results** (Claude Opus 4.6):
- **Baseline**: Training + WebFetch = $2.13 per 75 questions
- **Knowledge Pack**: Graph retrieval = **$0.63 per 75 questions**
- **Savings**: 70% while maintaining 50% accuracy and adding citations

**When to build a pack:**
- Specialized domain with 100-500 key articles
- Need cost-effective expert responses at scale
- Want to share domain expertise with others
- Require source attribution for answers
- Working offline or in air-gapped environments

## Quick Start - Build Your First Pack

### 1. Create a Knowledge Pack

```bash
# From Wikipedia topics
cat > topics.txt << 'EOF'
Machine Learning
Neural Networks
Deep Learning
EOF

export ANTHROPIC_API_KEY=your-key-here
wikigr pack create --name ml-expert --topics topics.txt --target 100
```

**Output**: Complete pack in `~/.wikigr/packs/ml-expert/` with graph database, skill file, and evaluation questions.

### 2. Or Build from Web Sources

```bash
# From Microsoft Learn or any documentation
cat > urls.txt << 'EOF'
https://learn.microsoft.com/en-us/azure/lighthouse/overview
https://learn.microsoft.com/en-us/azure/lighthouse/concepts/architecture
EOF

python3.10 scripts/build_pack_generic.py data/packs/azure-lighthouse
```

**Output**: Web-sourced pack with extracted knowledge from documentation.

### 3. Install and Use

```bash
# Package for distribution
python3.10 scripts/package_physics_pack.py

# Install
wikigr pack install physics-expert-1.0.0.tar.gz

# Use automatically in Claude Code
# Just ask physics questions - the skill auto-loads!
```

---

## Available Knowledge Packs

**Pre-built packs ready to install:**

1. **physics-expert** (451 articles) - Classical mechanics, quantum physics, relativity, thermodynamics
2. **fabric-graph-gql-expert** (21 articles) - Microsoft Fabric Graph GQL API
3. **azure-lighthouse** (13 articles) - Azure multi-tenant management
4. **sentinel-graph** (14 articles) - Microsoft Sentinel security analytics
5. **security-copilot** (6 articles) - Microsoft Security Copilot AI

**Total**: 505 articles, 5,026 entities, 3,103 relationships across all packs.

---

## Architecture

- **Database**: Kuzu 0.11.3 (embedded graph database, zero external dependencies)
- **Embeddings**: paraphrase-MiniLM-L3-v2 (384 dimensions)
- **Vector Index**: HNSW with cosine similarity
- **Data Source**: Wikipedia Action API or web content
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
