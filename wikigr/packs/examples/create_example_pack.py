#!/usr/bin/env python3
"""Example script demonstrating how to create a knowledge pack.

This script shows the complete workflow for creating a minimal valid
knowledge pack structure using the wikigr.packs API.
"""

import json
from pathlib import Path

from wikigr.packs import (
    EvalScores,
    GraphStats,
    PackManifest,
    save_manifest,
    validate_pack_structure,
)


def create_example_pack(output_dir: Path = Path("./example-pack")) -> None:
    """Create an example knowledge pack with all required components.

    Args:
        output_dir: Directory to create the pack in
    """
    print(f"Creating example pack in: {output_dir}")

    # Step 1: Create manifest
    print("\n1. Creating manifest...")
    manifest = PackManifest(
        name="example-pack",
        version="1.0.0",
        description="Example knowledge pack demonstrating the pack format",
        graph_stats=GraphStats(
            articles=100,
            entities=250,
            relationships=400,
            size_mb=15,
        ),
        eval_scores=EvalScores(
            accuracy=0.90,
            hallucination_rate=0.05,
            citation_quality=0.95,
        ),
        source_urls=["https://example.com/docs"],
        created="2026-02-24T10:00:00Z",
        license="CC-BY-SA-4.0",
    )
    save_manifest(manifest, output_dir)
    print("   ✓ Created manifest.json")

    # Step 2: Create pack.db directory (placeholder for Kuzu database)
    print("\n2. Creating pack.db directory...")
    pack_db_dir = output_dir / "pack.db"
    pack_db_dir.mkdir(exist_ok=True)
    # In a real pack, this would be a Kuzu database
    # For this example, just create a placeholder file
    (pack_db_dir / ".placeholder").write_text(
        "This directory would contain a Kuzu graph database\n"
    )
    print("   ✓ Created pack.db/ directory")

    # Step 3: Create skill.md
    print("\n3. Creating skill.md...")
    skill_content = """---
name: example-pack
description: Example knowledge pack skill
author: WikiGR Examples
version: 1.0.0
activation:
  keywords:
    - example-pack
  auto_load: false
dependencies:
  - wikigr>=0.9.0
---

# Example Knowledge Pack

## Purpose

This is an example knowledge pack demonstrating the pack format and structure.

## When I Activate

I load when you:
- Use "example-pack" skill explicitly
- Ask questions with keyword triggers

## Capabilities

### 1. Example Queries

**Query**: "Explain concept X"

**What I do**:
1. Search graph for concept X
2. Retrieve related information
3. Assemble explanation with citations

## Example Usage

```python
from wikigr.pack_manager import KnowledgePackSkill

skill = KnowledgePackSkill("example-pack")
result = skill.query("Explain example concept")
print(result.answer)
```

## Evaluation Metrics

Current performance (v1.0.0):
- **Accuracy**: 90% on 100 test questions
- **Hallucination Rate**: 5%
- **Citation Quality**: 95% verifiable sources

## Limitations

- **Scope**: Example domain only
- **Depth**: Basic level
- **Recency**: Knowledge cutoff February 2026
- **Languages**: English only
"""
    (output_dir / "skill.md").write_text(skill_content)
    print("   ✓ Created skill.md")

    # Step 4: Create kg_config.json
    print("\n4. Creating kg_config.json...")
    kg_config = {
        "pack_name": "example-pack",
        "database_path": "pack.db",
        "retrieval_strategy": {
            "hybrid": {
                "vector_weight": 0.6,
                "graph_weight": 0.3,
                "keyword_weight": 0.1,
            },
            "vector_search": {
                "model": "text-embedding-3-small",
                "top_k": 10,
                "min_similarity": 0.75,
                "rerank": True,
            },
            "graph_traversal": {
                "enabled": True,
                "max_depth": 3,
                "relationship_types": [
                    "RELATES_TO",
                    "EXPLAINS",
                    "DEPENDS_ON",
                ],
                "min_relationship_weight": 0.5,
            },
            "keyword_search": {
                "enabled": True,
                "fields": ["title", "content", "entity_name"],
                "boost_exact_match": 1.5,
                "fuzzy_threshold": 0.8,
            },
        },
        "context_assembly": {
            "max_sections": 5,
            "max_entities": 15,
            "max_relationships": 20,
            "citation_mode": "strict",
            "include_provenance": True,
            "deduplication": True,
        },
        "caching": {
            "enabled": True,
            "ttl_seconds": 3600,
            "max_cache_size_mb": 100,
        },
    }
    (output_dir / "kg_config.json").write_text(json.dumps(kg_config, indent=2) + "\n")
    print("   ✓ Created kg_config.json")

    # Step 5: Create optional README.md
    print("\n5. Creating README.md (optional)...")
    readme_content = """# Example Knowledge Pack

This is an example knowledge pack demonstrating the WikiGR pack format.

## Installation

```bash
wikigr pack install example-pack
```

## Usage

```bash
# In Claude Code session
User: "Use example-pack to explain concept X"
```

## Pack Contents

- **Articles**: 100
- **Entities**: 250
- **Relationships**: 400
- **Database Size**: 15 MB

## Evaluation

- **Accuracy**: 90%
- **Hallucination Rate**: 5%
- **Citation Quality**: 95%

## License

CC-BY-SA-4.0

## Version

1.0.0
"""
    (output_dir / "README.md").write_text(readme_content)
    print("   ✓ Created README.md")

    # Step 6: Create optional eval directory
    print("\n6. Creating eval/ directory (optional)...")
    eval_dir = output_dir / "eval"
    eval_dir.mkdir(exist_ok=True)

    # Create example questions
    questions = [
        {
            "id": "example-001",
            "question": "What is concept A?",
            "answer": "Concept A is...",
            "difficulty": "basic",
            "category": "fundamentals",
        },
        {
            "id": "example-002",
            "question": "How does concept B relate to concept C?",
            "answer": "Concept B relates to C through...",
            "difficulty": "intermediate",
            "category": "relationships",
        },
    ]
    questions_file = eval_dir / "questions.jsonl"
    questions_file.write_text("\n".join(json.dumps(q) for q in questions) + "\n")
    print("   ✓ Created eval/questions.jsonl")

    # Step 7: Validate the pack structure
    print("\n7. Validating pack structure...")
    errors = validate_pack_structure(output_dir)
    if errors:
        print("   ✗ Validation errors:")
        for error in errors:
            print(f"     - {error}")
    else:
        print("   ✓ Pack structure is valid!")

    print(f"\n✅ Example pack created successfully at: {output_dir.absolute()}")
    print("\nPack structure:")
    print("example-pack/")
    print("├── manifest.json")
    print("├── pack.db/")
    print("├── skill.md")
    print("├── kg_config.json")
    print("├── README.md")
    print("└── eval/")
    print("    └── questions.jsonl")


if __name__ == "__main__":
    # Create example pack in current directory
    create_example_pack()
