# Getting Started with Web Content Sources

Learn how to build knowledge graphs from web content with full feature parity to Wikipedia sources.

## What You'll Learn

- Creating a knowledge graph from web URLs
- Using LLM extraction for entities and relationships
- Expanding your graph with link crawling
- Keeping your graph up-to-date with incremental updates

## Prerequisites

- WikiGR installed (`pip install -e .`)
- OpenAI API key configured (`export OPENAI_API_KEY=your-key`)
- Basic familiarity with command-line tools

## Tutorial: Building a Knowledge Graph from Microsoft Azure Docs

### Step 1: Create Your First Web-Based Knowledge Graph

Start with a single URL to extract entities and relationships:

```bash
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks" \
  --db-path=azure_aks.db
```

**What happens:**
- Downloads and parses the web page
- Extracts entities (Azure Kubernetes Service, containers, orchestration)
- Identifies relationships between entities
- Creates nodes and edges in the knowledge graph

**Expected output:**
```
Processing 1 article from web...
Extracted 42 entities, 28 relationships
Knowledge graph created: azure_aks.db
```

### Step 2: Expand the Graph with Link Crawling

Add related pages using breadth-first search (BFS):

```bash
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks" \
  --max-depth=2 \
  --max-links=10 \
  --db-path=azure_aks_expanded.db
```

**What happens:**
- Starts from the root URL
- Follows links to depth 2 (root → linked pages → their linked pages)
- Processes up to 10 pages total
- Each page extracts entities and relationships

**Expected output:**
```
Processing 1 article from web...
Expanding links: depth 1, found 8 new URLs
Expanding links: depth 2, found 15 new URLs (limiting to 10 total)
Extracted 312 entities, 187 relationships across 10 pages
Knowledge graph created: azure_aks_expanded.db
```

### Step 3: Update Your Graph Incrementally

Add new content without rebuilding:

```bash
wikigr update \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/kubernetes-deployment" \
  --db-path=azure_aks_expanded.db
```

**What happens:**
- Checks if URL already exists in the database
- Skips if already processed, or updates if content changed
- Adds new entities and relationships
- Preserves existing graph structure

**Expected output:**
```
Checking existing content...
Processing 1 new article from web...
Extracted 18 new entities, 12 new relationships
Updated knowledge graph: azure_aks_expanded.db
```

### Step 4: Query Your Graph

Now explore the knowledge you've extracted:

```bash
# Start the backend server
python -m backend.main

# In another terminal, query the graph
curl -X POST http://localhost:8000/api/graph/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Azure Kubernetes Service?"}'
```

**Expected response:**
```json
{
  "answer": "Azure Kubernetes Service (AKS) is a managed container orchestration service...",
  "entities": ["Azure Kubernetes Service", "containers", "Kubernetes"],
  "relationships": [
    {"source": "AKS", "relation": "IS_A", "target": "managed service"},
    {"source": "AKS", "relation": "ORCHESTRATES", "target": "containers"}
  ]
}
```

## Key Concepts Learned

### LLM Extraction

Web sources use the same LLM extraction pipeline as Wikipedia:
- Identifies named entities (people, places, organizations, concepts)
- Extracts semantic relationships between entities
- Normalizes entity names for consistency

### Link Expansion

BFS crawling follows links intelligently:
- Respects `max-depth` (how many hops from root)
- Limits total pages with `max-links`
- Filters same-domain links by default

### Incremental Updates

The `update` command is efficient:
- Skips already-processed URLs
- Updates only changed content
- Merges new entities into existing graph

## Next Steps

- [How to configure LLM extraction parameters](../howto/configure-llm-extraction.md)
- [How to filter links during crawling](../howto/filter-link-crawling.md)
- [Web Content Source API Reference](../reference/web-content-source.md)
- [Understanding ArticleProcessor architecture](../concepts/article-processor.md)
