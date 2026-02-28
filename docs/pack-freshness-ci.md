# Pack Freshness CI

Automated system for detecting stale knowledge packs and rebuilding them when
source URLs change.

## How It Works

The pipeline has four stages:

```
1. Check Freshness   -->  2. Rebuild Changed  -->  3. Quick Eval  -->  4. Create PR
   (HEAD requests)        (build scripts)          (5 questions)       (manifest + cache)
```

### Stage 1: Check URL Freshness

For every pack with a `urls.txt`, the system sends HTTP HEAD requests and
compares `ETag` and `Last-Modified` headers against values stored in
`.freshness_cache.json`. If the headers differ from the cached values, the URL
is marked as changed.

When more than 20% of a pack's URLs have changed, the pack is flagged for
rebuild.

### Stage 2: Rebuild

Each flagged pack is rebuilt in parallel using its existing
`scripts/build_{pack}_pack.py --test-mode` script. The matrix strategy means
multiple packs rebuild concurrently.

### Stage 3: Quick Eval

A 5-question sanity eval runs against each rebuilt pack using the existing eval
framework (`wikigr.packs.eval.runner`). This catches regressions before the PR
is created.

### Stage 4: PR Creation

Updated `.freshness_cache.json` and `manifest.json` files are committed to an
auto-generated branch and a PR is created with a freshness report table.

## Schedule

- **Automatic**: Runs every Monday at 06:00 UTC via cron
- **Manual**: Trigger via GitHub UI or CLI

## Manual Trigger

Check a single pack:

```bash
gh workflow run pack-freshness.yml -f pack=kubernetes-networking
```

Check all packs without rebuilding:

```bash
gh workflow run pack-freshness.yml -f skip_rebuild=true
```

Use content hashing for more accuracy (slower):

```bash
gh workflow run pack-freshness.yml -f content_hash=true -f pack=rust-expert
```

Custom change threshold:

```bash
gh workflow run pack-freshness.yml -f threshold=0.10
```

## Local Usage

The freshness script works standalone:

```bash
# Check a single pack
python scripts/check_pack_freshness.py data/packs/kubernetes-networking

# Check all packs
python scripts/check_pack_freshness.py --all

# JSON output for scripting
python scripts/check_pack_freshness.py --all --json

# Content hashing (downloads full pages)
python scripts/check_pack_freshness.py data/packs/rust-expert --content-hash

# Custom threshold (10% instead of default 20%)
python scripts/check_pack_freshness.py --all --threshold 0.10
```

Exit codes:
- `0`: No packs need rebuilding
- `1`: At least one pack needs rebuilding

## Freshness Cache

Each pack stores header metadata in `data/packs/{name}/.freshness_cache.json`:

```json
{
  "https://kubernetes.io/docs/concepts/services-networking/service/": {
    "etag": "\"abc123\"",
    "last_modified": "Mon, 15 Jan 2026 10:00:00 GMT",
    "checked_at": "2026-02-28T06:00:00Z"
  }
}
```

This file is committed to the repo so the cache persists across CI runs (GitHub
Actions has no persistent state beyond git).

The first run for a pack always reports zero changes since there is nothing to
compare against. Subsequent runs detect drift.

## Rate Limiting

The checker handles rate limiting:

- 429 responses trigger exponential backoff (1s, 2s, 4s)
- After max retries, rate-limited URLs are assumed unchanged (not a false positive)
- Default concurrency is 8 workers per pack

## Threshold Tuning

The `--threshold` parameter controls what ratio of changed URLs triggers a
rebuild. Default is 0.20 (20%).

- **0.10**: Aggressive -- rebuilds on 10% change. Good for fast-moving domains
- **0.20**: Balanced -- the default
- **0.50**: Conservative -- only rebuilds when half the URLs changed

## Required Secrets

The workflow requires these repository secrets:

- `ANTHROPIC_API_KEY`: For LLM-based pack building and evaluation

## File Layout

```
scripts/check_pack_freshness.py          # Freshness checker CLI
.github/workflows/pack-freshness.yml     # GitHub Actions workflow
data/packs/{name}/.freshness_cache.json  # Per-pack header cache (committed)
docs/pack-freshness-ci.md               # This file
```
