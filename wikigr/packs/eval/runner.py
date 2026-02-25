"""Evaluation runner for complete two-baseline comparison.

This module orchestrates the evaluation process:
1. Run training baseline
2. Run knowledge pack baseline
3. Calculate metrics for each
4. Compare and determine if pack surpasses training baseline
"""

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from wikigr.packs.eval.baselines import (
    KnowledgePackEvaluator,
    WebFetchBaselineEvaluator,
)
from wikigr.packs.eval.metrics import aggregate_metrics
from wikigr.packs.eval.models import Answer, EvalResult, Question

logger = logging.getLogger(__name__)


class EvalRunner:
    """Runner for complete two-baseline evaluation."""

    def __init__(self, pack_path: Path, api_key: str | None = None, dry_run: bool = False):
        """Initialize evaluation runner.

        Args:
            pack_path: Path to knowledge pack directory
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
            dry_run: If True, skip API calls and use mock data (for development)
        """
        self.pack_path = pack_path
        self.dry_run = dry_run

        if not dry_run:
            self.webfetch_eval = WebFetchBaselineEvaluator(api_key=api_key)
            self.pack_eval = KnowledgePackEvaluator(pack_path, api_key=api_key)
        else:
            logger.info("DRY RUN MODE: API calls will be skipped")
            self.webfetch_eval = None
            self.pack_eval = None

    def _generate_mock_answers(self, questions: list[Question], source: str) -> list[Answer]:
        """Generate mock answers for dry-run mode.

        Args:
            questions: List of questions
            source: Source name ("training", "knowledge_pack")

        Returns:
            List of mock answers
        """
        return [
            Answer(
                question_id=q.id,
                answer=f"Mock answer for {q.question} from {source}",
                source=source,
                latency_ms=100.0 + (i * 10),
                cost_usd=0.001 * (1.0 + i * 0.1),
            )
            for i, q in enumerate(questions)
        ]

    def run_evaluation(self, questions: list[Question], show_progress: bool = True) -> EvalResult:
        """Run complete two-baseline evaluation.

        Args:
            questions: List of questions to evaluate
            show_progress: Whether to show progress bar (default True)

        Returns:
            EvalResult with all metrics and comparisons
        """
        if self.dry_run:
            logger.info("DRY RUN: Using mock answers")
            webfetch_answers = self._generate_mock_answers(questions, "training")
            pack_answers = self._generate_mock_answers(questions, "knowledge_pack")
        else:
            # Run both baselines with progress tracking
            total_steps = len(questions) * 2
            with tqdm(total=total_steps, desc="Evaluating", disable=not show_progress) as pbar:
                logger.info("Running WebFetch baseline (Claude + web search)...")
                webfetch_answers = []
                for q in questions:
                    answers = self.webfetch_eval.evaluate([q])
                    webfetch_answers.extend(answers)
                    pbar.update(1)

                logger.info("Running knowledge pack baseline...")
                pack_answers = []
                for q in questions:
                    answers = self.pack_eval.evaluate([q])
                    pack_answers.extend(answers)
                    pbar.update(1)

        # Calculate metrics
        webfetch_metrics = aggregate_metrics(webfetch_answers, questions)
        pack_metrics = aggregate_metrics(pack_answers, questions)

        # Determine if pack surpasses training baseline
        # Pack surpasses if it has:
        # - Higher accuracy
        # - Lower hallucination rate
        # - Higher citation quality
        surpasses_webfetch = (
            pack_metrics.accuracy > webfetch_metrics.accuracy
            and pack_metrics.hallucination_rate < webfetch_metrics.hallucination_rate
            and pack_metrics.citation_quality > webfetch_metrics.citation_quality
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
            webfetch_baseline=webfetch_metrics,
            knowledge_pack=pack_metrics,
            surpasses_webfetch=surpasses_webfetch,
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
            "webfetch_baseline": asdict(result.webfetch_baseline),
            "web_search_baseline": asdict(result.web_search_baseline)
            if result.web_search_baseline
            else None,
            "knowledge_pack": asdict(result.knowledge_pack),
            "surpasses_webfetch": result.surpasses_webfetch,
            "surpasses_web": result.surpasses_web,
            "questions_tested": result.questions_tested,
        }

        with open(output_path, "w") as f:
            json.dump(result_dict, f, indent=2)
            f.write("\n")

        logger.info(f"Results saved to {output_path}")
