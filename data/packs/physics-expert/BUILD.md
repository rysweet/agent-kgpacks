# Building the Physics Expert Pack

This document describes how to build the Physics Expert Knowledge Pack from the topics.txt source file.

## Overview

The physics expert pack contains ~500 Wikipedia articles covering fundamental and advanced physics topics. Building the pack involves:

1. Downloading Wikipedia articles for each topic
2. Extracting entities, relationships, and facts using Claude (LLM)
3. Generating embeddings for semantic search
4. Building a Kuzu knowledge graph database

## Prerequisites

- Python 3.10+
- Anthropic API key (set in `ANTHROPIC_API_KEY` environment variable)
- ~15 GB disk space for the full pack
- 10-15 hours runtime for full pack (or 1-2 minutes for test pack)

## Quick Start

### Build Test Pack (10 articles)

For development and testing, build a small 10-article pack:

```bash
python scripts/build_physics_pack.py --test-mode
```

This creates:
- `data/packs/physics-expert/pack.db` (~50 MB)
- `data/packs/physics-expert/manifest.json`

Runtime: 1-2 minutes
Cost: ~$0.50

### Build Full Pack (500 articles)

For production use, build the complete pack:

```bash
# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Run builder (this will take 10-15 hours)
python scripts/build_physics_pack.py
```

This creates:
- `data/packs/physics-expert/pack.db` (~1.2 GB)
- `data/packs/physics-expert/manifest.json`

Runtime: 10-15 hours
Estimated cost: $15-30 (Claude Haiku API)

## Build Process

The script (`scripts/build_physics_pack.py`) performs these steps:

1. **Load Topics**: Read topics from `topics.txt`
2. **Initialize Database**: Create Kuzu database with schema
3. **Process Each Article**:
   - Fetch from Wikipedia API
   - Parse sections
   - Extract knowledge using Claude:
     - Entities (people, concepts, quantities)
     - Relationships between entities
     - Key facts
   - Generate embeddings for semantic search
   - Store in knowledge graph
4. **Create Manifest**: Generate `manifest.json` with pack metadata

## Monitoring Progress

The script logs progress to both console and `logs/build_physics_pack.log`:

```
2024-01-15 10:23:45 - INFO - Processing 1/500: Classical mechanics
2024-01-15 10:24:12 - INFO - Processed Classical mechanics
2024-01-15 10:24:13 - INFO - Processing 2/500: Quantum mechanics
...
```

## Resuming After Interruption

The script checks for existing articles before processing, so you can safely interrupt and resume:

1. Press Ctrl+C to stop
2. Re-run the same command
3. Already-processed articles will be skipped

## Verification

After building, verify the pack:

```bash
# Check database size
ls -lh data/packs/physics-expert/pack.db

# Check manifest
cat data/packs/physics-expert/manifest.json

# Run validation tests
pytest tests/packs/test_pack_structure.py::test_physics_expert_pack_structure -v
```

## Troubleshooting

### "No module named 'anthropic'"

Install dependencies:
```bash
pip install -e .
```

### "ANTHROPIC_API_KEY not set"

Set your API key:
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Database already exists

The script will prompt you to delete and rebuild. Alternatively:
```bash
rm data/packs/physics-expert/pack.db
```

### Rate limiting errors

The script includes retry logic, but if you hit rate limits:
1. Wait a few minutes
2. Resume with the same command
3. Already-processed articles will be skipped

## Cost Estimation

- **Test pack (10 articles)**: ~$0.50
- **Full pack (500 articles)**: ~$15-30

Costs are based on Claude Haiku pricing (~$0.25/1M input tokens, ~$1.25/1M output tokens).

## Next Steps

After building the pack:

1. **Run Evaluation**: Test pack quality with `wikigr/packs/eval/runner.py`
2. **Package**: Create tarball for distribution
3. **Install**: Use pack manager to install in WikiGR

See [README.md](README.md) for more details.
