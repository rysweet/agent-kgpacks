# Pack Manifest Reference

Complete specification for the `manifest.json` file included in every Knowledge Pack.

## File Location

```
data/packs/<pack-name>/manifest.json
```

## Format

JSON object with the following structure:

```json
{
  "name": "go-expert",
  "version": "1.0.0",
  "description": "Expert Go programming knowledge covering Go 1.22+ features including generics, range-over-func iterators, structured logging with slog, error handling patterns, concurrency with goroutines and channels, modules, and testing",
  "graph_stats": {
    "articles": 16,
    "entities": 106,
    "relationships": 69,
    "size_mb": 2.08
  },
  "eval_scores": {
    "accuracy": 0.0,
    "hallucination_rate": 0.0,
    "citation_quality": 0.0
  },
  "source_urls": [
    "https://go.dev/doc/",
    "https://gobyexample.com/",
    "https://go.dev/blog/"
  ],
  "created": "2026-03-01T16:40:06.813001Z",
  "license": "MIT"
}
```

## Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Pack identifier. Must match the directory name. Lowercase alphanumeric with hyphens (e.g., `go-expert`, `react-expert`) |
| `version` | string | Semantic version (e.g., `1.0.0`). Follows [SemVer](https://semver.org/) |
| `description` | string | Human-readable description of the pack's domain coverage |
| `graph_stats` | object | Statistics about the knowledge graph (see below) |
| `created` | string | ISO 8601 timestamp of when the pack was built |
| `license` | string | License identifier (e.g., `MIT`, `Apache-2.0`) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `author` | string | Pack author name or organization |
| `topics` | list[string] | List of topic areas covered by the pack |
| `eval_scores` | object | Evaluation results (see below) |
| `source_urls` | list[string] | Representative source URLs used to build the pack |
| `created_at` | string | Alternative name for `created` (backwards compatibility) |

### graph_stats Object

| Field | Type | Description |
|-------|------|-------------|
| `articles` | integer | Number of articles (documents) in the knowledge graph |
| `entities` | integer | Number of named entities extracted by LLM |
| `relationships` | integer | Number of relationships between entities |
| `size_mb` | float | Database size on disk in megabytes |

### eval_scores Object

| Field | Type | Description |
|-------|------|-------------|
| `accuracy` | float | Proportion of questions scored >= 7/10 (0.0 to 1.0) |
| `hallucination_rate` | float | Proportion of answers with fabricated information (0.0 to 1.0) |
| `citation_quality` | float | Proportion of answers with correct source citations (0.0 to 1.0) |

!!! note "Initial values"
    A freshly built pack has `eval_scores` set to all zeros. Run evaluation to populate these values.

## Validation Rules

The `wikigr pack validate` command checks:

| Rule | Description |
|------|-------------|
| `name` is non-empty | Pack must have a name |
| `version` is valid SemVer | Must match `X.Y.Z` pattern |
| `graph_stats.articles` >= 0 | Must be a non-negative integer |
| `graph_stats.size_mb` >= 0 | Must be a non-negative number |
| `created` is valid ISO 8601 | Must be a parseable timestamp |
| `license` is non-empty | Pack must specify a license |

## Example Manifests

### Minimal Manifest

```json
{
  "name": "my-pack",
  "version": "1.0.0",
  "description": "My domain knowledge pack",
  "graph_stats": {
    "articles": 25,
    "entities": 150,
    "relationships": 80,
    "size_mb": 3.5
  },
  "created": "2026-03-01T00:00:00Z",
  "license": "MIT"
}
```

### Full Manifest

```json
{
  "name": "langchain-expert",
  "version": "2.0.0",
  "description": "LangChain framework expertise covering agents, chains, retrievers, prompts, embeddings, vector stores, and LCEL expression language",
  "author": "agent-kgpacks",
  "topics": [
    "LangChain",
    "LCEL",
    "Agents",
    "Retrieval",
    "Vector Stores"
  ],
  "graph_stats": {
    "articles": 71,
    "entities": 485,
    "relationships": 312,
    "size_mb": 15.2
  },
  "eval_scores": {
    "accuracy": 0.90,
    "hallucination_rate": 0.05,
    "citation_quality": 0.85
  },
  "source_urls": [
    "https://python.langchain.com/docs/concepts/",
    "https://python.langchain.com/docs/how_to/",
    "https://python.langchain.com/docs/tutorials/"
  ],
  "created": "2026-03-01T12:00:00Z",
  "license": "MIT"
}
```

## Pack Directory Structure

The manifest sits alongside these files in the pack directory:

```
data/packs/<pack-name>/
├── manifest.json         # This file
├── pack.db/              # Kuzu graph database directory
├── urls.txt              # Source URLs used to build the pack
├── skill.md              # Claude Code skill description
├── kg_config.json        # KG Agent configuration overrides
├── few_shot_examples.json # (optional) Curated few-shot examples
└── eval/
    ├── questions.jsonl    # Evaluation questions with ground truth
    └── results/           # Evaluation output files
```

## Updating the Manifest

After rebuilding a pack or running evaluation, update the manifest:

```bash
# After rebuild: update graph_stats
python -c "
import json, os
manifest_path = 'data/packs/my-pack/manifest.json'
manifest = json.load(open(manifest_path))
# Update stats from the new database
manifest['graph_stats']['articles'] = 45  # new count
manifest['created'] = '2026-03-01T12:00:00Z'
json.dump(manifest, open(manifest_path, 'w'), indent=2)
"

# Validate the updated manifest
wikigr pack validate data/packs/my-pack
```

## Version History

| Version | Changes |
|---------|---------|
| Current | `eval_scores` and `source_urls` are optional; `author` and `topics` fields added |
| Original | All fields required; no `author` or `topics` |

The manifest reader supports both `created` and `created_at` field names for backwards compatibility.
