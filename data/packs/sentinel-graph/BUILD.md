# Microsoft Sentinel Knowledge Pack — Build Guide

This document describes how to build the Microsoft Sentinel Knowledge Pack from source.

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

The build script is `scripts/build_sentinel_graph_pack.py`.

### Pack Constants

| Constant | Value |
|----------|-------|
| `PACK_DIR` | `data/packs/sentinel-graph` |
| `URLS_FILE` | `data/packs/sentinel-graph/urls.txt` |
| `DB_PATH` | `data/packs/sentinel-graph/pack.db` |
| `MANIFEST_PATH` | `data/packs/sentinel-graph/manifest.json` |
| `domain` | `microsoft_sentinel` |
| `category` | `Microsoft Sentinel` |

## Running the Build

### Test Build (Recommended First Step)

Processes only the first 5 URLs. Completes in 5-10 minutes.

```bash
uv run python scripts/build_sentinel_graph_pack.py --test-mode
```

Test mode auto-deletes any existing database and rebuilds without prompting.

### Full Build

Processes all 57 URLs. Completes in approximately 3-5 hours.

```bash
uv run python scripts/build_sentinel_graph_pack.py
```

If `pack.db` already exists, the script prompts before deleting it:

```
Database already exists: data/packs/sentinel-graph/pack.db
Delete and rebuild? (y/N):
```

To script non-interactively:

```bash
echo "y" | uv run python scripts/build_sentinel_graph_pack.py
```

## Build Pipeline

Each URL goes through six stages:

### Stage 1: URL Loading (`load_urls`)
- Reads `data/packs/sentinel-graph/urls.txt`
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
- Extracts: named entities (features, connectors, rule types), relationships, key facts
- Domain hint: `microsoft_sentinel` (improves entity relevance for SIEM concepts)

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
data/packs/sentinel-graph/
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
  "name": "sentinel-graph",
  "version": "1.0.0",
  "description": "Expert knowledge of Microsoft Sentinel covering SIEM architecture, data connectors, analytics rules, incident management, threat hunting, SOAR automation, threat intelligence, UEBA, KQL queries, and multi-tenant MSSP operations.",
  "graph_stats": {
    "articles": 50,
    "entities": 710,
    "relationships": 1480,
    "size_mb": 55.1
  },
  "eval_scores": {
    "accuracy": 0.0,
    "hallucination_rate": 0.0,
    "citation_quality": 0.0
  },
  "source_urls": [
    "https://learn.microsoft.com/en-us/azure/sentinel/overview",
    "https://learn.microsoft.com/en-us/azure/sentinel/best-practices"
  ],
  "created": "2026-03-03T12:00:00Z",
  "license": "MIT"
}
```

## Logs

Build logs are written to `logs/build_sentinel_graph_pack.log` and also streamed to stdout.

```bash
tail -f logs/build_sentinel_graph_pack.log
```

## Verifying the Build

### Check Manifest

```bash
python -m json.tool data/packs/sentinel-graph/manifest.json
```

Expected values:
- `graph_stats.articles` ≥ 40
- `graph_stats.entities` ≥ 450
- `graph_stats.size_mb` between 25 and 160

### Query the Database

```python
import kuzu

db = kuzu.Database("data/packs/sentinel-graph/pack.db")
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
    db_path="data/packs/sentinel-graph/pack.db",
    use_enhancements=True,
)
result = agent.query("How do I create an analytics rule in Microsoft Sentinel?")
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
uv run python scripts/build_sentinel_graph_pack.py --test-mode
```

### HTTP errors fetching `learn.microsoft.com`

Pages that return a non-200 status or empty body are logged as warnings and counted as `failed`. The build continues. The Microsoft Sentinel documentation is extensive and well-maintained; failures here typically mean the URL has been reorganized.

### Duplicate URL warnings

`urls.txt` contains some intentional duplicates (e.g., `detect-threats-built-in` and `investigate-cases` appear under multiple sections). The graph deduplication check at write time handles this correctly.

### KQL-heavy pages

Some Sentinel pages contain large amounts of KQL query code. The LLM extractor handles these well, extracting KQL concepts and query patterns as entities and facts.

### Out of disk space

Ensure at least 2 GB free before building. Sentinel has a large number of substantial documentation pages.

### Partial build recovery

If a build is interrupted, re-run the full build. The script rebuilds from scratch and does not support resuming partial builds.

## Updating the Pack

### Adding URLs

1. Add HTTPS URLs to `data/packs/sentinel-graph/urls.txt`
2. Verify accessibility:
   ```bash
   curl -I "https://learn.microsoft.com/en-us/azure/sentinel/..."
   ```
3. Rebuild

### Refreshing Stale Content

```bash
echo "y" | uv run python scripts/build_sentinel_graph_pack.py
```

## Distribution

### Create Archive

```bash
cd data/packs
tar -czf sentinel-graph-1.0.0.tar.gz sentinel-graph/
```

### Upload to GitHub Releases

```bash
gh release create sentinel-graph-v1.0.0 \
  data/packs/sentinel-graph-1.0.0.tar.gz \
  --title "Microsoft Sentinel Knowledge Pack v1.0.0"
```

---

**Script**: `scripts/build_sentinel_graph_pack.py`
**Domain**: `microsoft_sentinel`
**Last Updated**: 2026-03-03
