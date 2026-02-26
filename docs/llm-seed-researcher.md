# LLM Seed Researcher

Automated source discovery and URL extraction for knowledge pack creation using Claude Opus 4.6.

## Overview

The LLM Seed Researcher automates the discovery of authoritative sources for any domain, eliminating manual curation. It uses Claude's reasoning to identify high-quality documentation, blogs, and technical resources, then extracts article URLs using multiple strategies.

## Features

- **Intelligent Source Discovery**: Uses Claude Opus 4.6 to identify authoritative sources
- **Authority Scoring**: Ranks sources by authority (official docs > blogs > news)
- **Multi-Strategy URL Extraction**:
  - Sitemap.xml parsing
  - RSS/Atom feed extraction
  - Index page crawling
  - LLM-based URL generation
- **URL Validation**: Checks accessibility and content quality
- **Smart Ranking**: Ranks URLs by authority, recency, and content length

## Command-Line Usage

### Standalone Research Mode

Discover authoritative sources for any domain:

```bash
# Basic usage
wikigr research-sources ".NET programming"

# Save results to file
wikigr research-sources "Rust language" --output rust-sources.json

# Limit number of sources
wikigr research-sources "Machine Learning" --max-sources 5

# Verbose output
wikigr research-sources "Kubernetes" --verbose
```

**Output:**
```
Discovered 10 authoritative sources for '.NET programming'
======================================================================

1. https://docs.microsoft.com/dotnet
   Authority: 0.95
   Type: official_docs
   Estimated articles: 1000
   Description: Official .NET documentation

2. https://devblogs.microsoft.com/dotnet
   Authority: 0.85
   Type: blog
   Estimated articles: 500
   Description: .NET team blog
```

### Integrated Pack Creation

Create a knowledge pack with automatic source discovery:

```bash
# Auto-discover and create pack
wikigr pack create \
  --name dotnet-expert \
  --auto-discover ".NET programming" \
  --target 500 \
  --output ./packs

# Traditional mode (requires manual topics file)
wikigr pack create \
  --name rust-expert \
  --topics rust-topics.txt \
  --target 500 \
  --output ./packs
```

## Python API

### Basic Source Discovery

```python
from wikigr.packs.seed_researcher import LLMSeedResearcher

researcher = LLMSeedResearcher()

# Discover sources
sources = researcher.discover_sources(".NET programming", max_sources=10)

for source in sources:
    print(f"{source.url} (authority: {source.authority_score})")
```

### Extract Article URLs

```python
# Extract URLs from a source using multiple strategies
urls = researcher.extract_article_urls(
    "https://docs.microsoft.com/dotnet",
    max_urls=100,
    strategies=["sitemap", "rss", "index", "llm"]
)

print(f"Found {len(urls)} article URLs")
```

### Validate URLs

```python
# Validate that URLs are accessible and contain substantial content
for url in urls:
    is_valid, metadata = researcher.validate_url(url)

    if is_valid:
        print(f"✓ {url} ({metadata['word_count']} words)")
    else:
        print(f"✗ {url} - {metadata['error']}")
```

### Rank URLs

```python
# Rank URLs by authority, recency, and content quality
ranked = researcher.rank_urls(
    urls,
    authority_score=0.9,  # Source authority
    metadata_list=None    # Optional: validation metadata
)

# Print top 10 URLs
for url, score in ranked[:10]:
    print(f"{score:.3f} - {url}")
```

## Full Workflow Example

```python
from wikigr.packs.seed_researcher import LLMSeedResearcher

# Initialize researcher
researcher = LLMSeedResearcher()

# 1. Discover authoritative sources
print("Discovering sources...")
sources = researcher.discover_sources("Rust programming language", max_sources=10)
print(f"Found {len(sources)} sources")

# 2. Extract URLs from top sources
all_urls = []
for source in sources[:3]:  # Use top 3 sources
    print(f"Extracting URLs from {source.url}...")
    urls = researcher.extract_article_urls(source.url, max_urls=50)
    all_urls.extend(urls)

print(f"Total URLs: {len(all_urls)}")

# 3. Validate URLs
validated = []
metadata_list = []

for url in all_urls:
    is_valid, metadata = researcher.validate_url(url)
    if is_valid:
        validated.append(url)
        metadata_list.append(metadata)

print(f"Valid URLs: {len(validated)}")

# 4. Rank URLs
ranked = researcher.rank_urls(
    validated,
    authority_score=sources[0].authority_score,
    metadata_list=metadata_list
)

# 5. Use top-ranked URLs for pack creation
top_urls = [url for url, score in ranked[:100]]
print(f"Top 100 URLs ready for pack creation")
```

