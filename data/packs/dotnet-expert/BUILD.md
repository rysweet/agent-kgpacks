# .NET Expert Knowledge Pack - Build Guide

This document describes how to build the .NET Expert Knowledge Pack from source.

## Prerequisites

### System Requirements
- Python 3.10 or higher
- 4 GB RAM minimum
- 5 GB disk space (temporary files during build)
- Internet connection for web scraping

### Python Dependencies
```bash
pip install kuzu openai anthropic beautifulsoup4 requests lxml
```

### Environment Variables
```bash
# Required: One of these for LLM entity extraction
export OPENAI_API_KEY="your-key-here"
# OR
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-key-here"

# Optional: For embeddings (defaults to OpenAI text-embedding-3-small)
export EMBEDDING_MODEL="text-embedding-3-small"
```

## Build Methods

### Method 1: Using Generic Pack Builder (Recommended)

```bash
python scripts/build_pack_generic.py \
  --pack-name dotnet-expert \
  --urls-file data/packs/dotnet-expert/urls.txt \
  --output-dir data/packs/dotnet-expert \
  --category ".NET" \
  --parallel 4
```

**Arguments**:
- `--pack-name`: Name of the pack (used in manifest)
- `--urls-file`: Path to URLs file (250 URLs)
- `--output-dir`: Output directory for pack.db
- `--category`: Category for articles (defaults to ".NET")
- `--parallel`: Number of parallel workers (defaults to 4)

### Method 2: Custom Build Script

Create `scripts/build_dotnet_pack.py`:

```python
#!/usr/bin/env python3
"""Build .NET Expert Knowledge Pack."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.src.sources.web import WebContentSource
from bootstrap.src.expansion.processor import ArticleProcessor
from bootstrap.schema.ryugraph_schema import create_schema
from bootstrap.src.extraction.llm_extractor import get_extractor
from bootstrap.src.embeddings.generator import EmbeddingGenerator
import kuzu
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PACK_DIR = Path('data/packs/dotnet-expert')
URLS_FILE = PACK_DIR / 'urls.txt'
DB_PATH = PACK_DIR / 'pack.db'

# Load URLs
urls = []
with open(URLS_FILE) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            urls.append(line)

logger.info(f'Loaded {len(urls)} URLs')

# Create database and schema
if DB_PATH.exists():
    import shutil
    shutil.rmtree(DB_PATH) if DB_PATH.is_dir() else DB_PATH.unlink()

create_schema(str(DB_PATH), drop_existing=True)
db = kuzu.Database(str(DB_PATH))
conn = kuzu.Connection(db)

# Initialize components
web_source = WebContentSource()
processor = ArticleProcessor(
    db_path=str(DB_PATH),
    extractor=get_extractor(),
    embedder=EmbeddingGenerator()
)

# Process each URL
successful = 0
failed = 0

for i, url in enumerate(urls, 1):
    logger.info(f'Processing {i}/{len(urls)}: {url}')
    try:
        content = web_source.fetch(url)
        if not content:
            logger.warning(f'No content from {url}')
            failed += 1
            continue

        processor.process(content, category='.NET')
        successful += 1

    except Exception as e:
        logger.error(f'Failed to process {url}: {e}')
        failed += 1

# Get stats
result = conn.execute('MATCH (a:Article) RETURN count(a) AS count')
article_count = int(result.get_as_df().iloc[0]['count'])

result = conn.execute('MATCH (e:Entity) RETURN count(e) AS count')
entity_count = int(result.get_as_df().iloc[0]['count'])

result = conn.execute('MATCH ()-[r:ENTITY_RELATION]->() RETURN count(r) AS count')
rel_count = int(result.get_as_df().iloc[0]['count'])

logger.info(f'\n=== BUILD COMPLETE ===')
logger.info(f'Successful: {successful}, Failed: {failed}')
logger.info(f'Articles: {article_count}, Entities: {entity_count}, Relationships: {rel_count}')

# Create manifest
manifest = {
    'name': 'dotnet-expert',
    'version': '1.0.0',
    'description': '.NET Expert knowledge pack',
    'build_date': '2026-02-26',
    'graph_stats': {
        'articles': article_count,
        'entities': entity_count,
        'relationships': rel_count,
        'size_mb': round(sum(f.stat().st_size for f in DB_PATH.rglob('*') if f.is_file()) / 1024 / 1024, 2)
    },
    'sources': {
        'microsoft_learn_csharp': 60,
        'microsoft_learn_aspnet': 50,
        'microsoft_learn_efcore': 40,
        'microsoft_learn_aspire': 30,
        'architecture_patterns': 70
    }
}

with open(PACK_DIR / 'manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)

logger.info(f'Manifest written to {PACK_DIR}/manifest.json')
```

