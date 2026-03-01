# CLI Commands Reference

Complete reference for the `wikigr` command-line interface and pack management scripts.

## wikigr pack Commands

The `wikigr pack` subcommand provides 8 commands for pack lifecycle management.

### pack create

Build a new knowledge pack from topics.

```bash
wikigr pack create \
  --name <pack-name> \
  --source <wikipedia|web> \
  --topics <topics-file> \
  --target <article-count> \
  [--eval-questions <questions-file>] \
  --output <output-directory>
```

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--name` | Yes | - | Pack name (e.g., `physics-expert`) |
| `--source` | No | `wikipedia` | Content source (`wikipedia` or `web`) |
| `--topics` | Yes | - | Path to topics file (one topic per line) |
| `--target` | No | `1000` | Target article count |
| `--eval-questions` | No | - | Path to evaluation questions JSONL |
| `--output` | Yes | - | Output directory for the pack |

### pack install

Install a pack from a local archive or URL.

```bash
wikigr pack install <path-or-url>
```

Packs are installed to `~/.wikigr/packs/<pack-name>/`.

**Examples:**

```bash
wikigr pack install physics-expert.tar.gz
wikigr pack install https://example.com/packs/physics-expert-v1.0.0.tar.gz
```

### pack list

List all installed packs.

```bash
wikigr pack list [--format <text|json>]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `text` | Output format (`text` for table, `json` for machine-readable) |

### pack info

Show detailed information about an installed pack.

```bash
wikigr pack info <pack-name> [--show-eval-scores]
```

| Option | Description |
|--------|-------------|
| `--show-eval-scores` | Include evaluation scores if available |

### pack eval

Evaluate pack quality using three-baseline comparison.

```bash
wikigr pack eval <pack-name> \
  [--questions <custom-questions.jsonl>] \
  [--save-results]
```

| Option | Description |
|--------|-------------|
| `--questions` | Custom evaluation questions (default: pack's `eval_questions.jsonl`) |
| `--save-results` | Save results to pack directory |

Requires `ANTHROPIC_API_KEY` environment variable.

### pack update

Update an installed pack to a new version.

```bash
wikigr pack update <pack-name> --from <new-version.tar.gz>
```

Preserves evaluation results from the previous version.

### pack remove

Remove an installed pack.

```bash
wikigr pack remove <pack-name> [--force]
```

| Option | Description |
|--------|-------------|
| `--force` | Skip confirmation prompt |

### pack validate

Validate pack structure and manifest.

```bash
wikigr pack validate <pack-directory> [--strict]
```

| Option | Description |
|--------|-------------|
| `--strict` | Require optional files (README.md, eval_questions.jsonl) |

**Standard validation checks:**

- `manifest.json` exists and is valid JSON
- `pack.db/` directory exists
- `skill.md` exists
- `kg_config.json` exists and is valid JSON
- Manifest fields are valid (version format, timestamps)

## Evaluation Scripts

### eval_single_pack.py

Evaluate a single pack against the training baseline.

```bash
uv run python scripts/eval_single_pack.py <pack-name> [--sample N]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `pack-name` | Yes | Name of the pack under `data/packs/` |
| `--sample N` | No | Number of questions to evaluate (default: all) |

**Example:**

```bash
uv run python scripts/eval_single_pack.py go-expert --sample 10
```

### run_all_packs_evaluation.py

Evaluate all packs that have both `pack.db` and `eval/questions.jsonl`.

```bash
uv run python scripts/run_all_packs_evaluation.py [--sample N] [flags]
```

| Argument | Description |
|----------|-------------|
| `--sample N` | Questions per pack (default: all) |
| `--disable-reranker` | Disable GraphReranker for A/B testing |
| `--disable-multidoc` | Disable MultiDocSynthesizer |
| `--disable-fewshot` | Disable FewShotManager |

Results are saved to `data/packs/all_packs_evaluation.json`.

### generate_eval_questions.py

Generate evaluation questions for a pack using Claude Haiku.

```bash
python scripts/generate_eval_questions.py --pack <pack-name> [--count N] [--output <path>]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--pack` | (required) | Pack name |
| `--count` | 50 | Number of questions to generate |
| `--output` | auto | Output path (default: pack's `eval/questions.json`) |

### validate_pack_urls.py

Check that all URLs in a pack's `urls.txt` are reachable.

```bash
python scripts/validate_pack_urls.py <urls-file>
python scripts/validate_pack_urls.py --all  # Validate all packs
```

| Argument | Description |
|----------|-------------|
| `urls-file` | Positional path to a `urls.txt` file (e.g., `data/packs/go-expert/urls.txt`) |
| `--all` | Validate all packs in `data/packs/` |

## Build Scripts

Each pack has a dedicated build script in `scripts/`:

```bash
# Build a specific pack
echo "y" | uv run python scripts/build_go_pack.py [--test-mode]
echo "y" | uv run python scripts/build_react_expert_pack.py [--test-mode]
echo "y" | uv run python scripts/build_langchain_expert_pack.py [--test-mode]
```

| Flag | Description |
|------|-------------|
| `--test-mode` | Process only the first few URLs (fast, for testing) |

Available build scripts (48 packs):

```
scripts/build_go_pack.py
scripts/build_react_expert_pack.py
scripts/build_langchain_expert_pack.py
scripts/build_llamaindex_expert_pack.py
scripts/build_openai_api_expert_pack.py
scripts/build_vercel_ai_sdk_pack.py
scripts/build_zig_pack.py
scripts/build_bicep_infrastructure_pack.py
scripts/build_rust_pack.py
scripts/build_python_pack.py
scripts/build_typescript_pack.py
... (and 37 more)
```

## Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | All query and eval commands | Anthropic API key |
| `HOME` | `pack install`, `pack list` | Determines pack installation directory (`~/.wikigr/packs`) |

## Exit Codes

All commands use standard exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (file not found, validation failed, API error) |
