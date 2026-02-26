---
name: security-copilot
version: 1.0.0
description: Security Copilot knowledge from Microsoft Learn
triggers:
  - "security copilot"
---

# Security Copilot Skill

Knowledge graph: 6 articles, 48 entities, 45 relationships

## Overview

Security Copilot knowledge from Microsoft Learn

## Usage

This skill provides deep domain expertise through a knowledge graph.
Ask questions naturally and the skill will retrieve relevant information
from the graph database.

**Example queries:**
- "Explain security copilot concepts"
- "What is the relationship between X and Y in security copilot?"
- "Find articles about [topic] in security copilot"

## Knowledge Domains

This pack covers 6 articles across multiple domains within security copilot.

**Quality Metrics:**
- Accuracy: 50.0%
- Hallucination Rate: 0.0%
- Citation Quality: 20.0%

## Technical Details

- Database: Kuzu graph database (2.08 MB)
- Configuration: `data/packs/security-copilot/kg_config.json`
- License: CC-BY-SA-4.0

## Sources

This knowledge pack was created from:
- https://learn.microsoft.com/en-us/copilot/security/microsoft-security-copilot
- https://learn.microsoft.com/en-us/copilot/security/get-started-security-copilot
- https://learn.microsoft.com/en-us/copilot/security/security-copilot-inclusion
- https://learn.microsoft.com/en-us/copilot/security/get-started-security-copilot-api
- https://learn.microsoft.com/en-us/copilot/security/experiences-security-copilot

## Integration

This skill integrates with WikiGR's KG Agent for semantic retrieval.

**How to Use This Pack:**

When a user asks a question related to this domain, automatically:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent
from pathlib import Path

# Initialize KG Agent with pack database
pack_db = Path("data/packs/security-copilot/pack.db").resolve()
with KnowledgeGraphAgent(db_path=str(pack_db), read_only=True) as kg_agent:
    result = kg_agent.query(user_question, max_results=5)
    # Use result["answer"] and result["sources"] in your response
```

**Retrieval Strategy:**
1. **Vector Search**: Find semantically similar content
2. **Graph Traversal**: Navigate relationships between entities
3. **Hybrid Search**: Combine vector similarity with graph structure

Created: 2026-02-26T00:52:25.736334Z
