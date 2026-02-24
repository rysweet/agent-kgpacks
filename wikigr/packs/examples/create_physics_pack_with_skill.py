"""Example: Create a complete physics knowledge pack with skill integration.

This example demonstrates the complete Phase 2 workflow:
1. Create pack directory structure
2. Generate manifest with metadata
3. Create placeholder Kuzu database
4. Generate kg_config.json
5. Auto-generate skill.md from manifest
6. Discover pack and register it

Run:
    python -m wikigr.packs.examples.create_physics_pack_with_skill
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from wikigr.packs import (
    EvalScores,
    GraphStats,
    PackManifest,
    PackRegistry,
    discover_packs,
    generate_skill_md,
    save_manifest,
)


def create_physics_pack_with_skill(packs_dir: Path) -> None:
    """Create a complete physics knowledge pack with skill integration.

    Args:
        packs_dir: Directory where packs should be installed
    """
    # 1. Define pack metadata
    pack_name = "physics-expert"
    manifest = PackManifest(
        name=pack_name,
        version="1.0.0",
        description="Expert knowledge in quantum mechanics, relativity, and classical physics",
        graph_stats=GraphStats(
            articles=5240,
            entities=18500,
            relationships=42300,
            size_mb=420,
        ),
        eval_scores=EvalScores(
            accuracy=0.94,
            hallucination_rate=0.04,
            citation_quality=0.98,
        ),
        source_urls=[
            "https://en.wikipedia.org/wiki/Portal:Physics",
            "https://arxiv.org/archive/physics",
        ],
        created=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        license="CC-BY-SA-4.0",
    )

    # 2. Create pack directory
    pack_dir = packs_dir / pack_name
    if pack_dir.exists():
        print(f"Removing existing pack at {pack_dir}")
        shutil.rmtree(pack_dir)
    pack_dir.mkdir(parents=True)

    # 3. Save manifest
    print(f"Creating pack at {pack_dir}")
    save_manifest(manifest, pack_dir)
    print("✓ Created manifest.json")

    # 4. Create Kuzu database directory (placeholder)
    pack_db_dir = pack_dir / "pack.db"
    pack_db_dir.mkdir()
    print("✓ Created pack.db directory")

    # 5. Generate kg_config.json
    kg_config = {
        "retrieval": {
            "vector_k": 10,
            "graph_depth": 2,
            "hybrid_alpha": 0.7,
        },
        "embedding": {
            "model": "text-embedding-3-small",
            "dimensions": 1536,
        },
    }
    kg_config_path = pack_dir / "kg_config.json"
    with open(kg_config_path, "w") as f:
        json.dump(kg_config, f, indent=2)
        f.write("\n")
    print("✓ Created kg_config.json")

    # 6. Auto-generate skill.md from manifest
    skill_content = generate_skill_md(manifest, kg_config_path.resolve())
    skill_path = pack_dir / "skill.md"
    with open(skill_path, "w") as f:
        f.write(skill_content)
    print("✓ Generated skill.md")

    # 7. Create optional README
    readme_content = f"""# {manifest.name.replace('-', ' ').title()}

{manifest.description}

## Statistics

- **Articles**: {manifest.graph_stats.articles:,}
- **Entities**: {manifest.graph_stats.entities:,}
- **Relationships**: {manifest.graph_stats.relationships:,}
- **Database Size**: {manifest.graph_stats.size_mb} MB

## Quality Metrics

- **Accuracy**: {manifest.eval_scores.accuracy:.1%}
- **Hallucination Rate**: {manifest.eval_scores.hallucination_rate:.1%}
- **Citation Quality**: {manifest.eval_scores.citation_quality:.1%}

## Sources

{chr(10).join(f'- {url}' for url in manifest.source_urls)}

## License

{manifest.license}

## Usage

This pack can be used as a Claude Code skill for expert physics knowledge retrieval.

See `skill.md` for integration details.
"""
    readme_path = pack_dir / "README.md"
    with open(readme_path, "w") as f:
        f.write(readme_content)
    print("✓ Created README.md")

    print(f"\n✅ Pack created successfully at {pack_dir}")
    print("\nPack structure:")
    for item in sorted(pack_dir.rglob("*")):
        if item.is_file():
            rel_path = item.relative_to(pack_dir)
            print(f"  {rel_path}")


def demonstrate_discovery(packs_dir: Path) -> None:
    """Demonstrate pack discovery and registry.

    Args:
        packs_dir: Directory containing packs
    """
    print("\n" + "=" * 60)
    print("PACK DISCOVERY & REGISTRY")
    print("=" * 60)

    # Discover packs
    print(f"\nDiscovering packs in {packs_dir}...")
    packs = discover_packs(packs_dir)
    print(f"Found {len(packs)} pack(s)")

    for pack in packs:
        print(f"\n📦 {pack.name} v{pack.version}")
        print(f"   Path: {pack.path}")
        print(f"   Skill: {pack.skill_path}")
        print(f"   Description: {pack.manifest.description}")
        print(
            f"   Stats: {pack.manifest.graph_stats.articles:,} articles, "
            f"{pack.manifest.graph_stats.entities:,} entities"
        )

    # Use registry
    print("\n\nInitializing PackRegistry...")
    registry = PackRegistry(packs_dir)
    print(f"Registry contains {registry.count()} pack(s)")

    # List all packs
    print("\nAll packs in registry:")
    for pack in registry.list_packs():
        print(f"  - {pack.name} v{pack.version}")

    # Get specific pack
    physics_pack = registry.get_pack("physics-expert")
    if physics_pack:
        print("\n✓ Retrieved 'physics-expert' pack:")
        print(f"  Version: {physics_pack.version}")
        print(f"  Path: {physics_pack.path}")
        print(f"  Skill path: {physics_pack.skill_path}")


def main():
    """Run the complete example."""
    # Use temporary directory for example
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        packs_dir = Path(tmpdir) / "packs"
        packs_dir.mkdir()

        print("=" * 60)
        print("PHASE 2: SKILLS INTEGRATION EXAMPLE")
        print("=" * 60)
        print(f"\nUsing temporary packs directory: {packs_dir}\n")

        # Create pack with skill
        create_physics_pack_with_skill(packs_dir)

        # Demonstrate discovery
        demonstrate_discovery(packs_dir)

        print("\n" + "=" * 60)
        print("✅ Phase 2 example completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    main()
