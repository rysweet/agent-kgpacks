"""Evaluation runner for complete three-baseline comparison.

This module orchestrates the evaluation process:
1. Run training baseline
2. Run web search baseline
3. Run knowledge pack baseline
4. Calculate metrics for each
5. Compare and determine if pack surpasses baselines
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from wikigr.packs.eval.baselines import (
    KnowledgePackEvaluator,
    TrainingBaselineEvaluator,
    WebSearchBaselineEvaluator,
)
from wikigr.packs.eval.metrics import aggregate_metrics
from wikigr.packs.eval.models import EvalResult, Question


class EvalRunner:
    """Runner for complete three-baseline evaluation."""

    def __init__(self, pack_path: Path, api_key: str | None = None):
        """Initialize evaluation runner.

        Args:
            pack_path: Path to knowledge pack directory
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.pack_path = pack_path
        self.training_eval = TrainingBaselineEvaluator(api_key=api_key)
        self.web_eval = WebSearchBaselineEvaluator(api_key=api_key)
        self.pack_eval = KnowledgePackEvaluator(pack_path, api_key=api_key)

    def run_evaluation(self, questions: list[Question]) -> EvalResult:
        """Run complete three-baseline evaluation.

        Args:
            questions: List of questions to evaluate

        Returns:
            EvalResult with all metrics and comparisons
        """
        # Run all three baselines
        print("Running training baseline...")
        training_answers = self.training_eval.evaluate(questions)
        training_metrics = aggregate_metrics(training_answers, questions)

        print("Running web search baseline...")
        web_answers = self.web_eval.evaluate(questions)
        web_metrics = aggregate_metrics(web_answers, questions)

        print("Running knowledge pack baseline...")
        pack_answers = self.pack_eval.evaluate(questions)
        pack_metrics = aggregate_metrics(pack_answers, questions)

        # Determine if pack surpasses baselines
        # Pack surpasses if it has:
        # - Higher accuracy
        # - Lower hallucination rate
        # - Higher citation quality
        surpasses_training = (
            pack_metrics.accuracy > training_metrics.accuracy
            and pack_metrics.hallucination_rate < training_metrics.hallucination_rate
            and pack_metrics.citation_quality > training_metrics.citation_quality
        )

        surpasses_web = (
            pack_metrics.accuracy > web_metrics.accuracy
            and pack_metrics.hallucination_rate < web_metrics.hallucination_rate
            and pack_metrics.citation_quality > web_metrics.citation_quality
        )

        # Get pack name from manifest
        manifest_path = self.pack_path / "manifest.json"
        pack_name = "unknown"
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
                pack_name = manifest.get("name", "unknown")

        # Create result
        result = EvalResult(
            pack_name=pack_name,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            training_baseline=training_metrics,
            web_search_baseline=web_metrics,
            knowledge_pack=pack_metrics,
            surpasses_training=surpasses_training,
            surpasses_web=surpasses_web,
            questions_tested=len(questions),
        )

        return result

    def save_results(self, result: EvalResult, output_path: Path) -> None:
        """Save evaluation results to JSON.

        Args:
            result: EvalResult to save
            output_path: Path to save JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict
        result_dict = {
            "pack_name": result.pack_name,
            "timestamp": result.timestamp,
            "training_baseline": asdict(result.training_baseline),
            "web_search_baseline": asdict(result.web_search_baseline),
            "knowledge_pack": asdict(result.knowledge_pack),
            "surpasses_training": result.surpasses_training,
            "surpasses_web": result.surpasses_web,
            "questions_tested": result.questions_tested,
        }

        with open(output_path, "w") as f:
            json.dump(result_dict, f, indent=2)
            f.write("\n")

        print(f"Results saved to {output_path}")
