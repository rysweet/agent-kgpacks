# CI Pack Building

Automated pipeline for building and evaluating knowledge packs from GitHub
issues.

## How It Works

```
1. Maintainer creates issue    2. CI parses & validates    3. Build pack DB
   (using template)               (pack name, URLs)           (test-mode: 5 URLs)

4. Generate eval questions     5. Run eval (5-question)    6. Create PR
   (50 questions via Claude)      (training vs pack)          (urls.txt, manifest, eval, script)

7. Comment on issue with eval results and PR link
```

## Quick Start

1. Go to **Issues > New Issue** and pick the **Build Knowledge Pack** template.
2. Fill in the fields:
   - **Pack Name**: lowercase with hyphens, e.g. `aws-lambda-expert`
   - **Domain Description**: detailed description of the knowledge domain
   - **Seed URLs**: (optional) one URL per line
   - **Search Terms**: (optional) comma-separated terms for URL discovery
   - **Article Count Target**: 20, 50, or 100
3. Submit the issue. The `build-pack` label is applied automatically by the
   template.
4. CI runs and posts results as a comment on the issue.
5. A PR is created with all pack files (except the database, which is too large
   for git).

## Security

The workflow only runs when the issue author has `OWNER`, `MEMBER`, or
`COLLABORATOR` association with the repository. This prevents arbitrary users
from triggering builds that consume API credits.

Pack names are validated against `^[a-z0-9][a-z0-9-]*[a-z0-9]$` before being
used in any file path operations.

The workflow has a 30-minute timeout to prevent runaway builds.

## Required Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `ANTHROPIC_API_KEY` | Yes | LLM extraction and eval scoring |
| `HF_TOKEN` | No | Faster Hugging Face model downloads |

## What Gets Created

For a pack named `my-topic`:

```
data/packs/my-topic/
  urls.txt              # Source URLs
  manifest.json         # Pack metadata and graph stats
  pack.db/              # Kuzu database (NOT in git)
  eval/
    questions.json      # 50 eval questions (JSON array)
    questions.jsonl     # Same questions (JSONL format)

scripts/build_my_topic_pack.py   # Reproducible build script
```

The PR includes everything except `pack.db` (too large for git). To rebuild the
database locally:

```bash
uv run python scripts/build_my_topic_pack.py
```

Or in test mode (5 URLs only):

```bash
uv run python scripts/build_my_topic_pack.py --test-mode
```

## URL Discovery

If you provide **Seed URLs**, those are used directly.

If you provide **Search Terms** without URLs, the pipeline asks Claude to suggest
authoritative documentation URLs for the topic. This works well for established
technologies with official documentation sites.

For best results, provide seed URLs for niche topics and use search terms for
well-documented technologies.

## Eval Results

The eval compares two approaches on 5 sampled questions:

- **Training (baseline)**: Claude answers from training data alone
- **Pack (KG Agent)**: Claude answers using the knowledge graph

Scores are 0-10 per question, judged by Claude Haiku. The `delta` shows how much
the pack improves over baseline training knowledge.

A positive delta means the pack adds value beyond what Claude already knows.

## Manual Build

You can run the orchestrator script directly without CI:

```bash
uv run python scripts/build_pack_from_issue.py --issue-json '{
  "pack_name": "my-topic",
  "description": "Expert knowledge of ...",
  "urls": ["https://docs.example.com/guide"],
  "search_terms": "",
  "article_count_target": 20
}'
```

## Troubleshooting

### Build fails with "No URLs provided"

Either provide seed URLs in the issue or provide search terms so the pipeline can
discover URLs automatically.

### Build times out

The workflow has a 30-minute timeout. If your pack has many URLs, reduce the
article count target or provide fewer seed URLs. The build runs in test-mode
(5 URLs) in CI — full builds should be done locally.

### Pack already exists

If `data/packs/{name}/pack.db` already exists, the validation step rejects the
build. Delete the existing pack first or use a different name.

### Eval scores are low

Low scores (< 5.0) usually mean the source URLs don't contain enough relevant
content. Try adding more specific documentation URLs or adjusting the domain
description.
