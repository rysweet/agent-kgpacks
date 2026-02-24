# Knowledge Packs - Phases 1 & 2: Pack Format & Skills Integration

This module implements the pack format, manifest system, and Claude Code skills integration for WikiGR Knowledge Packs.

## Overview

Knowledge Packs are reusable, distributable domain-specific knowledge graphs that can be installed and used as Claude Code skills. This implementation provides:

- **Phase 1**: Pack format, manifest, and validation
- **Phase 2**: Pack discovery, skill generation, and registry system

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

### 3. Pack Discovery (`discovery.py`)

**Functions:**
- `is_valid_pack(pack_dir)`: Check if directory contains a valid pack
- `discover_packs(packs_dir)`: Discover all installed packs in directory

**Example:**
```python
from wikigr.packs import discover_packs, is_valid_pack
from pathlib import Path

# Check single pack
if is_valid_pack(Path("./physics-expert")):
    print("Valid pack!")

# Discover all packs
packs = discover_packs(Path.home() / ".wikigr/packs")
for pack in packs:
    print(f"{pack.name} v{pack.version}")
```

### 4. Pack Models (`models.py`)

**Data Model:**
- `PackInfo`: Complete information about an installed pack
  - Includes name, version, path, manifest, and skill path
  - All paths are absolute for reliable access

**Example:**
```python
from wikigr.packs import discover_packs

packs = discover_packs()
for pack_info in packs:
    print(f"Name: {pack_info.name}")
    print(f"Version: {pack_info.version}")
    print(f"Path: {pack_info.path}")
    print(f"Skill: {pack_info.skill_path}")
```

### 5. Skill Template Generator (`skill_template.py`)

**Function:**
- `generate_skill_md(manifest, kg_config_path)`: Generate skill.md from manifest

Generates Claude Code skill files with:
- YAML frontmatter (name, version, description, triggers)
- Knowledge graph statistics
- Usage examples
- Quality metrics
- Technical details

**Example:**
```python
from wikigr.packs import generate_skill_md, load_manifest
from pathlib import Path

manifest = load_manifest(Path("./physics-expert"))
kg_config = Path("./physics-expert/kg_config.json")
skill_content = generate_skill_md(manifest, kg_config)

# Write to skill.md
with open("./physics-expert/skill.md", "w") as f:
    f.write(skill_content)
```

### 6. Pack Registry (`registry.py`)

**Class:**
- `PackRegistry`: Centralized registry for managing installed packs

**Methods:**
- `refresh()`: Rescan packs directory
- `get_pack(name)`: Get pack by name
- `list_packs()`: List all packs (sorted)
- `has_pack(name)`: Check if pack exists
- `count()`: Number of registered packs

**Example:**
```python
from wikigr.packs import PackRegistry
from pathlib import Path

# Initialize registry
registry = PackRegistry(Path.home() / ".wikigr/packs")

# Check for pack
if registry.has_pack("physics-expert"):
    pack = registry.get_pack("physics-expert")
    print(f"Found: {pack.name} v{pack.version}")

# List all packs
print(f"Total packs: {registry.count()}")
for pack in registry.list_packs():
    print(f"  - {pack.name}")

# Refresh after changes
registry.refresh()
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

Comprehensive test suite with 75 tests covering:

1. **Data Model Tests** (`test_manifest.py`, `test_models.py`):
   - GraphStats, EvalScores, PackManifest creation
   - PackInfo dataclass validation
   - Serialization (to_dict, from_dict)
   - Loading and saving manifests
   - Validation logic

2. **Validator Tests** (`test_validator.py`):
   - Structure validation for valid packs
   - Detection of missing required files
   - Invalid file format detection
   - Optional file handling

3. **Discovery Tests** (`test_discovery.py`):
   - Pack validation (`is_valid_pack`)
   - Pack discovery across directories
   - Filtering invalid packs
   - Absolute path handling

4. **Skill Template Tests** (`test_skill_template.py`):
   - skill.md generation from manifest
   - Frontmatter structure validation
   - Domain-specific trigger generation
   - Content section completeness

5. **Registry Tests** (`test_registry.py`):
   - Registry initialization and refresh
   - Pack lookup and listing
   - Dynamic pack addition/removal
   - Invalid pack filtering

6. **Integration Tests** (`test_pack_structure.py`):
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

**Phase 1 deliverables** (✅ Complete):
- ✅ Pack manifest schema and validation
- ✅ Pack directory structure
- ✅ Manifest parser (load, save, validate)
- ✅ Pack validator (structure and content)
- ✅ Comprehensive test suite

**Phase 2 deliverables** (✅ Complete):
- ✅ Pack discovery system (`is_valid_pack`, `discover_packs`)
- ✅ Pack information models (`PackInfo`)
- ✅ Skill template generator (`generate_skill_md`)
- ✅ Pack registry (`PackRegistry` class)
- ✅ Complete integration example
- ✅ 43 additional tests (75 total)

## Future Phases

Phases 1 & 2 provide the foundation for:

- **Phase 3**: Evaluation Framework - Three-baseline comparison
- **Phase 4**: Distribution & Registry - Pack sharing and updates
- **Phase 5**: CLI Commands - `wikigr pack` command suite

## Usage Examples

### Complete Pack Creation with Skills Integration

See `wikigr/packs/examples/create_physics_pack_with_skill.py` for a complete example:

```bash
python -m wikigr.packs.examples.create_physics_pack_with_skill
```

This example demonstrates:
1. Creating pack directory structure
2. Generating manifest with metadata
3. Creating placeholder Kuzu database
4. Generating kg_config.json
5. Auto-generating skill.md from manifest
6. Discovering pack and registering it

### Future CLI Commands

Future `wikigr pack` commands will use these modules:

```bash
# Validate pack structure
wikigr pack validate ./physics-expert

# Install pack (Phase 4)
wikigr pack install ./physics-expert

# Create pack (Phase 5)
wikigr pack create physics-expert --source wikipedia

# List installed packs (Phase 5)
wikigr pack list

# Update pack (Phase 4)
wikigr pack update physics-expert
```

## API Stability

Phase 1 & 2 APIs are stable and follow these principles:

- **Dataclasses**: Type-safe, immutable-by-default data models
- **Simple validation**: Clear error messages, no exceptions on validation
- **Path-based**: All functions accept Path objects for directory references
- **Absolute paths**: All returned paths are absolute for reliability
- **No external dependencies**: Pure Python with only standard library (json, pathlib, re, datetime)
- **Fail-safe discovery**: Invalid packs are silently skipped during discovery

## Contributing

When extending this module:

1. Follow TDD: Write tests first, then implementation
2. Use dataclasses and type hints
3. Keep validation logic simple and clear
4. Return error lists instead of raising exceptions
5. Maintain 100% test coverage for new code
