---
name: ladybugdb-expert
version: 1.0.0
description: Comprehensive knowledge of LadybugDB, the active community fork of the archived Kuzu graph database. Covers the Python SDK (real_ladybug package), Cypher query language, vector search extensions, full-text search, graph algorithms, import/export, and migration from Kuzu.
triggers:
  - "ladybugdb"
---

# Ladybugdb Expert Skill

Knowledge graph: 43 articles, 207 entities, 178 relationships

## Overview

Comprehensive knowledge of LadybugDB, the active community fork of the archived Kuzu graph database. Covers the Python SDK (real_ladybug package), Cypher query language, vector search extensions, full-text search, graph algorithms, import/export, and migration from Kuzu.

## Usage

This skill provides deep domain expertise through a knowledge graph.
Ask questions naturally and the skill will retrieve relevant information
from the graph database.

**Example queries:**
- "Explain ladybugdb concepts"
- "What is the relationship between X and Y in ladybugdb?"
- "Find articles about [topic] in ladybugdb"

## Knowledge Domains

This pack covers 43 articles across multiple domains within ladybugdb.

**Quality Metrics:**
- Accuracy: 0.0%
- Hallucination Rate: 0.0%
- Citation Quality: 0.0%

## Technical Details

- Database: Kuzu graph database (2.08 MB)
- Configuration: `data/packs/ladybugdb-expert/kg_config.json`
- License: MIT

## Sources

This knowledge pack was created from:
- https://docs.ladybugdb.com/
- https://docs.ladybugdb.com/client-apis/python/
- https://docs.ladybugdb.com/extensions/vector/
- https://github.com/LadybugDB/ladybug

## Integration

This skill integrates with WikiGR's KG Agent for semantic retrieval.

**How to Use This Pack:**

When a user asks a question related to this domain, automatically:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
from pathlib import Path

# Initialize KG Agent with pack database
pack_db = Path("data/packs/ladybugdb-expert/pack.db").resolve()
with KnowledgeGraphAgent(db_path=str(pack_db), read_only=True) as kg_agent:
    result = kg_agent.query(user_question, max_results=5)
    # Use result["answer"] and result["sources"] in your response
```

**Retrieval Strategy:**
1. **Vector Search**: Find semantically similar content
2. **Graph Traversal**: Navigate relationships between entities
3. **Hybrid Search**: Combine vector similarity with graph structure

Created: 2026-03-03T18:44:21.748608Z