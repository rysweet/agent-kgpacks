"""Knowledge pack evaluation framework.

This module provides a three-baseline evaluation system for assessing
whether knowledge packs surpass training data and web search:

1. Training baseline: Claude without any tools
2. Web search baseline: Claude with web search
3. Knowledge pack baseline: Claude with pack retrieval

Key metrics:
- Accuracy: semantic similarity to ground truth
- Hallucination rate: detection of unsupported claims
- Citation quality: validation of citations
"""

from wikigr.packs.eval.baselines import (
    KnowledgePackEvaluator,
    TrainingBaselineEvaluator,
    WebSearchBaselineEvaluator,
)
from wikigr.packs.eval.metrics import (
    aggregate_metrics,
    calculate_accuracy,
    calculate_citation_quality,
    calculate_hallucination_rate,
)
from wikigr.packs.eval.models import Answer, EvalMetrics, EvalResult, Question
from wikigr.packs.eval.questions import load_questions_jsonl, validate_questions
from wikigr.packs.eval.runner import EvalRunner

__all__ = [
    # Models
    "Question",
    "Answer",
    "EvalMetrics",
    "EvalResult",
    # Baselines
    "TrainingBaselineEvaluator",
    "WebSearchBaselineEvaluator",
    "KnowledgePackEvaluator",
    # Metrics
    "calculate_accuracy",
    "calculate_hallucination_rate",
    "calculate_citation_quality",
    "aggregate_metrics",
    # Questions
    "load_questions_jsonl",
    "validate_questions",
    # Runner
    "EvalRunner",
]
