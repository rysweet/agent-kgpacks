"""Example: Running a complete evaluation on a physics knowledge pack.

This script demonstrates how to:
1. Load evaluation questions
2. Run three-baseline evaluation
3. Compare results and determine if pack surpasses baselines
4. Save results for analysis
"""

import sys
from pathlib import Path

from wikigr.packs.eval import EvalRunner, load_questions_jsonl, validate_questions


def main():
    """Run complete physics pack evaluation."""
    # Check command line arguments
    if len(sys.argv) < 3:
        print("Usage: python run_physics_evaluation.py <pack_dir> <questions_file>")
        print("Example: python run_physics_evaluation.py ./packs/physics-expert ./questions.jsonl")
        sys.exit(1)

    pack_dir = Path(sys.argv[1])
    questions_file = Path(sys.argv[2])

    # Validate inputs
    if not pack_dir.exists():
        print(f"Error: Pack directory not found: {pack_dir}")
        sys.exit(1)

    if not questions_file.exists():
        print(f"Error: Questions file not found: {questions_file}")
        sys.exit(1)

    # Load and validate questions
    print(f"Loading questions from {questions_file}...")
    questions = load_questions_jsonl(questions_file)
    print(f"Loaded {len(questions)} questions")

    errors = validate_questions(questions)
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    # Run evaluation
    print("\nStarting three-baseline evaluation...")
    print("This will take a few minutes...")
    print("-" * 60)

    runner = EvalRunner(pack_dir)
    result = runner.run_evaluation(questions)

    # Display results
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"\nPack: {result.pack_name}")
    print(f"Questions tested: {result.questions_tested}")
    print(f"Timestamp: {result.timestamp}")

    print("\n--- Training Baseline ---")
    print(f"Accuracy: {result.training_baseline.accuracy:.2f}")
    print(f"Hallucination Rate: {result.training_baseline.hallucination_rate:.2f}")
    print(f"Citation Quality: {result.training_baseline.citation_quality:.2f}")
    print(f"Avg Latency: {result.training_baseline.avg_latency_ms:.0f}ms")
    print(f"Total Cost: ${result.training_baseline.total_cost_usd:.4f}")

    print("\n--- Web Search Baseline ---")
    print(f"Accuracy: {result.web_search_baseline.accuracy:.2f}")
    print(f"Hallucination Rate: {result.web_search_baseline.hallucination_rate:.2f}")
    print(f"Citation Quality: {result.web_search_baseline.citation_quality:.2f}")
    print(f"Avg Latency: {result.web_search_baseline.avg_latency_ms:.0f}ms")
    print(f"Total Cost: ${result.web_search_baseline.total_cost_usd:.4f}")

    print("\n--- Knowledge Pack ---")
    print(f"Accuracy: {result.knowledge_pack.accuracy:.2f}")
    print(f"Hallucination Rate: {result.knowledge_pack.hallucination_rate:.2f}")
    print(f"Citation Quality: {result.knowledge_pack.citation_quality:.2f}")
    print(f"Avg Latency: {result.knowledge_pack.avg_latency_ms:.0f}ms")
    print(f"Total Cost: ${result.knowledge_pack.total_cost_usd:.4f}")

    print("\n--- Comparison ---")
    if result.surpasses_training:
        print("✓ Knowledge pack SURPASSES training baseline")
    else:
        print("✗ Knowledge pack does NOT surpass training baseline")

    if result.surpasses_web:
        print("✓ Knowledge pack SURPASSES web search baseline")
    else:
        print("✗ Knowledge pack does NOT surpass web search baseline")

    # Save results
    eval_dir = pack_dir / "eval"
    eval_dir.mkdir(exist_ok=True)
    output_file = eval_dir / f"results_{result.timestamp.replace(':', '-')}.json"

    runner.save_results(result, output_file)
    print(f"\nResults saved to: {output_file}")

    # Exit with appropriate code
    if result.surpasses_training and result.surpasses_web:
        print("\n✓ Pack meets quality bar!")
        sys.exit(0)
    else:
        print("\n✗ Pack needs improvement")
        sys.exit(1)


if __name__ == "__main__":
    main()
