# LLM Seed Researcher

**Automatic discovery of authoritative sources and article URLs for knowledge pack creation**

The LLM Seed Researcher uses Claude Opus 4.6 to intelligently discover authoritative sources for any domain, then employs multiple strategies to extract article URLs for knowledge pack creation.

## Overview

Building knowledge packs manually requires identifying authoritative sources and extracting article URLs—a time-consuming process. The LLM Seed Researcher automates this workflow by:

1. **Discovering Sources**: Using Claude to identify the most authoritative sources for a domain
2. **Extracting URLs**: Employing multiple strategies (sitemap, RSS, crawl, LLM) to find article URLs
3. **Validating URLs**: Checking accessibility and content type
4. **Ranking URLs**: Scoring by authority, recency, and content quality

## Quick Start

### Prerequisites

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Standalone Research

Discover sources and article URLs for a domain:

```bash
wikigr research-sources "quantum physics" --max-sources 10 --max-urls 100 --output research.json
```

### Integrated Pack Creation

Create a knowledge pack with automatic source discovery:

```bash
wikigr pack create --auto-discover "climate science" --pack-name climate-science-expert
```

## Usage

### Command: `wikigr research-sources`

Research authoritative sources for a domain.

**Syntax**:
```bash
wikigr research-sources <domain> [options]
```

**Arguments**:
- `domain`: Topic or domain to research (e.g., "quantum physics", "machine learning")

**Options**:
- `--max-sources N`: Maximum sources to discover (default: 10)
- `--max-urls N`: Maximum URLs per source (default: 100)
- `--output FILE`: Save results to JSON file
- `--validate`: Validate all URLs (slower, default: false)
- `--no-cache`: Skip cache, always use fresh LLM calls

**Examples**:

```bash
# Basic research
wikigr research-sources "artificial intelligence"

# Research with validation
wikigr research-sources "climate science" --validate --output climate-sources.json

# Discover more sources
wikigr research-sources "quantum computing" --max-sources 20 --max-urls 200
```

**Output**:

```json
{
  "domain": "quantum physics",
  "sources": [
    {
      "domain": "arxiv.org",
      "url": "https://arxiv.org",
      "authority_score": 0.95,
      "rationale": "Premier preprint repository for physics research",
      "article_count": 150,
      "extraction_methods": ["sitemap", "rss"]
    }
  ],
  "urls": [
    {
      "url": "https://arxiv.org/abs/2401.12345",
      "title": "Quantum Entanglement in Many-Body Systems",
      "published_date": "2024-01-15",
      "extraction_method": "rss",
      "authority_score": 0.95,
      "content_score": 0.88,
      "rank_score": 0.92
    }
  ],
  "summary": {
    "total_sources": 10,
    "total_urls": 847,
    "validated_urls": 812,
    "avg_authority": 0.87
  }
}
```

### Command: `wikigr pack create --auto-discover`

Create a knowledge pack with automatic source discovery.

**Syntax**:
```bash
wikigr pack create --auto-discover <domain> [options]
```

**Arguments**:
- `domain`: Topic or domain for the knowledge pack

**Options**:
- `--pack-name NAME`: Pack name (auto-generated if not provided)
- `--max-sources N`: Maximum sources to discover (default: 10)
- `--target N`: Target article count for pack (default: 1000)
- `--validate`: Validate URLs before pack creation

**Examples**:

```bash
# Create pack with auto-discovery
wikigr pack create --auto-discover "quantum physics" --pack-name quantum-physics-expert

# Create larger pack
wikigr pack create --auto-discover "machine learning" --target 2000 --max-sources 15
```

**Workflow**:

1. **Research**: Discover authoritative sources using LLM
2. **Extract**: Extract article URLs using multi-strategy approach
3. **Rank**: Score and rank URLs by quality
4. **Generate**: Create seeds.json for pack creation
5. **Build**: Execute standard pack creation workflow

## Multi-Strategy Extraction

The researcher tries multiple extraction strategies in order until sufficient URLs are found:

### 1. Sitemap Extraction

**How it works**: Parses XML sitemaps (`/sitemap.xml`, `/sitemap_index.xml`)

**Advantages**:
- Fast and comprehensive
- Standard format
- Includes metadata (last modified date)

**Best for**: Sites with proper sitemap configuration (most modern CMS)

**Example**:
```python
researcher = LLMSeedResearcher()
source = DiscoveredSource(domain="example.com", url="https://example.com", ...)
urls = researcher._extract_from_sitemap("https://example.com", max_urls=100)
```

