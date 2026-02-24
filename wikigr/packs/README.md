# Knowledge Packs - Phase 1: Pack Format & Manifest

This module implements the foundational pack format and manifest system for WikiGR Knowledge Packs.

## Overview

Knowledge Packs are reusable, distributable domain-specific knowledge graphs that can be installed and used as Claude Code skills. This Phase 1 implementation provides the core infrastructure for pack metadata and validation.

## Components

### 1. Pack Manifest (`manifest.py`)

**Data Models:**
- `GraphStats`: Statistics about the knowledge graph (articles, entities, relationships, size)
- `EvalScores`: Evaluation metrics (accuracy, hallucination rate, citation quality)
- `PackManifest`: Complete pack metadata and configuration

**Functions:**
- `load_manifest(pack_dir)`: Load manifest from pack directory
- `save_manifest(manifest, pack_dir)`: Save manifest to pack directory
- `validate_manifest(manifest)`: Validate manifest data and return errors

**Example:**
```python
from wikigr.packs import PackManifest, GraphStats, EvalScores, save_manifest
from pathlib import Path

# Create a manifest
manifest = PackManifest(
    name="physics-expert",
    version="1.0.0",
    description="Expert knowledge in quantum mechanics and relativity",
    graph_stats=GraphStats(
        articles=5240,
        entities=18500,
        relationships=42300,
        size_mb=420
    ),
    eval_scores=EvalScores(
        accuracy=0.94,
        hallucination_rate=0.04,
        citation_quality=0.98
    ),
    source_urls=["https://en.wikipedia.org/wiki/Portal:Physics"],
    created="2026-02-24T10:30:00Z",
    license="CC-BY-SA-4.0"
)

# Save to directory
save_manifest(manifest, Path("./physics-expert"))
```

### 2. Pack Validator (`validator.py`)

**Function:**
- `validate_pack_structure(pack_dir)`: Validate complete pack directory structure

**Validation Checks:**
- `manifest.json` exists and is valid
- `pack.db/` directory exists (Kuzu database)
- `skill.md` exists
- `kg_config.json` exists and is valid JSON
- Manifest content validation (semantic versioning, valid ranges, etc.)

**Example:**
```python
from wikigr.packs import validate_pack_structure
from pathlib import Path

errors = validate_pack_structure(Path("./physics-expert"))
if errors:
    print("Validation errors:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Pack structure is valid!")
```

## Pack Directory Structure

According to the design spec, a knowledge pack has the following structure:

```
physics-expert/
├── manifest.json          # Pack metadata (REQUIRED)
├── pack.db/               # Kuzu graph database directory (REQUIRED)
├── skill.md               # Claude Code skill interface (REQUIRED)
├── kg_config.json         # KG Agent configuration (REQUIRED)
├── eval/                  # Evaluation benchmarks (OPTIONAL)
│   └── questions.jsonl    # Test questions with ground truth
└── README.md              # Pack documentation (OPTIONAL)
```

### Required Files

1. **manifest.json**: Pack metadata including name, version, statistics, and evaluation scores
2. **pack.db/**: Kuzu database directory containing the knowledge graph
3. **skill.md**: Claude Code skill definition with frontmatter
4. **kg_config.json**: KG Agent retrieval configuration

### Optional Files

1. **README.md**: Human-readable pack documentation
2. **eval/**: Directory with evaluation benchmarks and questions

## Manifest Schema

The `manifest.json` file follows this schema:

```json
{
  "name": "physics-expert",
  "version": "1.2.0",
  "description": "Expert knowledge in quantum mechanics, relativity, and classical physics",
  "graph_stats": {
    "articles": 5240,
    "entities": 18500,
    "relationships": 42300,
    "size_mb": 420
  },
  "eval_scores": {
    "accuracy": 0.94,
    "hallucination_rate": 0.04,
    "citation_quality": 0.98
  },
  "source_urls": [
    "https://en.wikipedia.org/wiki/Portal:Physics",
    "https://arxiv.org/archive/physics"
  ],
  "created": "2026-02-24T10:30:00Z",
  "license": "CC-BY-SA-4.0"
}
```

## Validation Rules

### Manifest Validation

- **name**: Cannot be empty
- **version**: Must follow semantic versioning (e.g., "1.2.0")
- **description**: Cannot be empty
- **graph_stats**: All values must be non-negative integers
- **eval_scores**: All values must be between 0.0 and 1.0
- **source_urls**: Cannot be empty list
- **created**: Must be valid ISO 8601 timestamp
- **license**: Cannot be empty

### Structure Validation

- `manifest.json` must exist and be valid JSON
- `pack.db` must exist and be a directory (Kuzu database format)
- `skill.md` must exist
- `kg_config.json` must exist and be valid JSON

## Testing

Comprehensive test suite with 32 tests covering:

1. **Data Model Tests** (`test_manifest.py`):
   - GraphStats, EvalScores, PackManifest creation
   - Serialization (to_dict, from_dict)
   - Loading and saving manifests
   - Validation logic

2. **Validator Tests** (`test_validator.py`):
   - Structure validation for valid packs
   - Detection of missing required files
   - Invalid file format detection
   - Optional file handling

3. **Integration Tests** (`test_pack_structure.py`):
   - Complete pack creation workflows
   - Multiple pack scenarios
   - Design spec compliance verification

Run tests:
```bash
pytest tests/packs/ -v
```

## Design Reference

This implementation follows the design specification in:
`docs/design/knowledge-packs.md`

Phase 1 deliverables (this implementation):
- ✅ Pack manifest schema and validation
- ✅ Pack directory structure
- ✅ Manifest parser (load, save, validate)
- ✅ Pack validator (structure and content)
- ✅ Comprehensive test suite

## Future Phases

This Phase 1 implementation provides the foundation for:

- **Phase 2**: Skills Integration - Claude Code auto-discovery
- **Phase 3**: Evaluation Framework - Three-baseline comparison
- **Phase 4**: Distribution & Registry - Pack sharing and updates
- **Phase 5**: Advanced Features - Custom sources, multi-pack queries

## Usage in CLI

Future `wikigr pack` commands will use these modules:

```bash
# Validate pack structure
wikigr pack validate ./physics-expert

# Install pack (future)
wikigr pack install ./physics-expert

# Create pack (future)
wikigr pack create physics-expert --source wikipedia
```

## API Stability

Phase 1 APIs are stable and follow these principles:

- **Dataclasses**: Type-safe, immutable-by-default data models
- **Simple validation**: Clear error messages, no exceptions on validation
- **Path-based**: All functions accept Path objects for directory references
- **No external dependencies**: Pure Python with only standard library (json, pathlib, re, datetime)

## Contributing

When extending this module:

1. Follow TDD: Write tests first, then implementation
2. Use dataclasses and type hints
3. Keep validation logic simple and clear
4. Return error lists instead of raising exceptions
5. Maintain 100% test coverage for new code
