# WikiGR Pack CLI Commands

Complete reference for the `wikigr pack` command suite for managing knowledge packs.

## Overview

The `wikigr pack` command provides 8 subcommands for the complete lifecycle of knowledge packs:

| Command   | Purpose                                    |
|-----------|--------------------------------------------|
| `create`  | Build a new knowledge pack from topics    |
| `install` | Install a pack from local file or URL     |
| `list`    | List all installed packs                  |
| `info`    | Show detailed information about a pack    |
| `eval`    | Evaluate pack quality with 3-baseline test|
| `update`  | Update a pack to a new version            |
| `remove`  | Uninstall a pack                          |
| `validate`| Validate pack structure and manifest      |

## 1. wikigr pack create

Create a new knowledge pack from topics.

### Usage

```bash
wikigr pack create \
  --name <pack-name> \
  --source <wikipedia|web> \
  --topics <topics-file> \
  --target <article-count> \
  [--eval-questions <questions-file>] \
  --output <output-directory>
```

### Options

- `--name` (required): Pack name (e.g., "physics-expert")
- `--source` (optional): Content source, defaults to "wikipedia"
  - `wikipedia`: Use Wikipedia as source
  - `web`: Use generic web URLs (requires --urls)
- `--topics` (required): Path to topics file (markdown or text, one topic per line)
- `--target` (optional): Target article count, defaults to 1000
- `--eval-questions` (optional): Path to evaluation questions JSONL file
- `--output` (required): Output directory for the pack

### Example

```bash
# Create topics file
cat > topics.txt << EOF
Physics
Quantum Mechanics
Thermodynamics
EOF

# Create evaluation questions
cat > eval.jsonl << EOF
{"question": "What is quantum mechanics?", "ground_truth": "Branch of physics"}
{"question": "Define entropy", "ground_truth": "Measure of disorder"}
EOF

# Create pack
wikigr pack create \
  --name physics-expert \
  --source wikipedia \
  --topics topics.txt \
  --target 5000 \
  --eval-questions eval.jsonl \
  --output ./packs
```

### Output Structure

```
output/
└── pack-name/
    ├── manifest.json        # Pack metadata and stats
    ├── pack.db/            # Kuzu knowledge graph database
    ├── skill.md            # Claude Code skill file
    ├── kg_config.json      # KG Agent configuration
    └── eval_questions.jsonl # Evaluation questions (if provided)
```

## 2. wikigr pack install

Install a knowledge pack from a local archive or URL.

### Usage

```bash
# From local file
wikigr pack install <path-to-archive.tar.gz>

# From URL
wikigr pack install https://example.com/packs/physics-expert-v1.0.0.tar.gz
```

### Example

```bash
# Install from local file
wikigr pack install physics-expert.tar.gz

# Install from URL
wikigr pack install https://wikigr.io/packs/physics-expert-v1.0.0.tar.gz
```

### Installation Location

Packs are installed to `~/.wikigr/packs/<pack-name>/`

## 3. wikigr pack list

List all installed knowledge packs.

### Usage

```bash
wikigr pack list [--format <text|json>]
```

### Options

- `--format` (optional): Output format, defaults to "text"
  - `text`: Human-readable table format
  - `json`: JSON array of pack metadata

### Example

```bash
# List in text format
wikigr pack list

# Output:
# Installed knowledge packs (2):
#
#   physics-expert              v1.0.0     Expert knowledge in physics
#   chemistry-basics            v2.1.0     Fundamental chemistry concepts

# List in JSON format
wikigr pack list --format json

# Output:
# [
#   {
#     "name": "physics-expert",
#     "version": "1.0.0",
#     "description": "Expert knowledge in physics",
#     "topics": ["Physics", "Quantum Mechanics"],
#     "path": "/home/user/.wikigr/packs/physics-expert"
#   }
# ]
```

## 4. wikigr pack info

Show detailed information about an installed pack.

### Usage

```bash
wikigr pack info <pack-name> [--show-eval-scores]
```