### 2. RSS/Atom Feed Extraction

**How it works**: Parses RSS and Atom feeds

**Advantages**:
- Recent articles
- Structured metadata (title, date, description)
- Common on news sites and blogs

**Best for**: Sites with active RSS feeds (news, blogs, research sites)

**Example**:
```python
urls = researcher._extract_from_rss("https://example.com", max_urls=100)
```

### 3. Web Crawling

**How it works**: BFS crawling with depth limit (default: 2 levels)

**Advantages**:
- Works on any site with internal links
- Discovers deeply nested content

**Limitations**:
- Slower than sitemap/RSS
- Respects robots.txt
- Depth-limited to avoid infinite crawls

**Best for**: Sites without sitemaps or RSS feeds

**Example**:
```python
urls = researcher._extract_by_crawl("https://example.com", max_urls=100, max_depth=2)
```

### 4. LLM Extraction (Fallback)

**How it works**: Asks Claude Opus 4.6 to suggest article URLs

**Advantages**:
- Always produces results
- Understands domain context
- Can suggest high-value articles

**Limitations**:
- Slower (LLM API call)
- More expensive
- May suggest URLs that don't exist

**Best for**: Last resort when technical methods fail

**Example**:
```python
urls = researcher._extract_via_llm(source, max_urls=50)
```

## URL Validation

All discovered URLs are validated before inclusion:

**Checks**:
- HTTP 200 status code
- Content-Type is `text/html`
- Respects robots.txt
- Response within timeout (default: 5s)

**Validation Mode**:
- **Default**: Validate in parallel (fast, 10 workers)
- **Disabled**: Skip validation (fastest, use `--no-validate`)
- **Strict**: Validate + check content structure (slowest)

**Example**:
```python
is_valid = researcher.validate_url("https://example.com/article")
# Returns: True if accessible and valid, False otherwise
```

## URL Ranking

URLs are ranked by a composite score:

**Scoring Formula**:
```
rank_score = (authority × 0.4) + (recency × 0.3) + (content × 0.3)
```

**Components**:

1. **Authority Score (40%)**:
   - Inherited from source authority
   - Range: 0.0 - 1.0
   - Based on institutional reputation

2. **Recency Score (30%)**:
   - Publication date (if available)
   - Prefer articles within 2 years
   - Decay formula: `max(0, 1 - (age_days / 730))`

3. **Content Score (30%)**:
   - Word count (prefer 1000-5000 words)
   - Header structure (proper H1-H6)
   - Link quality (internal/external ratio)
   - Range: 0.0 - 1.0

**Example**:
```python
ranked_urls = researcher.rank_urls(extracted_urls)
# Returns URLs sorted by rank_score (highest first)
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key (required) | - |
| `WIKIGR_CACHE_DIR` | Cache directory | `~/.wikigr/cache` |
| `WIKIGR_CACHE_TTL` | Cache TTL in days | `7` |
| `WIKIGR_REQUEST_TIMEOUT` | HTTP timeout (seconds) | `5.0` |
| `WIKIGR_MAX_WORKERS` | Parallel validation workers | `10` |

### Class Configuration

```python
from wikigr.packs.seed_researcher import LLMSeedResearcher

researcher = LLMSeedResearcher(
    api_key="sk-ant-...",  # Or from ANTHROPIC_API_KEY
    model="claude-opus-4-6"  # LLM model to use
)

# Customize behavior
researcher.timeout = 10.0  # Longer timeout for slow sites
researcher.max_crawl_depth = 3  # Deeper crawling
researcher.user_agent = "MyBot/1.0"  # Custom user agent
```

## Caching

The researcher caches source discoveries to reduce API costs and improve response time.

**Cache Behavior**:
- Cache location: `~/.wikigr/cache/sources/`
- Cache key: Hash of domain string
- TTL: 7 days (configurable)
- Format: JSON with timestamp

**Cache Management**:

```bash
# Clear cache (force fresh research)
rm -rf ~/.wikigr/cache/sources/

