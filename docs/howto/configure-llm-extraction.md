# How to Configure LLM Extraction for Web Sources

Configure entity and relationship extraction parameters for optimal results.

## Problem

You want to control how entities and relationships are extracted from web content, adjusting model selection, temperature, or output format.

## Solution

Use environment variables and command-line flags to configure LLM extraction behavior.

## Configure OpenAI Model

Set the model used for extraction:

```bash
export OPENAI_MODEL=gpt-4-turbo-preview
wikigr create --source=web --url="https://example.com/article"
```

**Available models:**
- `gpt-4-turbo-preview` (default, best quality)
- `gpt-3.5-turbo` (faster, lower cost)
- `gpt-4` (highest quality, slower)

## Configure Extraction Temperature

Control randomness in entity extraction:

```bash
export LLM_TEMPERATURE=0.0
wikigr create --source=web --url="https://example.com/article"
```

**Temperature values:**
- `0.0` - Deterministic, consistent extraction (recommended)
- `0.3` - Slight variation, creative edge cases
- `0.7` - More diverse entities, less consistent

## Configure Max Entities Per Article

Limit entities extracted from each page:

```bash
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/intro-kubernetes" \
  --max-entities=50
```

**When to adjust:**
- Long articles: Increase to 100+ to capture all concepts
- Short articles: Decrease to 20-30 for focused extraction
- Default: 50 entities per article

## Configure Relationship Extraction

Enable or disable relationship extraction:

```bash
# Extract only entities (faster)
wikigr create \
  --source=web \
  --url="https://example.com/article" \
  --no-relationships

# Extract entities and relationships (default)
wikigr create \
  --source=web \
  --url="https://example.com/article" \
  --relationships
```

**Trade-offs:**
- Without relationships: 2x faster, nodes-only graph
- With relationships: Richer semantic graph, higher cost

## Configure Extraction Retries

Set retry behavior for failed LLM calls:

```bash
export LLM_MAX_RETRIES=3
export LLM_RETRY_DELAY=2.0
wikigr create --source=web --url="https://example.com/article"
```

**Variables:**
- `LLM_MAX_RETRIES` - Number of retry attempts (default: 3)
- `LLM_RETRY_DELAY` - Seconds between retries (default: 1.0)

## Example: High-Quality Extraction for Important Content

```bash
export OPENAI_MODEL=gpt-4
export LLM_TEMPERATURE=0.0
export LLM_MAX_RETRIES=5

wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/architecture/best-practices/api-design" \
  --max-entities=100 \
  --relationships \
  --db-path=api_design_high_quality.db
```

**Output:**
```
Processing 1 article from web...
Using model: gpt-4, temperature: 0.0
Extracted 87 entities, 64 relationships
Knowledge graph created: api_design_high_quality.db
```

## Example: Fast Extraction for Large Crawls

```bash
export OPENAI_MODEL=gpt-3.5-turbo
export LLM_TEMPERATURE=0.0

wikigr create \
  --source=web \
  --url="https://docs.python.org/3/library/" \
  --max-depth=2 \
  --max-links=50 \
  --max-entities=30 \
  --no-relationships \
  --db-path=python_docs_fast.db
```

**Output:**
```
Processing 50 articles from web...
Using model: gpt-3.5-turbo, temperature: 0.0
Extracted 1,234 entities across 50 pages (avg 25 per page)
Knowledge graph created: python_docs_fast.db
```

## Troubleshooting

### Extraction Taking Too Long

**Problem:** LLM calls are slow for large pages.

**Solution:** Reduce `max-entities` or use `gpt-3.5-turbo`:
```bash
export OPENAI_MODEL=gpt-3.5-turbo
wikigr create --source=web --url="..." --max-entities=30
```

### Inconsistent Entity Names

**Problem:** Same entity extracted with different names.

**Solution:** Use temperature 0.0 for deterministic extraction:
```bash
export LLM_TEMPERATURE=0.0
```

### Rate Limit Errors

**Problem:** OpenAI API rate limits exceeded.

**Solution:** Increase retry delay and reduce concurrency:
```bash
export LLM_RETRY_DELAY=5.0
export LLM_MAX_RETRIES=5
```

## Related Documentation

- [Getting Started with Web Sources](../tutorials/web-sources-getting-started.md)
- [ArticleProcessor API Reference](../reference/article-processor.md)
- [Understanding LLM Extraction](../concepts/llm-extraction.md)
