# Microsoft Security Copilot Knowledge Pack — Build Guide

This document describes how to build the Microsoft Security Copilot Knowledge Pack from source.

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

The build script is `scripts/build_security_copilot_pack.py`.

### Pack Constants

| Constant | Value |
|----------|-------|
| `PACK_DIR` | `data/packs/security-copilot` |
| `URLS_FILE` | `data/packs/security-copilot/urls.txt` |
| `DB_PATH` | `data/packs/security-copilot/pack.db` |
| `MANIFEST_PATH` | `data/packs/security-copilot/manifest.json` |
| `domain` | `security_copilot` |
| `category` | `Microsoft Security Copilot` |

## Running the Build

### Test Build (Recommended First Step)

Processes only the first 5 URLs. Completes in 5-10 minutes.

```bash
uv run python scripts/build_security_copilot_pack.py --test-mode
```

Test mode auto-deletes any existing database and rebuilds without prompting.

### Full Build

Processes all 58 URLs. Completes in approximately 3-5 hours.

```bash
uv run python scripts/build_security_copilot_pack.py
```

If `pack.db` already exists, the script prompts before deleting it:

```
Database already exists: data/packs/security-copilot/pack.db
Delete and rebuild? (y/N):
```

To script non-interactively:

```bash
echo "y" | uv run python scripts/build_security_copilot_pack.py
```

## Build Pipeline

Each URL goes through six stages:

### Stage 1: URL Loading (`load_urls`)
- Reads `data/packs/security-copilot/urls.txt`
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
- Extracts: named entities (plugins, features, concepts), relationships, key facts
- Domain hint: `security_copilot` (improves entity relevance)

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
data/packs/security-copilot/
├── pack.db/            # KuzuDB graph database (directory)
├── manifest.json       # Pack metadata and graph stats
├── urls.txt            # Source URLs (58 entries)
├── BUILD.md            # This file
├── README.md           # Pack documentation
└── skill.md            # Claude Code skill description
```

### Sample `manifest.json`

```json
{
  "name": "security-copilot",
  "version": "1.0.0",
  "description": "Expert knowledge of Microsoft Security Copilot covering AI-powered security analysis, threat intelligence, incident response, plugin ecosystem, promptbooks, embedded experiences, and administration.",
  "graph_stats": {
    "articles": 50,
    "entities": 680,
    "relationships": 1350,
    "size_mb": 48.2
  },
  "eval_scores": {
    "accuracy": 0.0,
    "hallucination_rate": 0.0,
    "citation_quality": 0.0
  },
  "source_urls": [
    "https://learn.microsoft.com/en-us/copilot/security/microsoft-security-copilot",
    "https://learn.microsoft.com/en-us/copilot/security/get-started-security-copilot"
  ],
  "created": "2026-03-03T12:00:00Z",
  "license": "MIT"
}
```

## Logs

Build logs are written to `logs/build_security_copilot_pack.log` and also streamed to stdout.

```bash
tail -f logs/build_security_copilot_pack.log
```

## Verifying the Build

### Check Manifest

```bash
python -m json.tool data/packs/security-copilot/manifest.json
```

Expected values:
- `graph_stats.articles` ≥ 40
- `graph_stats.entities` ≥ 400
- `graph_stats.size_mb` between 20 and 150

### Query the Database

```python
import kuzu

db = kuzu.Database("data/packs/security-copilot/pack.db")
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
    db_path="data/packs/security-copilot/pack.db",
    use_enhancements=True,
)
result = agent.query("What is a Security Copilot promptbook?")
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
uv run python scripts/build_security_copilot_pack.py --test-mode
```

### HTTP errors or rate limiting from `learn.microsoft.com`

Some pages at `learn.microsoft.com/en-us/copilot/security/` may return 404 if a feature has been renamed or reorganized. The build continues with any failed URLs counted separately. Check the log for patterns — a handful of failures is expected for a rapidly evolving product like Security Copilot.

### Duplicate URL warnings

`urls.txt` contains some intentional duplicates (e.g., `get-started-security-copilot` and `manage-usage` appear in multiple sections). The graph deduplication check handles this at write time.

### Out of disk space

Ensure at least 2 GB free before building.

### Partial build recovery

If a build is interrupted, re-run the full build. The script does not resume partial builds; it rebuilds from scratch.

## Updating the Pack

### Adding URLs

1. Add HTTPS URLs to `data/packs/security-copilot/urls.txt`
2. Verify the URL is accessible:
   ```bash
   curl -I "https://learn.microsoft.com/en-us/copilot/security/..."
   ```
3. Rebuild

### Refreshing Stale Content

Security Copilot is updated frequently. To refresh all content:

```bash
echo "y" | uv run python scripts/build_security_copilot_pack.py
```

## Distribution

### Create Archive

```bash
cd data/packs
tar -czf security-copilot-1.0.0.tar.gz security-copilot/
```

### Upload to GitHub Releases

```bash
gh release create security-copilot-v1.0.0 \
  data/packs/security-copilot-1.0.0.tar.gz \
  --title "Microsoft Security Copilot Knowledge Pack v1.0.0"
```

---

**Script**: `scripts/build_security_copilot_pack.py`
**Domain**: `security_copilot`
**Last Updated**: 2026-03-03