# Use fresh research (skip cache)
wikigr research-sources "domain" --no-cache
```

## Error Handling

### Exception Hierarchy

```python
SeedResearcherError          # Base exception
├── LLMAPIError              # Anthropic API failures
├── ExtractionError          # URL extraction failures
├── ValidationError          # URL validation failures
└── ConfigurationError       # Missing API key, invalid config
```

### Retry Logic

**LLM API Calls**:
- Retries: 3
- Backoff: Exponential (1s, 2s, 4s, 8s)
- Catches: `anthropic.RateLimitError`, `anthropic.APIError`

**HTTP Requests**:
- Retries: 2
- Backoff: Linear (1s, 2s)
- Catches: `requests.ConnectionError`, `requests.Timeout`

**No Retry**:
- 400 Bad Request (client errors)
- Validation failures (invalid URL format)
- Configuration errors (missing API key)

### Graceful Degradation

When strategies fail, the researcher gracefully degrades:

1. Sitemap fails → Try RSS
2. RSS fails → Try crawl
3. Crawl fails → Try LLM
4. LLM fails → Return partial results

**Example**:
```python
try:
    urls = researcher.extract_article_urls(source, max_urls=100)
except ExtractionError as e:
    # Some strategies failed, but partial results returned
    print(f"Warning: {e}")
    print(f"Extracted {len(urls)} URLs (partial results)")
```

## API Reference

### DiscoveredSource

**Dataclass** representing an authoritative source.

```python
@dataclass
class DiscoveredSource:
    domain: str                      # Domain name (e.g., "nasa.gov")
    url: str                         # Base URL
    authority_score: float           # Authority ranking (0.0-1.0)
    rationale: str                   # Why this source is authoritative
    article_count: int               # Number of extractable articles
    extraction_methods: list[str]    # Supported extraction methods
```

### ExtractedURL

**Dataclass** representing a discovered article URL.

```python
@dataclass
class ExtractedURL:
    url: str                         # Full article URL
    title: str | None                # Article title (if available)
    published_date: str | None       # Publication date (ISO format)
    extraction_method: str           # How URL was found
    authority_score: float           # Inherited from source
    content_score: float             # Content quality score (0.0-1.0)
    rank_score: float                # Final combined score
