# Seed Agent

The **SeedAgent** generates Wikipedia seed articles from user-provided topics using Claude. It powers the `wikigr create` CLI command that builds custom knowledge graphs end-to-end.

## How It Works

1. **Topic -> Claude**: For each topic, Claude suggests ~15 real Wikipedia article titles
2. **Wikipedia validation**: Titles are batch-validated against the Wikipedia Query API (50 per request). Invalid titles are dropped; redirects resolve to canonical names.
3. **Seed JSON**: Validated seeds are output in the same format as `bootstrap/data/seeds_1k.json`, ready for the expansion pipeline.

## Usage

### Python API

```python
from wikigr.agent import SeedAgent

agent = SeedAgent(seeds_per_topic=10)

# Per-topic (one seed set each)
by_topic = agent.generate_seeds_by_topic(["Quantum Computing", "Marine Biology"])
print(by_topic["Quantum Computing"]["metadata"]["total_seeds"])

# Combined (all topics merged, deduplicated)
combined = agent.generate_seeds(["Quantum Computing", "Marine Biology"])
```

### CLI

```bash
# Build one knowledge graph per topic
wikigr create --topics topics.md --db data/ --target 500

# Just generate and inspect seeds
wikigr create --topics topics.md --seeds-only

# Save seeds for later reuse
wikigr create --topics topics.md --seeds-output seeds/ --seeds-only

# Build from pre-generated seeds (single DB)
wikigr create --seeds seeds/quantum-computing.json --db data/quantum.db --target 1000
```

### Topics File Format

Plain text (one per line), markdown bullets, or numbered lists all work:

```markdown
- Quantum Computing
- Renaissance Art
- Marine Biology
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--seeds-per-topic` | 10 | Target validated seeds per topic |
| `--target` | 1000 | Articles per knowledge graph |
| `--max-depth` | 2 | Link expansion hops from seeds |
| `--batch-size` | 10 | Articles per expansion batch |
| `--db` | `data/` | Output directory (topics) or file (seeds) |

## Environment Variables

- `ANTHROPIC_API_KEY`: Required for seed generation (Claude API)

## Architecture

```
topics.md
    |
    v
SeedAgent._generate_titles_for_topic()   [Claude Haiku]
    |
    v
SeedAgent._validate_titles()             [Wikipedia Query API]
    |
    v
seeds JSON (per topic)
    |
    v
create_schema() + RyuGraphOrchestrator   [Kuzu + sentence-transformers]
    |
    v
<topic>.db                               [One knowledge graph per topic]
```

## Key Files

- `wikigr/agent/seed_agent.py` - SeedAgent class
- `wikigr/cli.py` - CLI entry point (`wikigr create`)
- `tests/agent/test_seed_agent.py` - Unit tests (17 tests)
