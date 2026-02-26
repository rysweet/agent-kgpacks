---
name: azure-lighthouse
version: 1.0.0
description: Azure Lighthouse knowledge from Microsoft Learn
triggers:
  - "azure lighthouse"
---

# Azure Lighthouse Skill

Knowledge graph: 13 articles, 102 entities, 94 relationships

## Overview

Azure Lighthouse knowledge from Microsoft Learn

## Usage

This skill provides deep domain expertise through a knowledge graph.
Ask questions naturally and the skill will retrieve relevant information
from the graph database.

**Example queries:**
- "Explain azure lighthouse concepts"
- "What is the relationship between X and Y in azure lighthouse?"
- "Find articles about [topic] in azure lighthouse"

## Knowledge Domains

This pack covers 13 articles across multiple domains within azure lighthouse.

**Quality Metrics:**
- Accuracy: 50.0%
- Hallucination Rate: 0.0%
- Citation Quality: 20.0%

## Technical Details

- Database: Kuzu graph database (2.08 MB)
- Configuration: `data/packs/azure-lighthouse/kg_config.json`
- License: CC-BY-SA-4.0

## Sources

This knowledge pack was created from:
- https://learn.microsoft.com/en-us/azure/lighthouse/overview
- https://learn.microsoft.com/en-us/azure/lighthouse/concepts/architecture
- https://learn.microsoft.com/en-us/azure/lighthouse/concepts/enterprise
- https://learn.microsoft.com/en-us/azure/lighthouse/concepts/managed-applications
- https://learn.microsoft.com/en-us/azure/lighthouse/how-to/onboard-customer

## Integration

This skill integrates with WikiGR's KG Agent for semantic retrieval.

**How to Use This Pack:**

When a user asks a question related to this domain, automatically:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
from pathlib import Path

# Initialize KG Agent with pack database
pack_db = Path("data/packs/azure-lighthouse/pack.db").resolve()
with KnowledgeGraphAgent(db_path=str(pack_db), read_only=True) as kg_agent:
    result = kg_agent.query(user_question, max_results=5)
    # Use result["answer"] and result["sources"] in your response
```

**Retrieval Strategy:**
1. **Vector Search**: Find semantically similar content
2. **Graph Traversal**: Navigate relationships between entities
3. **Hybrid Search**: Combine vector similarity with graph structure

Created: 2026-02-26T00:45:57.846209Z