```

### LLMSeedResearcher

Main researcher class.

#### `__init__(api_key: str | None = None, model: str = "claude-opus-4-6")`

Initialize researcher with Anthropic API client.

**Parameters**:
- `api_key`: Anthropic API key (or from `ANTHROPIC_API_KEY`)
- `model`: Claude model name (default: `claude-opus-4-6`)

**Raises**:
- `ConfigurationError`: If API key not provided and not in environment

#### `discover_sources(domain: str, max_sources: int = 10) -> list[DiscoveredSource]`

Discover authoritative sources for a domain using LLM.

**Parameters**:
- `domain`: Topic or domain (e.g., "quantum physics")
- `max_sources`: Maximum number of sources to return

**Returns**:
- List of `DiscoveredSource` objects ranked by authority

**Raises**:
- `LLMAPIError`: On Anthropic API failures

#### `extract_article_urls(source: DiscoveredSource, max_urls: int = 100, strategies: list[str] | None = None) -> list[ExtractedURL]`

Extract article URLs using multi-strategy approach.

**Parameters**:
- `source`: DiscoveredSource to extract from
- `max_urls`: Maximum URLs to extract
- `strategies`: Strategies to try (default: `["sitemap", "rss", "crawl", "llm"]`)

**Returns**:
- List of `ExtractedURL` objects

**Raises**:
- `ExtractionError`: On extraction failures (with partial results)

#### `validate_url(url: str) -> bool`

Validate URL accessibility and content type.

**Parameters**:
- `url`: URL to validate

**Returns**:
- `True` if URL is valid and accessible, `False` otherwise

#### `rank_urls(urls: list[ExtractedURL]) -> list[ExtractedURL]`

Rank URLs by authority, recency, and content quality.

**Parameters**:
- `urls`: List of ExtractedURL objects to rank

**Returns**:
- URLs sorted by rank_score (highest first)

## Performance

### Typical Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Discover sources (10) | 5-10s | LLM API call |
| Extract via sitemap | 1-3s | Fast, standard format |
| Extract via RSS | 2-5s | Depends on feed size |
| Extract via crawl | 10-30s | Depends on depth |
| Extract via LLM | 10-20s | Slow, last resort |
| Validate 100 URLs | 5-10s | Parallel (10 workers) |
| Full research cycle | 20-60s | Domain-dependent |

### Optimization Tips

1. **Use Cache**: Skip cache only when sources change frequently
2. **Limit Sources**: Fewer sources = faster research
3. **Skip Validation**: Disable validation for initial exploration
4. **Prefer Sitemaps**: Sites with sitemaps extract 10x faster
5. **Parallel Validation**: Increase `WIKIGR_MAX_WORKERS` for faster validation

## Limitations

### Current Limitations

1. **LLM Dependency**: Requires Claude Opus 4.6 API access
2. **English Only**: Optimized for English-language sources
3. **No Authentication**: Cannot extract from login-required sites
4. **Rate Limiting**: Subject to Anthropic API rate limits
5. **No PDF Extraction**: Does not extract URLs from PDF files
6. **No Video Content**: Focuses on text articles only

### False Positive Rate

**Target**: <10% false positives (invalid or low-quality URLs)

**Validation Methods**:
- HTTP accessibility check
- Content-Type verification
- Robots.txt compliance
- Manual inspection in tests

**Typical Causes**:
- Dynamic URLs (session IDs, temporary links)
- Paywalled content (403/402 errors)
- Redirected URLs (301/302 chains)
- JavaScript-required pages (empty HTML)

## Troubleshooting

### "ConfigurationError: ANTHROPIC_API_KEY not set"

**Cause**: Missing API key

**Solution**:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "LLMAPIError: Rate limit exceeded"

**Cause**: Too many API requests

**Solution**:
- Wait and retry (automatic exponential backoff)
- Use cached results (`--no-cache=false`)
- Reduce `--max-sources` to minimize API calls

### "ExtractionError: All strategies failed"

**Cause**: No extraction strategies succeeded

**Solutions**:
- Check internet connection
- Verify source URL is accessible
- Try fewer URLs (`--max-urls 50`)
- Enable LLM fallback strategy

### "ValidationError: All URLs failed validation"

**Cause**: URLs are inaccessible or invalid

**Solutions**:
- Skip validation (`--no-validate`)
- Increase timeout (`WIKIGR_REQUEST_TIMEOUT=10`)
- Check if source requires authentication
- Verify robots.txt isn't blocking access

## Examples

### Example 1: Research Quantum Physics

```bash
wikigr research-sources "quantum physics" --max-sources 10 --output quantum-sources.json
```

**Output** (`quantum-sources.json`):
```json
{
  "domain": "quantum physics",
  "sources": [
    {"domain": "arxiv.org", "authority_score": 0.95},
    {"domain": "nature.com", "authority_score": 0.92},
    {"domain": "mit.edu", "authority_score": 0.90}
  ],
  "urls": [
    {
      "url": "https://arxiv.org/abs/2401.12345",
      "title": "Quantum Entanglement",
      "rank_score": 0.92
    }
  ]
}
```

### Example 2: Create Climate Science Pack

```bash
wikigr pack create --auto-discover "climate science" --pack-name climate-expert --target 1500
```

**Workflow**:
1. Research sources (NOAA, NASA, IPCC, etc.)
2. Extract 1500+ article URLs
3. Generate seeds.json
4. Build knowledge pack
5. Install to `~/.wikigr/packs/climate-expert/`

### Example 3: Programmatic Usage

```python
from wikigr.packs.seed_researcher import LLMSeedResearcher, DiscoveredSource

# Initialize researcher
researcher = LLMSeedResearcher(api_key="sk-ant-...")

# Discover sources
sources = researcher.discover_sources("machine learning", max_sources=5)

# Extract URLs from top source
top_source = sources[0]
urls = researcher.extract_article_urls(top_source, max_urls=100)

# Rank and get top 10
ranked = researcher.rank_urls(urls)
top_10 = ranked[:10]

# Validate top URLs
valid_urls = [url for url in top_10 if researcher.validate_url(url.url)]

print(f"Found {len(valid_urls)} valid high-quality URLs")
```

## Future Enhancements

Potential future improvements:

1. **Multi-language Support**: Extend to non-English sources
2. **PDF Extraction**: Extract articles from academic PDFs
3. **Video Transcripts**: Extract and index video content
4. **Authentication Support**: Handle login-required sites
5. **Incremental Updates**: Track source updates over time
6. **Quality Feedback**: Learn from user feedback on URL quality
7. **Custom Scrapers**: Plugin system for site-specific extractors
8. **Parallel Source Research**: Research multiple domains simultaneously

## See Also

- [Knowledge Packs Overview](../README.md)
- [Pack Creation Guide](pack-creation.md)
- [Pack Manifest Format](manifest-format.md)
- [CLI Reference](cli-reference.md)
