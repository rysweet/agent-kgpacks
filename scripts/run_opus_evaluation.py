#!/usr/bin/env python3.10
"""
Run evaluation for Knowledge Packs with baseline and enhanced modes.

Usage:
    python3.10 scripts/run_opus_evaluation.py --pack physics-expert --baseline
    python3.10 scripts/run_opus_evaluation.py --pack physics-expert --enhanced
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from wikigr.agent import KnowledgeGraphAgent
from wikigr.packs.eval.questions import load_questions_from_pack
from wikigr.packs.eval.metrics import calculate_accuracy
from wikigr.packs.eval.runner import EvaluationRunner
from wikigr.packs.eval.baselines import TrainingBaselineEvaluator, KnowledgePackEvaluator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run Knowledge Pack evaluation")
    parser.add_argument("--pack", required=True, help="Pack name (e.g., physics-expert)")
    parser.add_argument("--baseline", action="store_true", help="Run baseline evaluation")
    parser.add_argument("--enhanced", action="store_true", help="Run enhanced evaluation")
    parser.add_argument("--db-path", help="Override database path")
    parser.add_argument("--output", help="Output results file")

    args = parser.parse_args()

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Determine pack path
    pack_path = Path(f"data/packs/{args.pack}")
    if not pack_path.exists():
        logger.error(f"Pack not found: {pack_path}")
        sys.exit(1)

    # Load questions
    try:
        questions_file = pack_path / "eval" / "questions.json"
        if not questions_file.exists():
            logger.error(f"Questions file not found: {questions_file}")
            sys.exit(1)

        questions = load_questions_from_pack(str(pack_path))
        logger.info(f"Loaded {len(questions)} questions from {args.pack}")
    except Exception as e:
        logger.error(f"Failed to load questions: {e}")
        sys.exit(1)

    # Determine database path
    if args.db_path:
        db_path = args.db_path
    else:
        db_path = str(pack_path / f"{args.pack}.db")

    if not Path(db_path).exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    # Run evaluation
    results = {}

    if args.baseline:
        logger.info("Running baseline evaluation (training data only)...")
        evaluator = TrainingBaselineEvaluator(api_key=api_key)
        runner = EvaluationRunner(evaluator, questions)
        baseline_results = runner.run()

        accuracy = calculate_accuracy(baseline_results, questions)
        results["baseline"] = {
            "accuracy": accuracy,
            "total_questions": len(questions),
            "correct": int(accuracy * len(questions)),
        }

        logger.info(f"Baseline accuracy: {accuracy:.2%}")

    if args.enhanced:
        logger.info("Running enhanced evaluation (with Phase 1 enhancements)...")

        # Initialize agent with enhancements
        few_shot_path = "data/few_shot/physics_examples.json"
        agent = KnowledgeGraphAgent(
            db_path=db_path,
            anthropic_api_key=api_key,
            few_shot_examples_path=few_shot_path if Path(few_shot_path).exists() else None,
        )

        # Evaluate each question with enhancements
        correct = 0
        for question in questions:
            try:
                result = agent.query(question.text, use_enhancements=True)
                # Simple correctness check (exact match or containment)
                if question.expected_answer.lower() in result["answer"].lower():
                    correct += 1
            except Exception as e:
                logger.warning(f"Query failed for question {question.id}: {e}")

        agent.close()

        accuracy = correct / len(questions)
        results["enhanced"] = {
            "accuracy": accuracy,
            "total_questions": len(questions),
            "correct": correct,
        }

        logger.info(f"Enhanced accuracy: {accuracy:.2%}")

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results written to {args.output}")
    else:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
