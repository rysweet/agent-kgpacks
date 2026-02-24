"""Integration tests for complete pack directory structure."""

import json
from pathlib import Path

from wikigr.packs import (
    EvalScores,
    GraphStats,
    PackManifest,
    load_manifest,
    save_manifest,
    validate_pack_structure,
)


class TestPackDirectoryStructure:
    """Test complete pack directory structure creation and validation."""

    def test_create_minimal_pack(self, tmp_path: Path):
        """Test creating minimal valid pack structure."""
        pack_dir = tmp_path / "physics-expert"
        pack_dir.mkdir()

        # Create manifest
        manifest = PackManifest(
            name="physics-expert",
            version="1.0.0",
            description="Expert knowledge in quantum mechanics and relativity",
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
            source_urls=["https://en.wikipedia.org/wiki/Portal:Physics"],
            created="2026-02-24T10:30:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)

        # Create pack.db (Kuzu database directory)
        (pack_dir / "pack.db").mkdir()

        # Create skill.md
        skill_content = """---
name: physics-expert
description: Domain expert in physics with graph-enhanced knowledge retrieval
version: 1.0.0
---

# Physics Expert Knowledge Pack

Domain expert in quantum mechanics and relativity.
"""
        (pack_dir / "skill.md").write_text(skill_content)

        # Create kg_config.json
        kg_config = {
            "pack_name": "physics-expert",
            "database_path": "pack.db",
            "retrieval_strategy": {
                "vector_search": {"top_k": 10, "min_similarity": 0.75},
                "graph_traversal": {"enabled": True, "max_depth": 3},
            },
        }
        (pack_dir / "kg_config.json").write_text(json.dumps(kg_config, indent=2))

        # Validate structure
        errors = validate_pack_structure(pack_dir)
        assert len(errors) == 0

        # Verify files exist
        assert (pack_dir / "manifest.json").exists()
        assert (pack_dir / "pack.db").is_dir()
        assert (pack_dir / "skill.md").exists()
        assert (pack_dir / "kg_config.json").exists()

        # Verify manifest can be loaded
        loaded_manifest = load_manifest(pack_dir)
        assert loaded_manifest.name == "physics-expert"
        assert loaded_manifest.version == "1.0.0"
        assert loaded_manifest.graph_stats.articles == 5240

    def test_create_complete_pack_with_eval(self, tmp_path: Path):
        """Test creating complete pack structure with eval directory."""
        pack_dir = tmp_path / "physics-expert"
        pack_dir.mkdir()

        # Create manifest
        manifest = PackManifest(
            name="physics-expert",
            version="1.2.0",
            description="Expert knowledge in physics",
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
            created="2026-02-24T10:30:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)

        # Create pack.db
        (pack_dir / "pack.db").mkdir()

        # Create skill.md
        (pack_dir / "skill.md").write_text("# Physics Expert")

        # Create kg_config.json
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": "physics-expert"}))

        # Create README.md
        readme = """# Physics Expert Knowledge Pack

Domain expert in quantum mechanics, relativity, and classical physics.

## Installation

```bash
wikigr pack install physics-expert
```
"""
        (pack_dir / "README.md").write_text(readme)

        # Create eval directory with questions
        eval_dir = pack_dir / "eval"
        eval_dir.mkdir()

        questions = [
            {
                "id": "phys-001",
                "question": "What is the Heisenberg uncertainty principle?",
                "answer": "The uncertainty principle states...",
                "difficulty": "basic",
            },
            {
                "id": "phys-002",
                "question": "Explain quantum tunneling",
                "answer": "Quantum tunneling is...",
                "difficulty": "intermediate",
            },
        ]
        questions_file = eval_dir / "questions.jsonl"
        questions_file.write_text("\n".join(json.dumps(q) for q in questions) + "\n")

        # Validate structure
        errors = validate_pack_structure(pack_dir)
        assert len(errors) == 0

        # Verify all files
        assert (pack_dir / "manifest.json").exists()
        assert (pack_dir / "pack.db").is_dir()
        assert (pack_dir / "skill.md").exists()
        assert (pack_dir / "kg_config.json").exists()
        assert (pack_dir / "README.md").exists()
        assert (eval_dir / "questions.jsonl").exists()

    def test_pack_directory_layout_matches_spec(self, tmp_path: Path):
        """Test that pack directory matches design spec layout."""
        # This test documents the expected structure from knowledge-packs.md
        pack_dir = tmp_path / "physics-expert"
        pack_dir.mkdir()

        # Expected structure from design doc:
        # physics-expert/
        # ├── manifest.json
        # ├── pack.db/
        # ├── kg_config.json
        # ├── skill.md
        # ├── eval/
        # │   └── questions.jsonl
        # └── README.md

        # Create all components
        manifest = PackManifest(
            name="physics-expert",
            version="1.0.0",
            description="Test pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)

        (pack_dir / "pack.db").mkdir()
        (pack_dir / "skill.md").write_text("# Skill")
        (pack_dir / "kg_config.json").write_text("{}")
        (pack_dir / "README.md").write_text("# README")
        (pack_dir / "eval").mkdir()
        (pack_dir / "eval" / "questions.jsonl").write_text("{}\n")

        # Verify structure matches spec
        assert (pack_dir / "manifest.json").is_file()
        assert (pack_dir / "pack.db").is_dir()
        assert (pack_dir / "kg_config.json").is_file()
        assert (pack_dir / "skill.md").is_file()
        assert (pack_dir / "eval").is_dir()
        assert (pack_dir / "eval" / "questions.jsonl").is_file()
        assert (pack_dir / "README.md").is_file()

        # Validate
        errors = validate_pack_structure(pack_dir)
        assert len(errors) == 0

    def test_multiple_packs_in_parent_directory(self, tmp_path: Path):
        """Test scenario with multiple packs like ~/.wikigr/packs/."""
        packs_root = tmp_path / "packs"
        packs_root.mkdir()

        # Create multiple packs
        pack_names = ["physics-expert", "math-expert", "chem-expert"]

        for pack_name in pack_names:
            pack_dir = packs_root / pack_name
            pack_dir.mkdir()

            manifest = PackManifest(
                name=pack_name,
                version="1.0.0",
                description=f"{pack_name} knowledge",
                graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
                eval_scores=EvalScores(
                    accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95
                ),
                source_urls=["https://example.com"],
                created="2026-02-24T10:00:00Z",
                license="CC-BY-SA-4.0",
            )
            save_manifest(manifest, pack_dir)
            (pack_dir / "pack.db").mkdir()
            (pack_dir / "skill.md").write_text(f"# {pack_name}")
            (pack_dir / "kg_config.json").write_text("{}")

        # Verify all packs are valid
        for pack_name in pack_names:
            pack_dir = packs_root / pack_name
            errors = validate_pack_structure(pack_dir)
            assert len(errors) == 0

            manifest = load_manifest(pack_dir)
            assert manifest.name == pack_name