### Options

- `--show-eval-scores` (optional): Include evaluation scores if available

### Example

```bash
wikigr pack info physics-expert

# Output:
# Pack: physics-expert
# Version: 1.0.0
# Description: Expert knowledge in physics
# Author: John Doe
# License: MIT
# Created: 2026-01-15T10:30:00Z
# Topics: Physics, Quantum Mechanics, Thermodynamics
# Path: /home/user/.wikigr/packs/physics-expert
#
# Graph Statistics:
#   Articles: 5000
#   Entities: 12500
#   Relationships: 8900
#   Size: 45 MB

# Show with evaluation scores
wikigr pack info physics-expert --show-eval-scores

# Additional output:
# Evaluation Scores:
#   Accuracy: 0.92
#   Hallucination Rate: 0.08
#   Citation Quality: 0.85
#
#   Surpasses Training: True
#   Surpasses Web: True
```

## 5. wikigr pack eval

Evaluate pack quality using three-baseline comparison.

### Usage

```bash
wikigr pack eval <pack-name> \
  [--questions <custom-questions.jsonl>] \
  [--save-results]
```

### Options

- `--questions` (optional): Path to custom evaluation questions (JSONL format)
  - If not provided, uses `eval_questions.jsonl` from pack directory
- `--save-results` (optional): Save evaluation results to pack directory

### Evaluation Process

The evaluation runs three baselines:

1. **Training Baseline**: Claude without any tools (pure training data)
2. **Web Search Baseline**: Claude with web search capability
3. **Knowledge Pack Baseline**: Claude with pack retrieval

For each baseline, the system measures:

- **Accuracy**: Semantic similarity to ground truth answers
- **Hallucination Rate**: Detection of fabricated or unsupported claims
- **Citation Quality**: Validation of citations and sources

### Example

```bash
# Evaluate using pack's default questions
wikigr pack eval physics-expert --save-results

# Output:
# Loading evaluation questions...
# Loaded 50 questions
#
# Running three-baseline evaluation...
# Running training baseline...
# Running web search baseline...
# Running knowledge pack baseline...
#
# ============================================================
# EVALUATION RESULTS
# ============================================================
#
# Knowledge Pack: physics-expert
# Questions Tested: 50
#
# --- Knowledge Pack Metrics ---
#   Accuracy: 0.92
#   Hallucination Rate: 0.08
#   Citation Quality: 0.85
#
# --- Training Baseline Metrics ---
#   Accuracy: 0.78
#   Hallucination Rate: 0.22
#   Citation Quality: 0.60
#
# --- Web Search Baseline Metrics ---
#   Accuracy: 0.85
#   Hallucination Rate: 0.15
#   Citation Quality: 0.75
#
# --- Comparison ---
#   Surpasses Training: YES
#   Surpasses Web: YES
#
# Results saved to /home/user/.wikigr/packs/physics-expert/eval_results.json

# Use custom questions
wikigr pack eval physics-expert --questions my-questions.jsonl
```

### Question Format

Evaluation questions must be in JSONL format (one JSON object per line):

```jsonl
{"question": "What is quantum entanglement?", "ground_truth": "Phenomenon where particles remain connected"}
{"question": "Define absolute zero", "ground_truth": "Lowest possible temperature at -273.15°C"}
```

### Requirements

- Requires `ANTHROPIC_API_KEY` environment variable to be set
- Evaluation can take several minutes depending on question count

## 6. wikigr pack update

Update an installed pack to a new version.

### Usage

```bash
wikigr pack update <pack-name> --from <new-version-archive.tar.gz>
```

### Options

- `--from` (required): Path to new version archive

### Behavior

- Preserves evaluation results from the old version
- Validates version compatibility
- Replaces pack files with new version

### Example

```bash
# Update to new version
wikigr pack update physics-expert --from physics-expert-v1.1.0.tar.gz

# Output:
# Updating pack: physics-expert
# Current version: 1.0.0
# Successfully updated to version 1.1.0
```

