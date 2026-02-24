# How to Filter Links During Web Crawling

Control which links are followed during BFS crawling to focus on relevant content.

## Problem

You want to crawl a website but only follow certain links (same domain, specific paths, exclude patterns).

## Solution

Use link filtering options to control BFS crawling behavior.

## Filter by Domain

Only follow links within the same domain:

```bash
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks" \
  --max-depth=2 \
  --same-domain-only \
  --db-path=azure_aks.db
```

**What happens:**
- Starting URL: `learn.microsoft.com`
- Follows: `https://learn.microsoft.com/en-us/azure/aks/concepts-clusters-workloads`
- Skips: `https://github.com/Azure/AKS` (different domain)

## Filter by URL Pattern

Include only URLs matching a pattern:

```bash
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks" \
  --max-depth=3 \
  --include-pattern="/azure/aks/" \
  --db-path=aks_only.db
```

**What happens:**
- Follows: `https://learn.microsoft.com/en-us/azure/aks/tutorial-kubernetes-deploy-cluster`
- Skips: `https://learn.microsoft.com/en-us/azure/vm/...` (doesn't match pattern)

## Exclude URL Patterns

Skip URLs matching exclusion patterns:

```bash
wikigr create \
  --source=web \
  --url="https://docs.python.org/3/library/" \
  --max-depth=2 \
  --exclude-pattern="^.*/genindex\\.html$" \
  --exclude-pattern="^.*/py-modindex\\.html$" \
  --db-path=python_docs.db
```

**What happens:**
- Follows: `https://docs.python.org/3/library/os.html`
- Skips: `https://docs.python.org/3/genindex.html` (matches exclusion)

## Combine Multiple Filters

Use multiple filters together:

```bash
wikigr create \
  --source=web \
  --url="https://kubernetes.io/docs/concepts/overview/" \
  --max-depth=2 \
  --max-links=20 \
  --same-domain-only \
  --include-pattern="/docs/concepts/" \
  --exclude-pattern="/docs/concepts/workloads/controllers/" \
  --db-path=k8s_concepts.db
```

**Filter logic:**
1. Must be same domain (`kubernetes.io`)
2. Must match include pattern (`/docs/concepts/`)
3. Must NOT match exclude pattern (`/docs/concepts/workloads/controllers/`)
4. Stop after 20 pages

## Example: Crawl Azure Documentation for AKS

```bash
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/" \
  --max-depth=2 \
  --max-links=50 \
  --same-domain-only \
  --include-pattern="/azure/aks/" \
  --exclude-pattern="/azure/aks/api-reference/" \
  --db-path=azure_aks_focused.db
```

**Output:**
```
Processing 1 article from web...
Expanding links: depth 1, found 28 URLs (12 after filtering)
Expanding links: depth 2, found 64 URLs (37 after filtering, limiting to 50 total)
Filtered out: 15 different domain, 8 excluded pattern
Extracted 1,456 entities, 892 relationships across 50 pages
Knowledge graph created: azure_aks_focused.db
```

## Example: Crawl GitHub Wiki with URL Filtering

```bash
wikigr create \
  --source=web \
  --url="https://github.com/microsoft/WSL/wiki" \
  --max-depth=1 \
  --same-domain-only \
  --include-pattern="/microsoft/WSL/wiki/" \
  --db-path=wsl_wiki.db
```

**Output:**
```
Processing 1 article from web...
Expanding links: depth 1, found 42 URLs (42 after filtering)
All links within github.com/microsoft/WSL/wiki/
Extracted 783 entities, 521 relationships across 43 pages
Knowledge graph created: wsl_wiki.db
```

## Depth vs Breadth Control

Understand how `max-depth` and `max-links` interact:

```bash
# Deep but narrow: follow links far but limit total count
wikigr create \
  --source=web \
  --url="https://example.com/root" \
  --max-depth=5 \
  --max-links=25

# Shallow but wide: follow many links but stay close to root
wikigr create \
  --source=web \
  --url="https://example.com/root" \
  --max-depth=1 \
  --max-links=100
```

**Depth 5, max 25 links:**
- Explores deep hierarchies
- Finds highly specific content
- Fewer pages overall

**Depth 1, max 100 links:**
- Stays close to root
- Covers broad topics
- More pages at same level

## Link Filtering Algorithm

The BFS crawler applies filters in this order:

1. **Parse URL** - Extract domain, path, query
2. **Check visited** - Skip if already processed
3. **Same domain** - Skip if `--same-domain-only` and domain differs
4. **Include pattern** - Skip if `--include-pattern` provided and doesn't match
5. **Exclude pattern** - Skip if `--exclude-pattern` provided and matches
6. **Max links** - Stop if total pages exceeds `--max-links`
7. **Add to queue** - Process at next depth level

## Troubleshooting

### Too Many Irrelevant Pages

**Problem:** Crawler follows links to off-topic pages.

**Solution:** Add more restrictive include patterns:
```bash
--include-pattern="/docs/guide/"
```

### Missing Important Pages

**Problem:** Crawler skips pages you want to include.

**Solution:** Check if exclude patterns are too broad:
```bash
# Too broad - excludes everything under /api/
--exclude-pattern="/api/"

# More specific - excludes only /api/internal/
--exclude-pattern="/api/internal/"
```

### Crawl Never Finishes

**Problem:** Too many links discovered.

**Solution:** Reduce depth or add stricter filters:
```bash
wikigr create \
  --source=web \
  --url="..." \
  --max-depth=1 \
  --max-links=20 \
  --same-domain-only
```

## Related Documentation

- [Getting Started with Web Sources](../tutorials/web-sources-getting-started.md)
- [Web Content Source API Reference](../reference/web-content-source.md)
- [Understanding BFS Link Expansion](../concepts/bfs-link-expansion.md)
