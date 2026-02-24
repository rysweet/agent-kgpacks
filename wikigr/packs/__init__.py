"""Knowledge Pack system for WikiGR.

This module provides the core infrastructure for creating, managing, and using
knowledge packs - reusable, distributable domain-specific knowledge graphs.
"""

from wikigr.packs.discovery import discover_packs, is_valid_pack
from wikigr.packs.distribution import package_pack, unpackage_pack
from wikigr.packs.eval import (
    Answer,
    EvalMetrics,
    EvalResult,
    EvalRunner,
    KnowledgePackEvaluator,
    Question,
    TrainingBaselineEvaluator,
    WebSearchBaselineEvaluator,
    aggregate_metrics,
    calculate_accuracy,
    calculate_citation_quality,
    calculate_hallucination_rate,
    load_questions_jsonl,
    validate_questions,
)
from wikigr.packs.installer import PackInstaller
from wikigr.packs.manifest import (
    EvalScores,
    GraphStats,
    PackManifest,
    load_manifest,
    save_manifest,
    validate_manifest,
)
from wikigr.packs.models import PackInfo
from wikigr.packs.registry import PackRegistry
from wikigr.packs.registry_api import PackListing, PackRegistryClient
from wikigr.packs.skill_template import generate_skill_md
from wikigr.packs.validator import validate_pack_structure
from wikigr.packs.versioning import compare_versions, is_compatible

__all__ = [
    # Manifest
    "PackManifest",
    "GraphStats",
    "EvalScores",
    "load_manifest",
    "save_manifest",
    "validate_manifest",
    # Validation
    "validate_pack_structure",
    "is_valid_pack",
    # Discovery
    "discover_packs",
    "PackInfo",
    # Distribution
    "package_pack",
    "unpackage_pack",
    # Installation
    "PackInstaller",
    # Versioning
    "compare_versions",
    "is_compatible",
    # Registry
    "PackRegistry",
    "PackRegistryClient",
    "PackListing",
    # Skill generation
    "generate_skill_md",
    # Evaluation framework
    "Question",
    "Answer",
    "EvalMetrics",
    "EvalResult",
    "TrainingBaselineEvaluator",
    "WebSearchBaselineEvaluator",
    "KnowledgePackEvaluator",
    "calculate_accuracy",
    "calculate_hallucination_rate",
    "calculate_citation_quality",
    "aggregate_metrics",
    "load_questions_jsonl",
    "validate_questions",
    "EvalRunner",
]