## Configuration

### Model Selection

```python
# Use different Claude models
researcher = LLMSeedResearcher(
    model="claude-opus-4-6-20250826",  # Default: most accurate
    # model="claude-haiku-4-5-20251001",  # Faster, cheaper
)
```

### HTTP Timeout and Retries

```python
researcher = LLMSeedResearcher(
    timeout=60,        # Request timeout in seconds (default: 30)
    max_retries=5      # Max retry attempts (default: 3)
)
```

## Authority Scoring

Sources are scored on a 0.0-1.0 scale:

| Source Type | Authority Range | Example |
|-------------|----------------|---------|
| Official docs | 0.9 - 1.0 | docs.microsoft.com, doc.rust-lang.org |
| Official blogs | 0.7 - 0.9 | devblogs.microsoft.com |
| Technical sites | 0.6 - 0.8 | rust-lang.github.io |
| Community blogs | 0.4 - 0.6 | Individual developer blogs |
| News sites | 0.3 - 0.5 | TechCrunch, Ars Technica |

## URL Extraction Strategies

### 1. Sitemap.xml

Parses XML sitemaps to extract all indexed URLs.

**Pros:** Complete, structured, efficient
**Cons:** Not all sites have sitemaps

### 2. RSS/Atom Feeds

Extracts URLs from RSS and Atom feeds.

**Pros:** Good for blogs and news sites
**Cons:** Limited to recent articles

### 3. Index Crawling

Scrapes the main page to find links.

**Pros:** Works for any site
**Cons:** May miss deep pages

### 4. LLM Generation

Uses Claude to generate likely URL patterns.

**Pros:** Fallback when other methods fail
**Cons:** May generate non-existent URLs

## URL Ranking Algorithm

URLs are ranked by combining multiple signals:

```
score = authority_score                  # Base (0.0-1.0)
      + length_boost                     # 0-0.2 (normalized by word count)
      + pattern_boost                    # 0-0.15 (/docs/ > /tutorial/ > /blog/)
      + recency_boost                    # 0-0.08 (current/recent year in URL)
      - long_url_penalty                 # -0.1 (URLs > 200 chars)
```

**Pattern Boosts:**
- `/docs/`, `/documentation/`: +0.15
- `/tutorial/`, `/guide/`: +0.10
- `/blog/`, `/article/`: +0.05

## Success Criteria

The researcher meets these targets:

- ✅ Discovers ≥10 sources for any domain
- ✅ <10% false positives (non-existent or inaccessible URLs)
- ✅ Prioritizes authoritative sources (official docs first)
- ✅ Handles multiple content types (docs, blogs, tutorials)

## Error Handling

The researcher gracefully handles common failures:

```python
try:
    sources = researcher.discover_sources("invalid domain")
except ValueError as e:
    print(f"Invalid input: {e}")
except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
```

**Common Errors:**
- `ValueError`: Empty domain or invalid JSON from Claude
- `requests.exceptions.Timeout`: HTTP request timeout
- `requests.exceptions.ConnectionError`: Network unreachable
- `json.JSONDecodeError`: Malformed JSON response

## Testing

Run the comprehensive test suite:

```bash
# Run all seed researcher tests
pytest tests/packs/test_seed_researcher.py -v

# Run with coverage
pytest tests/packs/test_seed_researcher.py --cov=wikigr.packs.seed_researcher

# Run specific test class
pytest tests/packs/test_seed_researcher.py::TestDiscoverSources -v
```

The test suite includes 27+ tests covering:
- Source discovery with various inputs
- All URL extraction strategies
- URL validation with edge cases
- Ranking algorithm correctness
- Error handling and edge cases
- Full integration workflows

## Limitations

- **LLM Dependency**: Requires ANTHROPIC_API_KEY and API access
- **Rate Limits**: Subject to Anthropic API rate limits
- **Network Required**: Cannot work offline (except for cached results)
- **Language**: Optimized for English-language sources
- **Coverage**: May miss sources behind authentication or paywalls

## Future Enhancements

Potential improvements for future versions:

1. **Caching**: Cache discovered sources to reduce API calls
2. **Parallel Extraction**: Extract URLs from multiple sources concurrently
3. **Quality Scoring**: Add content quality metrics (readability, depth)
4. **Multilingual**: Support non-English domains
5. **Custom Filters**: User-defined filters for source types
6. **Incremental Updates**: Track and refresh outdated sources

## Related Documentation

- [Knowledge Packs Design](design/knowledge-packs.md)
- [Pack Creation CLI](../README.md#knowledge-packs)
- [Evaluation Framework](design/evaluation-framework.md)
