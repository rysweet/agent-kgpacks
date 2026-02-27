# Improving .NET Pack Content Quality

Guide to auditing and improving knowledge pack content quality, with a focus on the .NET Expert pack.

## Problem

The .NET pack had only 60% accuracy vs 100% for physics. Two causes:
1. **Thin content**: Microsoft Learn pages are JS-heavy; scraped articles often have < 200 words
2. **Hallucinated URLs**: 13/244 URLs in the original manifest were fabricated by the LLM

## Audit Content Quality

Use the `audit_pack_content.py` script to compare packs:

```bash
# Audit the .NET pack
python scripts/audit_pack_content.py --pack dotnet-expert

# Compare .NET vs physics
python scripts/audit_pack_content.py --pack dotnet-expert --compare physics-expert
```

Output shows:
- Min/max/avg/median word count per article
- Articles with < 200 words ("thin content")
- Comparison with reference pack

## Content Quality Threshold

The `WebContentSource` now skips articles with fewer than 200 words by default:

```python
from wikigr.packs.web_source import WebContentSource

source = WebContentSource(
    min_content_words=200,  # skip thin content (default)
)
```

To lower the threshold for sparse domains:

```python
source = WebContentSource(
    min_content_words=100,  # allow shorter articles for API reference docs
)
```

To disable the threshold:

```python
source = WebContentSource(
    min_content_words=0,  # no minimum
)
```

## Validate and Fix Pack URLs

Before building a pack, validate all URLs to remove hallucinated or broken ones:

```bash
# Check URLs (dry run)
python scripts/validate_pack_urls.py --pack dotnet-expert

# Auto-fix: remove invalid URLs
python scripts/validate_pack_urls.py --pack dotnet-expert --fix

# Validate all packs
python scripts/validate_pack_urls.py --all --fix
```

The validator:
- Returns HTTP 404 → marks as invalid
- Returns HTTP 429 (rate limited) → marks as valid (don't remove)
- Returns redirect → follows and checks final URL

## Rebuild After Improvements

After fixing URLs and enabling the content threshold:

```bash
# Rebuild .NET pack with quality threshold
python scripts/build_dotnet_pack.py --min-content-words 200
```

## Expected Impact

Content quality improvements typically yield +5-15% accuracy:

| Issue | Before | After |
|-------|--------|-------|
| Thin articles (<200 words) | ~40% of articles | <5% |
| Hallucinated URLs | 13 invalid | 0 invalid |
| Expected accuracy | 60% | ~70-75% |

## See Also

- [Generating Evaluation Questions](generating-evaluation-questions.md) — measure accuracy after rebuild
- [Vector Search Retrieval](vector-search-primary-retrieval.md) — retrieval improvements
- [LLM Seed Researcher](../llm-seed-researcher.md) — automated URL discovery
