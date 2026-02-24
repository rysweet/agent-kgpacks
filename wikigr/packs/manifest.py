"""Pack manifest data model and operations.

This module provides the PackManifest dataclass and functions for loading,
saving, and validating pack manifests.
"""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class GraphStats:
    """Statistics about the knowledge graph in a pack.

    Attributes:
        articles: Number of articles in the knowledge graph
        entities: Number of extracted entities
        relationships: Number of relationships between entities
        size_mb: Database size in megabytes
    """

    articles: int
    entities: int
    relationships: int
    size_mb: int


@dataclass
class EvalScores:
    """Evaluation scores for pack quality.

    Attributes:
        accuracy: Accuracy score (0.0 to 1.0) on test questions
        hallucination_rate: Rate of fabricated information (0.0 to 1.0)
        citation_quality: Quality of citations (0.0 to 1.0)
    """

    accuracy: float
    hallucination_rate: float
    citation_quality: float


@dataclass
class PackManifest:
    """Pack manifest containing metadata and statistics.

    Attributes:
        name: Pack name (e.g., "physics-expert")
        version: Semantic version (e.g., "1.2.0")
        description: Human-readable description
        graph_stats: Knowledge graph statistics
        eval_scores: Evaluation scores
        source_urls: List of source URLs used to create the pack
        created: ISO 8601 timestamp when pack was created
        license: License identifier (e.g., "CC-BY-SA-4.0")
    """

    name: str
    version: str
    description: str
    graph_stats: GraphStats
    eval_scores: EvalScores
    source_urls: list[str]
    created: str
    license: str

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "graph_stats": asdict(self.graph_stats),
            "eval_scores": asdict(self.eval_scores),
            "source_urls": self.source_urls,
            "created": self.created,
            "license": self.license,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackManifest":
        """Create manifest from dictionary.

        Args:
            data: Dictionary containing manifest data

        Returns:
            PackManifest instance
        """
        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            graph_stats=GraphStats(**data["graph_stats"]),
            eval_scores=EvalScores(**data["eval_scores"]),
            source_urls=data["source_urls"],
            created=data["created"],
            license=data["license"],
        )


def load_manifest(pack_dir: Path) -> PackManifest:
    """Load pack manifest from directory.

    Args:
        pack_dir: Path to pack directory

    Returns:
        Loaded PackManifest

    Raises:
        FileNotFoundError: If manifest.json doesn't exist
        json.JSONDecodeError: If manifest.json contains invalid JSON
    """
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {pack_dir}")

    with open(manifest_path) as f:
        data = json.load(f)

    return PackManifest.from_dict(data)


def save_manifest(manifest: PackManifest, pack_dir: Path) -> None:
    """Save pack manifest to directory.

    Args:
        manifest: PackManifest to save
        pack_dir: Path to pack directory (created if it doesn't exist)
    """
    pack_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = pack_dir / "manifest.json"

    with open(manifest_path, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
        f.write("\n")  # Add trailing newline


def validate_manifest(manifest: PackManifest) -> list[str]:
    """Validate pack manifest and return list of errors.

    Args:
        manifest: PackManifest to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Validate name
    if not manifest.name or not manifest.name.strip():
        errors.append("Pack name cannot be empty")

    # Validate version (semantic versioning)
    semver_pattern = r"^\d+\.\d+\.\d+(-[\w\.]+)?(\+[\w\.]+)?$"
    if not re.match(semver_pattern, manifest.version):
        errors.append(f"Invalid semantic version: {manifest.version}")

    # Validate description
    if not manifest.description or not manifest.description.strip():
        errors.append("Pack description cannot be empty")

    # Validate graph stats (no negative values)
    if manifest.graph_stats.articles < 0:
        errors.append("Graph stats articles cannot be negative")
    if manifest.graph_stats.entities < 0:
        errors.append("Graph stats entities cannot be negative")
    if manifest.graph_stats.relationships < 0:
        errors.append("Graph stats relationships cannot be negative")
    if manifest.graph_stats.size_mb < 0:
        errors.append("Graph stats size_mb cannot be negative")

    # Validate eval scores (0.0 to 1.0 range)
    if not (0.0 <= manifest.eval_scores.accuracy <= 1.0):
        errors.append("Eval score accuracy must be between 0 and 1")
    if not (0.0 <= manifest.eval_scores.hallucination_rate <= 1.0):
        errors.append("Eval score hallucination_rate must be between 0 and 1")
    if not (0.0 <= manifest.eval_scores.citation_quality <= 1.0):
        errors.append("Eval score citation_quality must be between 0 and 1")

    # Validate source_urls
    if not manifest.source_urls:
        errors.append("Pack source_urls cannot be empty")

    # Validate created timestamp (ISO 8601)
    try:
        datetime.fromisoformat(manifest.created.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(f"Invalid ISO 8601 timestamp for created: {manifest.created}")

    # Validate license
    if not manifest.license or not manifest.license.strip():
        errors.append("Pack license cannot be empty")

    return errors
