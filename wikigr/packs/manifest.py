"""Pack manifest data model and operations.

This module provides the PackManifest dataclass and functions for loading,
saving, and validating pack manifests.
"""

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
        license: License identifier (e.g., "CC-BY-SA-4.0")
        eval_scores: Evaluation scores (optional)
        source_urls: List of source URLs used to create the pack (optional)
        created: ISO 8601 timestamp when pack was created (deprecated, use created_at)
        created_at: ISO 8601 timestamp when pack was created (primary field)
        author: Pack author (optional)
        topics: List of topics covered by the pack (optional)
    """

    name: str
    version: str
    description: str
    graph_stats: GraphStats
    license: str
    eval_scores: EvalScores | None = None
    source_urls: list[str] | None = None
    created: str | None = None  # Deprecated, use created_at (backward compat)
    created_at: str | None = None  # Primary timestamp field (optional for backward compat)
    author: str | None = None
    topics: list[str] | None = None

    def __post_init__(self):
        """Handle backward compatibility for created → created_at migration."""
        # If created_at is not provided, try to use created
        if self.created_at is None:
            if self.created is not None:
                self.created_at = self.created
            else:
                # Default to current timestamp if neither is provided
                self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        result = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "graph_stats": asdict(self.graph_stats),
            "license": self.license,
            "created_at": self.created_at,
        }
        if self.eval_scores is not None:
            result["eval_scores"] = asdict(self.eval_scores)
        if self.source_urls is not None:
            result["source_urls"] = self.source_urls
        if self.author is not None:
            result["author"] = self.author
        if self.topics is not None:
            result["topics"] = self.topics
        # Backwards compat
        if self.created is not None:
            result["created"] = self.created
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackManifest":
        """Create manifest from dictionary.

        Args:
            data: Dictionary containing manifest data

        Returns:
            PackManifest instance
        """
        # Support both created_at (new) and created (old)
        created_at = data.get("created_at") or data.get("created", "")

        return cls(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            graph_stats=GraphStats(**data["graph_stats"]),
            license=data["license"],
            created_at=created_at,
            eval_scores=EvalScores(**data["eval_scores"]) if "eval_scores" in data else None,
            source_urls=data.get("source_urls"),
            created=data.get("created"),
            author=data.get("author"),
            topics=data.get("topics"),
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

    # Validate eval scores (0.0 to 1.0 range) - optional
    if manifest.eval_scores is not None:
        if not (0.0 <= manifest.eval_scores.accuracy <= 1.0):
            errors.append("Eval score accuracy must be between 0 and 1")
        if not (0.0 <= manifest.eval_scores.hallucination_rate <= 1.0):
            errors.append("Eval score hallucination_rate must be between 0 and 1")
        if not (0.0 <= manifest.eval_scores.citation_quality <= 1.0):
            errors.append("Eval score citation_quality must be between 0 and 1")

    # Validate source_urls - optional but cannot be empty list
    if manifest.source_urls is not None and len(manifest.source_urls) == 0:
        errors.append("source_urls list cannot be empty (use None if not applicable)")

    # Validate created_at timestamp (ISO 8601)
    try:
        datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(f"Invalid ISO 8601 timestamp for created_at: {manifest.created_at}")

    # Validate license
    if not manifest.license or not manifest.license.strip():
        errors.append("Pack license cannot be empty")

    return errors
