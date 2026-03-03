# Microsoft Fabric GraphQL Expert Knowledge Pack — Build Guide

This document describes how to build the Microsoft Fabric GraphQL Expert Knowledge Pack from source.

## Prerequisites

### System Requirements
- Python 3.10 or higher
- 1 GB RAM minimum
- 1 GB disk space (build artifacts and database)
- Internet connection for web scraping

### Python Dependencies

Install with `uv` (recommended):

```bash
uv sync
```

Or with pip:

```bash
pip install kuzu anthropic beautifulsoup4 requests lxml sentence-transformers
```

### Environment Variables

```bash
# Required: Anthropic API key for LLM entity extraction
export ANTHROPIC_API_KEY="your-key-here"
```

The extractor defaults to `claude-haiku-4-5-20251001` (~$0.25/1M input tokens).

## Build Script

The build script is `scripts/build_fabric_graphql_expert_pack.py`.

### Pack Constants

| Constant | Value |
|----------|-------|
| `PACK_DIR` | `data/packs/fabric-graphql-expert` |
| `URLS_FILE` | `data/packs/fabric-graphql-expert/urls.txt` |
| `DB_PATH` | `data/packs/fabric-graphql-expert/pack.db` |
| `MANIFEST_PATH` | `data/packs/fabric-graphql-expert/manifest.json` |
| `domain` | `fabric_graphql` |
| `category` | `Microsoft Fabric GraphQL` |

## Running the Build

### Test Build (Recommended First Step)

Processes only the first 5 URLs. Completes in 5-10 minutes.

```bash
uv run python scripts/build_fabric_graphql_expert_pack.py --test-mode
```

Test mode auto-deletes any existing database and rebuilds without prompting.

### Full Build

Processes all 28 URLs. Completes in approximately 2-4 hours (faster than other packs due to fewer URLs).

```bash
uv run python scripts/build_fabric_graphql_expert_pack.py
```

If `pack.db` already exists, the script prompts before deleting it:

```
Database already exists: data/packs/fabric-graphql-expert/pack.db
Delete and rebuild? (y/N):
```

To script non-interactively:

```bash
echo "y" | uv run python scripts/build_fabric_graphql_expert_pack.py
```

## Build Pipeline

Each URL goes through six stages:

### Stage 1: URL Loading (`load_urls`)
- Reads `data/packs/fabric-graphql-expert/urls.txt`
- Skips blank lines and `#` comments
- Accepts lines starting with `http`
- Logs the count loaded

### Stage 2: Fetch & Parse (`process_url` → `WebContentSource`)
- Downloads HTML from `learn.microsoft.com`
- Extracts title and body text
- Splits content into sections by heading level
- Falls back to a single "Overview" section if no headings found

### Stage 3: Deduplication
- Checks `MATCH (a:Article {title: $title})` before inserting
- Skips pages already in the graph (idempotent re-runs)

### Stage 4: LLM Extraction (`get_extractor`)
- Sends up to 5 sections per article to Claude Haiku
- Extracts: named entities (GraphQL types, operations, Fabric items), relationships, key facts
- Domain hint: `fabric_graphql` (improves entity relevance for GraphQL API concepts)

### Stage 5: Embedding & Graph Write
- Generates 768-dim embeddings with `BAAI/bge-base-en-v1.5` for the first 3 sections
- Writes `Article`, `Entity`, `Fact`, `Section` nodes to KuzuDB
- Creates `HAS_ENTITY`, `ENTITY_RELATION`, `HAS_FACT`, `HAS_SECTION` edges

### Stage 6: Manifest (`create_manifest`)
- Queries final counts: articles, entities, relationships
- Calculates `pack.db` size on disk
- Writes `manifest.json`

## Build Output

```
data/packs/fabric-graphql-expert/
├── pack.db/            # KuzuDB graph database (directory)
├── manifest.json       # Pack metadata and graph stats
├── urls.txt            # Source URLs (28 entries)
├── BUILD.md            # This file
├── README.md           # Pack documentation
├── skill.md            # Claude Code skill description
└── eval/
    ├── questions.json
    └── questions.jsonl
```

