# WikiGR - Wikipedia Knowledge Graph

A semantic search and graph traversal system for Wikipedia articles using embedded graph database (Kuzu) and vector search (HNSW).

## Features

- **Semantic Search**: Find articles by meaning using vector embeddings
- **Graph Traversal**: Explore link relationships between articles
- **Hybrid Queries**: Combine semantic similarity and graph proximity
- **Incremental Expansion**: Start with 3K seeds, expand to 30K articles
- **Zero Cost**: Embedded database with no external dependencies

## Architecture

- **Database**: Kuzu 0.11.3 (embedded graph database)
- **Embeddings**: paraphrase-MiniLM-L3-v2 (384 dimensions)
- **Vector Index**: HNSW with cosine similarity
- **Data Source**: Wikipedia Action API

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Validate Setup

```bash
# Run quickstart validation (3 sample articles)
python bootstrap/quickstart.py
```

Expected output: All systems validated ✅

### 3. Run with 10 Articles

```bash
# Load 10 articles and test semantic search
python bootstrap/scripts/load_articles.py --count 10
```

## Project Structure

```
wikigr/
├── bootstrap/              # Bootstrap implementation
│   ├── docs/              # Documentation
│   ├── schema/            # Database schema
│   ├── src/               # Source code
│   │   ├── wikipedia/     # Wikipedia API client
│   │   ├── embeddings/    # Embedding generation
│   │   ├── database/      # Database operations
│   │   ├── query/         # Query functions
│   │   └── expansion/     # Expansion orchestrator
│   ├── tests/             # Test queries and scripts
│   ├── scripts/           # Utility scripts
│   ├── data/              # Seed data
│   └── quickstart.py      # Validation script
├── data/                  # Database storage
├── logs/                  # Log files
├── requirements.txt       # Dependencies
└── README.md             # This file
```

## Usage

### Load Articles

```python
from bootstrap.src.expansion.orchestrator import RyuGraphOrchestrator

# Initialize
orch = RyuGraphOrchestrator("data/wikigr.db")

# Initialize with seeds
seeds = ["Machine Learning", "Quantum Computing", "Deep Learning"]
orch.initialize_seeds(seeds)

# Expand to target count
orch.expand_to_target(target_count=100)
```

### Semantic Search

```python
from bootstrap.src.query.search import semantic_search
import kuzu

# Connect to database
db = kuzu.Database("data/wikigr.db")
conn = kuzu.Connection(db)

# Search for similar articles
results = semantic_search(
    conn,
    query_title="Machine Learning",
    category="Computer Science",
    top_k=10
)

for article, similarity in results:
    print(f"{article}: {similarity:.4f}")
```

### Graph Traversal

```python
from bootstrap.src.query.search import graph_traversal

# Explore neighborhood
neighbors = graph_traversal(
    conn,
    seed_title="Machine Learning",
    max_hops=2,
    max_results=50
)

for neighbor, hops in neighbors:
    print(f"{neighbor} ({hops} hops)")
```

## Development

### Run Tests

```bash
# Run all tests
pytest bootstrap/tests/

# With coverage
pytest --cov=bootstrap bootstrap/tests/
```

### Code Formatting

```bash
# Format code
ruff format bootstrap/

# Check style
ruff check bootstrap/

# Type checking
pyright bootstrap/
```

## Performance

| Metric | Target | Actual |
|--------|--------|--------|
| P95 query latency | <500ms | 298ms |
| Semantic precision | >70% | 100% |
| Database size (30K) | <10 GB | ~3 GB |
| Memory usage | <500 MB | ~350 MB |
| Expansion time (30K) | <2 hours | ~14 min (CPU) |

## Documentation

- **Research Findings**: `bootstrap/docs/research-findings.md`
- **Architecture**: `bootstrap/docs/architecture-specification.md`
- **Implementation Roadmap**: `bootstrap/docs/implementation-roadmap.md`
- **API Documentation**: `bootstrap/docs/wikipedia-api-validation.md`
- **Embedding Models**: `bootstrap/docs/embedding-model-choice.md`

## Roadmap

- [x] Phase 1: Research & Assessment (Complete)
- [x] Phase 2: Implementation Planning (Complete)
- [x] Phase 3: Foundation - 10 articles validated
- [x] Phase 3: Orchestrator - Automatic graph expansion working
- [ ] Phase 4: Scale to 30K articles

## License

MIT License - See LICENSE file for details

## Contributing

This is an educational project. Contributions welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and formatting
5. Submit a pull request

## Support

For issues, questions, or suggestions:
- Open a GitHub issue
- Check existing documentation in `bootstrap/docs/`

## Acknowledgments

- **Kuzu**: Embedded graph database
- **sentence-transformers**: Pre-trained embedding models
- **Wikipedia**: Data source via Action API
- **Claude Code**: Development assistance

---

**Status**: Phase 3 complete - Orchestrator working, scaling to 30K
**Version**: 0.1.0-dev
**Updated**: February 2026
