#!/usr/bin/env python3
"""Run full Opus 4.6 evaluation with WebFetch baseline."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from wikigr.packs.eval.models import Question
from wikigr.packs.eval.runner import EvalRunner

# Load questions
questions = []
with open("data/packs/physics-expert/eval/questions.jsonl") as f:
    for line in f:
        questions.append(Question(**json.loads(line)))

print("🚀 OPUS 4.6 EVALUATION")
print(f"Questions: {len(questions)}")
print("Baseline: Claude Opus 4.6 (training + webfetch)")
print("Pack: Claude Opus 4.6 (knowledge graph)")
print()

runner = EvalRunner(Path("data/packs/physics-expert"))
result = runner.run_evaluation(questions)

# Save results
output = Path("data/packs/physics-expert/eval/results_opus46.json")
with open(output, "w") as f:
    json.dump(result.to_dict(), f, indent=2)

print("\n📊 RESULTS:")
print(f"WebFetch Baseline: {result.webfetch_baseline.accuracy:.1%} accuracy")
print(f"Knowledge Pack: {result.knowledge_pack.accuracy:.1%} accuracy")
print(f"WebFetch Cost: ${result.webfetch_baseline.total_cost_usd:.2f}")
print(f"Pack Cost: ${result.knowledge_pack.total_cost_usd:.2f}")
print(f"\nPack surpasses WebFetch: {result.surpasses_webfetch}")
print(f"\n✓ Results saved to {output}")
