---
name: sentinel-graph
version: 1.0.0
description: Sentinel Graph knowledge from Microsoft Learn
triggers:
  - "sentinel graph"
---

# Sentinel Graph Skill

Knowledge graph: 14 articles, 117 entities, 97 relationships

## Overview

Sentinel Graph knowledge from Microsoft Learn

## Usage

This skill provides deep domain expertise through a knowledge graph.
Ask questions naturally and the skill will retrieve relevant information
from the graph database.

**Example queries:**
- "Explain sentinel graph concepts"
- "What is the relationship between X and Y in sentinel graph?"
- "Find articles about [topic] in sentinel graph"

## Knowledge Domains

This pack covers 14 articles across multiple domains within sentinel graph.

**Quality Metrics:**
- Accuracy: 50.0%
- Hallucination Rate: 0.0%
- Citation Quality: 20.0%

## Technical Details

- Database: Kuzu graph database (2.08 MB)
- Configuration: `data/packs/sentinel-graph/kg_config.json`
- License: CC-BY-SA-4.0

## Sources

This knowledge pack was created from:
- https://learn.microsoft.com/en-us/azure/sentinel/datalake/sentinel-graph-overview
- https://learn.microsoft.com/en-us/azure/sentinel/whats-new
- https://learn.microsoft.com/en-us/rest/api/securityinsights/
- https://learn.microsoft.com/en-us/azure/sentinel/overview
- https://learn.microsoft.com/en-us/azure/sentinel/quickstart-onboard

## Integration

This skill integrates with WikiGR's KG Agent for semantic retrieval.

**How to Use This Pack:**

When a user asks a question related to this domain, automatically:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
from pathlib import Path

# Initialize KG Agent with pack database
pack_db = Path("data/packs/sentinel-graph/pack.db").resolve()
with KnowledgeGraphAgent(db_path=str(pack_db), read_only=True) as kg_agent:
    result = kg_agent.query(user_question, max_results=5)
    # Use result["answer"] and result["sources"] in your response
```

**Retrieval Strategy:**
1. **Vector Search**: Find semantically similar content
2. **Graph Traversal**: Navigate relationships between entities
3. **Hybrid Search**: Combine vector similarity with graph structure

Created: 2026-02-26T00:51:21.968169Z
