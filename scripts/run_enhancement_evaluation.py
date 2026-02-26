#!/usr/bin/env python3
"""Evaluate Phase 1 Enhancements: Baseline vs Enhanced accuracy comparison.

Runs 10-question sample evaluation comparing:
1. Training baseline (Claude alone)
2. Standard pack (KG Agent without enhancements)
3. Enhanced pack (KG Agent with GraphReranker + MultiDocSynthesizer + FewShotManager)

Usage:
    python scripts/run_enhancement_evaluation.py
"""

import argparse
import json
import logging
import time
from pathlib import Path

from anthropic import Anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PACK_DIR = Path("data/packs/physics-expert")
QUESTIONS_FILE = PACK_DIR / "eval" / "questions.jsonl"
SAMPLE_SIZE = 10  # Evaluate 10 questions per baseline
MODEL = "claude-sonnet-4-5-20250929"


def load_sample_questions(path: Path, n: int) -> list[dict]:
    """Load first N questions from JSONL file."""
    questions = []
    with open(path) as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
                if len(questions) >= n:
                    break
    return questions


def evaluate_training_baseline(client: Anthropic, questions: list[dict]) -> list[dict]:
    """Baseline 1: Claude answers from training data only."""
    results = []
    for q in questions:
        start = time.time()
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": q["question"]}],
        )
        answer = response.content[0].text if response.content else ""
        latency = time.time() - start
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "answer": answer,
                "source": "training_baseline",
                "latency_s": round(latency, 2),
            }
        )
        logger.info(f"  Training: {q['id']} ({latency:.1f}s)")
    return results


def evaluate_pack_baseline(questions: list[dict]) -> list[dict]:
    """Baseline 2: KG Agent without enhancements."""
    from wikigr.agent.kg_agent import KnowledgeGraphAgent

    db_path = str(PACK_DIR / "pack.db")
    agent = KnowledgeGraphAgent(db_path, use_enhancements=False)

    results = []
    for q in questions:
        start = time.time()
        try:
            response = agent.query(q["question"])
            answer = response.get("answer", "")
        except Exception as e:
            answer = f"Error: {e}"
        latency = time.time() - start
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "answer": answer,
                "source": "pack_baseline",
                "latency_s": round(latency, 2),
            }
        )
        logger.info(f"  Pack: {q['id']} ({latency:.1f}s)")

    agent.close()
    return results


def evaluate_enhanced(questions: list[dict], args: argparse.Namespace) -> list[dict]:
    """Enhanced: KG Agent WITH Phase 1 enhancements."""
    from wikigr.agent.kg_agent import KnowledgeGraphAgent

    db_path = str(PACK_DIR / "pack.db")
    agent = KnowledgeGraphAgent(
        db_path,
        use_enhancements=True,
        few_shot_path="data/few_shot/physics_examples.json",
        enable_reranker=not args.disable_reranker,
        enable_multidoc=not args.disable_multidoc,
        enable_fewshot=not args.disable_fewshot,
    )

    results = []
    for q in questions:
        start = time.time()
        try:
            response = agent.query(q["question"])
            answer = response.get("answer", "")
        except Exception as e:
            answer = f"Error: {e}"
        latency = time.time() - start
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "answer": answer,
                "source": "enhanced",
                "latency_s": round(latency, 2),
            }
        )
        logger.info(f"  Enhanced: {q['id']} ({latency:.1f}s)")

    agent.close()
    return results