Then run:
```bash
python scripts/build_dotnet_pack.py
```

## Build Process Details

### Stage 1: URL Loading
- Reads `urls.txt` (250 URLs)
- Filters comments and blank lines
- Validates URL format

### Stage 2: Web Scraping
- Fetches HTML content using WebContentSource
- Parses with BeautifulSoup
- Extracts title, body text, metadata
- Handles rate limiting and retries

### Stage 3: Content Processing
- Sends text to LLM for entity extraction
- Identifies entities (concepts, frameworks, patterns)
- Extracts relationships between entities
- Maps to WikiGR schema

### Stage 4: Embedding Generation
- Generates vector embeddings for text chunks
- Uses text-embedding-3-small by default
- Stores in Kuzu vector index
- Enables semantic search

### Stage 5: Database Creation
- Inserts articles, entities, relationships into Kuzu
- Creates indexes for performance
- Validates graph structure
- Compacts database

### Stage 6: Manifest Generation
- Collects statistics (article count, entities, relationships)
- Records build date and version
- Calculates database size
- Writes manifest.json

## Build Time Estimates

- **Sequential**: ~2-3 hours (250 URLs)
- **Parallel (4 workers)**: ~45-60 minutes
- **Network-dependent**: Varies with bandwidth

## Troubleshooting

### HTTP 429 (Rate Limiting)
```
Solution: Add delay between requests or use parallel workers
Web scraper includes built-in retry with exponential backoff
```

### HTTP 403 (Forbidden)
```
Solution: Some sites block scrapers
Check robots.txt, use user-agent header
Consider alternative URL or manual download
```

### LLM API Errors
```
Solution: Check API key, endpoint, rate limits
Use error logging to identify problematic URLs
Retry with exponential backoff
```

### Out of Memory
```
Solution: Reduce parallel workers
Process in smaller batches
Increase system RAM or use swap
```

## Validation

### Post-Build Checks

```bash
# Check database exists and has content
python -c "
import kuzu
db = kuzu.Database('data/packs/dotnet-expert/pack.db')
conn = kuzu.Connection(db)
result = conn.execute('MATCH (a:Article) RETURN count(a)')
print(f'Articles: {result.get_as_df().iloc[0][0]}')
"

# Verify manifest
cat data/packs/dotnet-expert/manifest.json | jq .

# Check evaluation questions
wc -l data/packs/dotnet-expert/eval/questions.jsonl
```

### Quality Checks

1. **URL Coverage**: Verify all 250 URLs processed successfully
2. **Entity Count**: Should have 1000+ entities extracted
3. **Relationship Count**: Should have 2000+ relationships
4. **Database Size**: Should be 500-1000 MB
5. **Vector Index**: Verify embeddings created

## Performance Optimization

### Faster Builds
```bash
# Use more parallel workers (if sufficient API quota)
--parallel 8

# Use faster embedding model
export EMBEDDING_MODEL="text-embedding-ada-002"

# Skip embeddings during initial build (add later)
--skip-embeddings
```

### Resource Optimization
```bash
# Process in batches
--batch-size 50

# Use local LLM for entity extraction (if available)
--local-llm localhost:8000
```

## Incremental Updates

To add new URLs without rebuilding entire pack:

```bash
# Append new URLs to urls.txt
echo "https://learn.microsoft.com/en-us/dotnet/csharp/new-feature" >> urls.txt

# Build with append mode (if supported)
python scripts/build_pack_generic.py \
  --pack-name dotnet-expert \
  --urls-file new_urls.txt \
  --output-dir data/packs/dotnet-expert \
  --mode append
```

## Distribution

### Create Distribution Archive

```bash
cd data/packs
tar -czf dotnet-expert-1.0.0.tar.gz dotnet-expert/
```

### Upload to Distribution Server

```bash
# Upload to GitHub Releases
gh release create v1.0.0 dotnet-expert-1.0.0.tar.gz

# Or upload to cloud storage
az storage blob upload \
  --account-name wikigr \
  --container packs \
  --file dotnet-expert-1.0.0.tar.gz
```

## Maintenance

### Regular Updates
- **Quarterly**: Rebuild with latest documentation
- **Major .NET Releases**: Rebuild within 1 month
- **URL Validation**: Check for broken links monthly
- **Content Refresh**: Re-scrape modified pages

### Version Bumping
- **Patch (1.0.x)**: URL additions, question updates
- **Minor (1.x.0)**: New source additions, significant content updates
- **Major (x.0.0)**: Schema changes, major restructuring

## Support

For build issues:
1. Check logs in `data/packs/dotnet-expert/build.log`
2. Verify environment variables
3. Test with small URL subset first
4. Open issue on GitHub with logs

---

**Last Updated**: 2026-02-26
**Build Version**: 1.0.0
