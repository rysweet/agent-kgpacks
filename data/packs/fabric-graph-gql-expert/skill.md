---
name: fabric-graph-gql-expert
version: 1.0.0
description: Fabric Graph Gql Expert knowledge from Microsoft Learn
triggers:
  - "fabric graph gql"
---

# Fabric Graph Gql Expert Skill

Knowledge graph: 21 articles, 152 entities, 153 relationships

## Overview

Fabric Graph Gql Expert knowledge from Microsoft Learn

## Usage

This skill provides deep domain expertise through a knowledge graph.
Ask questions naturally and the skill will retrieve relevant information
from the graph database.

**Example queries:**
- "Explain fabric graph gql concepts"
- "What is the relationship between X and Y in fabric graph gql?"
- "Find articles about [topic] in fabric graph gql"

## Knowledge Domains

This pack covers 21 articles across multiple domains within fabric graph gql.

**Quality Metrics:**
- Accuracy: 50.0%
- Hallucination Rate: 0.0%
- Citation Quality: 20.0%

## Technical Details

- Database: Kuzu graph database (2.08 MB)
- Configuration: `data/packs/fabric-graph-gql-expert/kg_config.json`
- License: CC-BY-SA-4.0

## Sources

This knowledge pack was created from:
- https://learn.microsoft.com/en-us/fabric/data-engineering/api-graphql-overview
- https://learn.microsoft.com/en-us/fabric/data-engineering/get-started-api-graphql
- https://learn.microsoft.com/en-us/fabric/data-engineering/api-graphql-editor
- https://learn.microsoft.com/en-us/fabric/data-engineering/connect-apps-api-graphql
- https://learn.microsoft.com/en-us/fabric/data-engineering/api-graphql-introspection-schema-export

## Integration

This skill integrates with WikiGR's KG Agent for semantic retrieval.

**How to Use This Pack:**

When a user asks a question related to this domain, automatically:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
from pathlib import Path

# Initialize KG Agent with pack database
pack_db = Path("data/packs/fabric-graph-gql-expert/pack.db").resolve()
with KnowledgeGraphAgent(db_path=str(pack_db), read_only=True) as kg_agent:
    result = kg_agent.query(user_question, max_results=5)
    # Use result["answer"] and result["sources"] in your response
```

**Retrieval Strategy:**
1. **Vector Search**: Find semantically similar content
2. **Graph Traversal**: Navigate relationships between entities
3. **Hybrid Search**: Combine vector similarity with graph structure

Created: 2026-02-26T00:49:15.608177Z