def judge_answer(client: Anthropic, question: str, ground_truth: str, answer: str) -> dict:
    """Use Claude to judge answer quality (0-10 scale)."""
    prompt = f"""You are an evaluation judge. Score this answer on a 0-10 scale.

Question: {question}
Ground Truth: {ground_truth}
Answer to evaluate: {answer}

Score criteria:
- 10: Perfect match to ground truth
- 7-9: Mostly correct, may miss minor details
- 4-6: Partially correct, significant gaps
- 1-3: Mostly wrong or irrelevant
- 0: Completely wrong or no answer

Respond with ONLY a JSON object: {{"score": N, "reason": "brief explanation"}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text if response.content else '{"score": 0, "reason": "empty"}'
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract score from text
        import re

        match = re.search(r'"score"\s*:\s*(\d+)', text)
        score = int(match.group(1)) if match else 0
        return {"score": score, "reason": text[:100]}


def main():
    parser = argparse.ArgumentParser(description="Evaluate Phase 1 enhancements")
    parser.add_argument("--disable-reranker", action="store_true", help="Disable graph reranker")
    parser.add_argument("--disable-multidoc", action="store_true", help="Disable multi-doc")
    parser.add_argument("--disable-fewshot", action="store_true", help="Disable few-shot examples")
    args = parser.parse_args()

    print("=" * 70)
    print("PHASE 1 ENHANCEMENT EVALUATION")
    print(f"Pack: {PACK_DIR}")
    print(f"Questions: {SAMPLE_SIZE} (sample)")
    print(f"Model: {MODEL}")
    disabled = [
        c for c, v in [
            ("reranker", args.disable_reranker),
            ("multidoc", args.disable_multidoc),
            ("fewshot", args.disable_fewshot),
        ] if v
    ]
    if disabled:
        print(f"Disabled components: {', '.join(disabled)}")
    print("=" * 70)

    client = Anthropic()
    questions = load_sample_questions(QUESTIONS_FILE, SAMPLE_SIZE)
    print(f"\nLoaded {len(questions)} questions\n")

    # Run all three baselines
    print("--- Baseline 1: Training Only ---")
    training_results = evaluate_training_baseline(client, questions)

    print("\n--- Baseline 2: Pack (No Enhancements) ---")
    pack_results = evaluate_pack_baseline(questions)

    print("\n--- Baseline 3: Enhanced (Phase 1 Enhancements) ---")
    enhanced_results = evaluate_enhanced(questions, args)

    # Judge all answers
    print("\n--- Judging Answers ---")
    all_scores = {"training": [], "pack": [], "enhanced": []}

    for i, q in enumerate(questions):
        for _source, results, key in [
            ("Training", training_results, "training"),
            ("Pack", pack_results, "pack"),
            ("Enhanced", enhanced_results, "enhanced"),
        ]:
            judgment = judge_answer(client, q["question"], q["ground_truth"], results[i]["answer"])
            all_scores[key].append(judgment["score"])
            results[i]["score"] = judgment["score"]
            results[i]["reason"] = judgment["reason"]

        logger.info(
            f"  {q['id']}: Training={all_scores['training'][-1]}, "
            f"Pack={all_scores['pack'][-1]}, Enhanced={all_scores['enhanced'][-1]}"
        )

    # Calculate and display results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    for key, label in [
        ("training", "Training Baseline"),
        ("pack", "Pack (No Enhancements)"),
        ("enhanced", "Enhanced (Phase 1)"),
    ]:
        scores = all_scores[key]
        avg = sum(scores) / len(scores) if scores else 0
        accuracy = sum(1 for s in scores if s >= 7) / len(scores) * 100 if scores else 0
        print(f"\n{label}:")
        print(f"  Average Score: {avg:.1f}/10")
        print(f"  Accuracy (≥7): {accuracy:.0f}%")
        print(f"  Scores: {scores}")

    # Improvement delta
    pack_avg = sum(all_scores["pack"]) / len(all_scores["pack"])
    enhanced_avg = sum(all_scores["enhanced"]) / len(all_scores["enhanced"])
    delta = enhanced_avg - pack_avg
    print(f"\n{'=' * 70}")
    print(f"IMPROVEMENT: Enhanced - Pack = {delta:+.1f} points")
    print(f"{'=' * 70}")

    # Save results
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample_size": SAMPLE_SIZE,
        "model": MODEL,
        "results": {
            "training": training_results,
            "pack": pack_results,
            "enhanced": enhanced_results,
        },
        "summary": {
            "training_avg": sum(all_scores["training"]) / len(all_scores["training"]),
            "pack_avg": pack_avg,
            "enhanced_avg": enhanced_avg,
            "improvement_delta": delta,
            "training_accuracy": sum(1 for s in all_scores["training"] if s >= 7)
            / len(all_scores["training"])
            * 100,
            "pack_accuracy": sum(1 for s in all_scores["pack"] if s >= 7)
            / len(all_scores["pack"])
            * 100,
            "enhanced_accuracy": sum(1 for s in all_scores["enhanced"] if s >= 7)
            / len(all_scores["enhanced"])
            * 100,
        },
    }

    output_path = PACK_DIR / "eval" / "enhancement_comparison.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