## 7. wikigr pack remove

Remove an installed knowledge pack.

### Usage

```bash
wikigr pack remove <pack-name> [--force]
```

### Options

- `--force` (optional): Skip confirmation prompt

### Example

```bash
# Remove with confirmation
wikigr pack remove physics-expert
# Remove pack 'physics-expert'? (y/N): y
# Successfully removed pack: physics-expert

# Remove without confirmation
wikigr pack remove physics-expert --force
# Successfully removed pack: physics-expert
```

## 8. wikigr pack validate

Validate pack structure and manifest.

### Usage

```bash
wikigr pack validate <pack-directory> [--strict]
```

### Options

- `--strict` (optional): Enable strict validation mode
  - Requires optional files: README.md, eval_questions.jsonl

### Validation Checks

Standard mode checks:

- `manifest.json` exists and is valid JSON
- `pack.db/` exists (Kuzu database directory)
- `skill.md` exists
- `kg_config.json` exists and is valid JSON
- Manifest fields are valid (version format, timestamps, etc.)

Strict mode additionally requires:

- `README.md` documentation file
- `eval_questions.jsonl` evaluation questions

### Example

```bash
# Standard validation
wikigr pack validate ./my-pack
# Validating pack at ./my-pack...
# Pack is valid.

# Strict validation
wikigr pack validate ./my-pack --strict
# Validating pack at ./my-pack...
# Pack validation failed with 2 error(s):
#
#   - Strict mode: README.md is required but missing
#   - Strict mode: eval_questions.jsonl is required but missing

# Validation with errors
wikigr pack validate ./incomplete-pack
# Validating pack at ./incomplete-pack...
# Pack validation failed with 3 error(s):
#
#   - Required database missing: pack.db
#   - Required file missing: skill.md
#   - Invalid semantic version: v1.0
```

## Complete Workflow Example

See `wikigr/packs/examples/complete_pack_workflow.sh` for a complete demonstration script that uses all 8 commands in a realistic workflow.

### Quick Start

```bash
# 1. Create pack
wikigr pack create --name my-pack --topics topics.txt --target 1000 --output ./output

# 2. Validate
wikigr pack validate ./output/my-pack

# 3. Package and install
cd output
tar -czf my-pack.tar.gz my-pack
wikigr pack install my-pack.tar.gz

# 4. List and info
wikigr pack list
wikigr pack info my-pack

# 5. Evaluate (requires ANTHROPIC_API_KEY)
wikigr pack eval my-pack --save-results

# 6. Update (when new version available)
wikigr pack update my-pack --from my-pack-v1.1.0.tar.gz

# 7. Remove
wikigr pack remove my-pack --force
```

## Exit Codes

All pack commands use standard exit codes:

- `0`: Success
- `1`: Error (file not found, validation failed, etc.)

## Environment Variables

- `ANTHROPIC_API_KEY`: Required for `pack eval` command
- `HOME`: Used to determine pack installation directory (`~/.wikigr/packs`)

## Troubleshooting

### Pack not found after installation

Check that `~/.wikigr/packs/` directory exists and the pack directory is present:

```bash
ls -la ~/.wikigr/packs/
```

### Validation fails with manifest errors

Ensure manifest.json follows the required format:

```json
{
  "name": "pack-name",
  "version": "1.0.0",
  "description": "Pack description",
  "author": "Author name",
  "license": "MIT",
  "created_at": "2026-01-01T00:00:00Z",
  "topics": ["topic1", "topic2"],
  "graph_stats": {
    "articles": 1000,
    "entities": 2500,
    "relationships": 1800,
    "size_mb": 25
  }
}
```

### Evaluation requires API key

Set the ANTHROPIC_API_KEY environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
wikigr pack eval my-pack
```

## See Also

- [Knowledge Pack Design Document](../docs/knowledge_packs_design.md)
- [Pack Format Specification](../wikigr/packs/README.md)
- [Example Packs](../wikigr/packs/examples/)
