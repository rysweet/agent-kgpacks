# Query Module

Provides semantic search, graph traversal, and hybrid queries over the WikiGR knowledge graph.

## Public Interface

```python
from bootstrap.src.query import semantic_search, graph_traversal, hybrid_query

results = semantic_search(conn, "Machine Learning", top_k=10)
neighbors = graph_traversal(conn, "Machine Learning", max_hops=2)
combined = hybrid_query(conn, "Machine Learning", max_hops=2, top_k=10)
```

## Functions

- `semantic_search()` - Find articles by vector similarity (HNSW index)
- `graph_traversal()` - Explore link neighborhood (Cypher variable-length paths)
- `hybrid_query()` - Combine semantic similarity with graph proximity

## Dependencies

- `kuzu` (database queries)
- HNSW vector index on Section.embedding
