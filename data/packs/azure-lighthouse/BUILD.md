# Azure Lighthouse Knowledge Pack — Build Guide

This document describes how to build the Azure Lighthouse Knowledge Pack from source.

## Prerequisites

### System Requirements
- Python 3.10 or higher
- 2 GB RAM minimum
- 2 GB disk space (build artifacts and database)
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

The build script is `scripts/build_azure_lighthouse_pack.py`.

### Pack Constants

| Constant | Value |
|----------|-------|
| `PACK_DIR` | `data/packs/azure-lighthouse` |
| `URLS_FILE` | `data/packs/azure-lighthouse/urls.txt` |
| `DB_PATH` | `data/packs/azure-lighthouse/pack.db` |
| `MANIFEST_PATH` | `data/packs/azure-lighthouse/manifest.json` |
| `domain` | `azure_lighthouse` |
| `category` | `Azure Lighthouse` |

## Running the Build

### Test Build (Recommended First Step)

Processes only the first 5 URLs. Completes in 5-10 minutes.

```bash
uv run python scripts/build_azure_lighthouse_pack.py --test-mode
```

Test mode auto-deletes any existing database and rebuilds without prompting.

### Full Build

Processes all 57 URLs. Completes in approximately 3-5 hours.

```bash
uv run python scripts/build_azure_lighthouse_pack.py
```

If `pack.db` already exists, the script prompts before deleting it:

```
Database already exists: data/packs/azure-lighthouse/pack.db
Delete and rebuild? (y/N):
```

To script non-interactively:

```bash
echo "y" | uv run python scripts/build_azure_lighthouse_pack.py
```

## Build Pipeline

Each URL goes through six stages:

### Stage 1: URL Loading (`load_urls`)
- Reads `data/packs/azure-lighthouse/urls.txt`
- Skips blank lines and `#` comments
- Accepts lines starting with `http` (HTTPS URLs from the file)
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
- Extracts: named entities (concepts, services, features), relationships between entities, key facts
- Domain hint: `azure_lighthouse` (improves entity relevance)

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
data/packs/azure-lighthouse/
├── pack.db/            # KuzuDB graph database (directory)
├── manifest.json       # Pack metadata and graph stats
├── urls.txt            # Source URLs (57 entries)
├── BUILD.md            # This file
├── README.md           # Pack documentation
└── skill.md            # Claude Code skill description
```

### Sample `manifest.json`

```json
{
  "name": "azure-lighthouse",
  "version": "1.0.0",
  "description": "Expert knowledge of Azure Lighthouse covering delegated resource management, cross-tenant management, managed services offers, Azure Marketplace publishing, policy at scale, monitoring, security best practices, and MSSP scenarios.",
  "graph_stats": {
    "articles": 48,
    "entities": 620,
    "relationships": 1240,
    "size_mb": 42.5
  },
  "eval_scores": {
    "accuracy": 0.0,
    "hallucination_rate": 0.0,
    "citation_quality": 0.0
  },
  "source_urls": [
    "https://learn.microsoft.com/en-us/azure/lighthouse/overview",
    "https://learn.microsoft.com/en-us/azure/lighthouse/concepts/azure-delegated-resource-management"
  ],
  "created": "2026-03-03T12:00:00Z",
  "license": "MIT"
}
```

## Logs

Build logs are written to `logs/build_azure_lighthouse_pack.log` and also streamed to stdout.

```bash
tail -f logs/build_azure_lighthouse_pack.log
```

## Verifying the Build

### Check Manifest

```bash
python -m json.tool data/packs/azure-lighthouse/manifest.json
```

Expected values:
- `graph_stats.articles` ≥ 40
- `graph_stats.entities` ≥ 400
- `graph_stats.size_mb` between 20 and 150

### Query the Database

```python
import kuzu

db = kuzu.Database("data/packs/azure-lighthouse/pack.db")
conn = kuzu.Connection(db)

# Article count
r = conn.execute("MATCH (a:Article) RETURN count(a) AS n")
print("Articles:", r.get_as_df().iloc[0]["n"])

# Top entities
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
    db_path="data/packs/azure-lighthouse/pack.db",
    use_enhancements=True,
)
result = agent.query("What is Azure delegated resource management?")
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
uv run python scripts/build_azure_lighthouse_pack.py --test-mode
```

### HTTP errors fetching `learn.microsoft.com`

Pages that return a non-200 status or empty body are logged as warnings and counted as `failed`. The build continues. A handful of failed URLs is expected; check the log for patterns.

### Duplicate URL warnings

`urls.txt` contains some intentional duplicates (e.g., the partner-earned-credit page appears multiple times under different sections). The graph deduplication check (`MATCH (a:Article {title: $title})`) ensures each page is only stored once.

### Out of disk space

The KuzuDB directory can grow to 100+ MB for this pack. Ensure at least 2 GB free before building.

### Partial build recovery

If a build is interrupted, re-running without `--test-mode` will prompt to delete and rebuild. The script does not support resuming a partial build; it rebuilds from scratch.

## Updating the Pack

### Adding URLs

1. Add HTTPS URLs to `data/packs/azure-lighthouse/urls.txt` under an appropriate section comment
2. Verify the URL returns a 200 response:
   ```bash
   curl -I "https://learn.microsoft.com/en-us/azure/lighthouse/..."
   ```
3. Rebuild the pack

### Refreshing Stale Content

Microsoft Learn pages are updated regularly. To refresh:

```bash
echo "y" | uv run python scripts/build_azure_lighthouse_pack.py
```

The full rebuild fetches all URLs fresh from the web.

## Distribution

### Create Archive

```bash
cd data/packs
tar -czf azure-lighthouse-1.0.0.tar.gz azure-lighthouse/
```

### Upload to GitHub Releases

```bash
gh release create azure-lighthouse-v1.0.0 \
  data/packs/azure-lighthouse-1.0.0.tar.gz \
  --title "Azure Lighthouse Knowledge Pack v1.0.0"
```

---

**Script**: `scripts/build_azure_lighthouse_pack.py`
**Domain**: `azure_lighthouse`
**Last Updated**: 2026-03-03