### Sample `manifest.json`

```json
{
  "name": "fabric-graphql-expert",
  "version": "1.0.0",
  "description": "Expert knowledge of Microsoft Fabric GraphQL API covering schema design, authentication, pagination, filtering, mutations, security, and integration with Fabric data sources.",
  "graph_stats": {
    "articles": 24,
    "entities": 310,
    "relationships": 620,
    "size_mb": 18.4
  },
  "eval_scores": {
    "accuracy": 0.0,
    "hallucination_rate": 0.0,
    "citation_quality": 0.0
  },
  "source_urls": [
    "https://learn.microsoft.com/en-us/fabric/data-engineering/api-graphql-overview",
    "https://learn.microsoft.com/en-us/fabric/data-engineering/get-started-api-graphql"
  ],
  "created": "2026-03-03T12:00:00Z",
  "license": "MIT"
}
```

## Logs

Build logs are written to `logs/build_fabric_graphql_expert_pack.log` and also streamed to stdout.

```bash
tail -f logs/build_fabric_graphql_expert_pack.log
```

## Verifying the Build

### Check Manifest

```bash
python -m json.tool data/packs/fabric-graphql-expert/manifest.json
```

Expected values:
- `graph_stats.articles` ≥ 20
- `graph_stats.entities` ≥ 200
- `graph_stats.size_mb` between 10 and 80

### Query the Database

```python
import kuzu

db = kuzu.Database("data/packs/fabric-graphql-expert/pack.db")
conn = kuzu.Connection(db)

# Article count
r = conn.execute("MATCH (a:Article) RETURN count(a) AS n")
print("Articles:", r.get_as_df().iloc[0]["n"])

# Top entities by mention count
r = conn.execute(
    "MATCH (e:Entity)<-[:HAS_ENTITY]-(a:Article) "
    "RETURN e.name AS entity, count(a) AS mentions "
    "ORDER BY mentions DESC LIMIT 10"
)
print(r.get_as_df())
```

### End-to-End Query Test

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/fabric-graphql-expert/pack.db",
    use_enhancements=True,
)
result = agent.query("How do I create a GraphQL API item in Microsoft Fabric?")
print(result["answer"])
```

## Troubleshooting

### `ANTHROPIC_API_KEY` not set

```
ValueError: ANTHROPIC_API_KEY environment variable not set
```

Set the environment variable before running:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
uv run python scripts/build_fabric_graphql_expert_pack.py --test-mode
```

### 404 errors for Fabric GraphQL pages

The Fabric GraphQL API is a newer feature. Some documentation URLs in `urls.txt` (e.g., performance, monitoring, troubleshooting sub-pages) may not yet exist or may have different paths. Failed URLs are logged and counted but do not abort the build.

### Small article count

This pack intentionally targets only 28 URLs. If the resulting article count is below 20, some pages may have failed to load. Check `logs/build_fabric_graphql_expert_pack.log` for HTTP errors.

### Partial build recovery

If a build is interrupted, re-run the full build. The script rebuilds from scratch.

## Updating the Pack

### Adding URLs

The Fabric GraphQL documentation is growing rapidly as the feature matures. To add new pages:

1. Add HTTPS URLs to `data/packs/fabric-graphql-expert/urls.txt`
2. Verify accessibility:
   ```bash
   curl -I "https://learn.microsoft.com/en-us/fabric/data-engineering/..."
   ```
3. Rebuild

### Refreshing Stale Content

```bash
echo "y" | uv run python scripts/build_fabric_graphql_expert_pack.py
```

## Distribution

### Create Archive

```bash
cd data/packs
tar -czf fabric-graphql-expert-1.0.0.tar.gz fabric-graphql-expert/
```

### Upload to GitHub Releases

```bash
gh release create fabric-graphql-expert-v1.0.0 \
  data/packs/fabric-graphql-expert-1.0.0.tar.gz \
  --title "Microsoft Fabric GraphQL Expert Knowledge Pack v1.0.0"
```

---

**Script**: `scripts/build_fabric_graphql_expert_pack.py`
**Domain**: `fabric_graphql`
**Last Updated**: 2026-03-03
