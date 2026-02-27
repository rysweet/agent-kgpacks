#!/usr/bin/env python3
"""Evaluate ALL knowledge packs: Baseline vs Enhanced accuracy comparison.

Runs evaluation across all packs with pack.db and questions.jsonl.

Usage:
    python scripts/run_all_packs_evaluation.py
    python scripts/run_all_packs_evaluation.py --sample 5  # 5 questions per pack
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

from anthropic import Anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"
JUDGE_MODEL = "claude-haiku-4-5-20251001"


def find_all_packs() -> list[dict]:
    """Find all packs with both pack.db and eval/questions.jsonl."""
    packs_dir = Path("data/packs")
    packs = []
    for pack_dir in sorted(packs_dir.iterdir()):
        if not pack_dir.is_dir():
            continue
        db_path = pack_dir / "pack.db"
        questions_path = pack_dir / "eval" / "questions.jsonl"
        if db_path.exists() and questions_path.exists():
            packs.append(
                {
                    "name": pack_dir.name,
                    "dir": pack_dir,
                    "db": db_path,
                    "questions": questions_path,
                }
            )
    return packs


def load_questions(path: Path, n: int) -> list[dict]:
    """Load first N questions from JSONL."""
    questions = []
    with open(path) as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
                if len(questions) >= n:
                    break
    return questions


def evaluate_training(client: Anthropic, questions: list[dict]) -> list[dict]:
    """Training baseline: Claude alone."""
    results = []
    for q in questions:
        start = time.time()
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": q["question"]}],
        )
        answer = response.content[0].text if response.content else ""
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "answer": answer,
                "source": "training",
                "latency_s": round(time.time() - start, 2),
            }
        )
    return results


def evaluate_pack(
    questions: list[dict],
    db_path: str,
    use_enhancements: bool,
    enable_reranker: bool = True,
    enable_multidoc: bool = True,
    enable_fewshot: bool = True,
    few_shot_path: str | None = None,
) -> list[dict]:
    """Pack evaluation with or without enhancements."""
    from wikigr.agent.kg_agent import KnowledgeGraphAgent

    agent = KnowledgeGraphAgent(
        str(db_path),
        use_enhancements=use_enhancements,
        few_shot_path=few_shot_path if use_enhancements else None,
        enable_reranker=enable_reranker,
        enable_multidoc=enable_multidoc,
        enable_fewshot=enable_fewshot,
    )
    results = []
    for q in questions:
        start = time.time()
        try:
            response = agent.query(q["question"])
            answer = response.get("answer", "")
        except Exception as e:
            answer = f"Error: {e}"
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "ground_truth": q["ground_truth"],
                "answer": answer,
                "source": "enhanced" if use_enhancements else "pack",
                "latency_s": round(time.time() - start, 2),
            }
        )
    agent.close()
    return results


def judge_answer(client: Anthropic, question: str, ground_truth: str, answer: str) -> dict:
    """Score answer 0-10."""
    prompt = f"""Score this answer 0-10.
Question: {question}
Ground Truth: {ground_truth}
Answer: {answer}

10=perfect, 7-9=mostly correct, 4-6=partial, 1-3=mostly wrong, 0=completely wrong.
Return ONLY JSON: {{"score": N, "reason": "brief"}}"""

    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text if response.content else '{"score": 0}'
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'"score"\s*:\s*(\d+)', text)
        return {"score": int(match.group(1)) if match else 0, "reason": text[:80]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=5, help="Questions per pack")
    parser.add_argument("--disable-reranker", action="store_true", help="Disable graph reranker")
    parser.add_argument("--disable-multidoc", action="store_true", help="Disable multi-doc")
    parser.add_argument("--disable-fewshot", action="store_true", help="Disable few-shot examples")
    args = parser.parse_args()

    packs = find_all_packs()
    if not packs:
        print("No packs found with pack.db + eval/questions.jsonl")
        sys.exit(1)

    print("=" * 70)
    print(f"ALL-PACKS EVALUATION ({len(packs)} packs, {args.sample} questions each)")
    print("=" * 70)
    for p in packs:
        print(f"  - {p['name']}")
    print()

    client = Anthropic()
    all_results = {}
    grand_scores = {"training": [], "pack": [], "enhanced": []}

    for pack in packs:
        print(f"\n{'=' * 70}")
        print(f"PACK: {pack['name']}")
        print(f"{'=' * 70}")

        questions = load_questions(pack["questions"], args.sample)
        if not questions:
            print("  No questions found, skipping")
            continue

        print(f"  Loaded {len(questions)} questions")

        # Run baselines
        print("  Running training baseline...")
        training = evaluate_training(client, questions)

        print("  Running pack baseline...")
        pack_results = evaluate_pack(questions, pack["db"], use_enhancements=False)

        print("  Running enhanced...")
        pack_few_shot = pack["dir"] / "eval" / "questions.jsonl"
        enhanced = evaluate_pack(
            questions,
            pack["db"],
            use_enhancements=True,
            enable_reranker=not args.disable_reranker,
            enable_multidoc=not args.disable_multidoc,
            enable_fewshot=not args.disable_fewshot,
            few_shot_path=str(pack_few_shot) if pack_few_shot.exists() else None,
        )

        # Judge all
        print("  Judging answers...")
        scores = {"training": [], "pack": [], "enhanced": []}
        for i, q in enumerate(questions):
            for results, key in [
                (training, "training"),
                (pack_results, "pack"),
                (enhanced, "enhanced"),
            ]:
                j = judge_answer(client, q["question"], q["ground_truth"], results[i]["answer"])
                scores[key].append(j["score"])
                results[i]["score"] = j["score"]

        # Pack summary
        for key in ["training", "pack", "enhanced"]:
            avg = sum(scores[key]) / len(scores[key]) if scores[key] else 0
            acc = (
                sum(1 for s in scores[key] if s >= 7) / len(scores[key]) * 100 if scores[key] else 0
            )
            print(f"  {key:12s}: avg={avg:.1f}/10, accuracy(≥7)={acc:.0f}%, scores={scores[key]}")
            grand_scores[key].extend(scores[key])

        all_results[pack["name"]] = {
            "training": training,
            "pack": pack_results,
            "enhanced": enhanced,
            "scores": scores,
        }

    # Grand summary
    print(f"\n{'=' * 70}")
    print("GRAND SUMMARY (ALL PACKS)")
    print(f"{'=' * 70}")
    for key in ["training", "pack", "enhanced"]:
        s = grand_scores[key]
        avg = sum(s) / len(s) if s else 0
        acc = sum(1 for x in s if x >= 7) / len(s) * 100 if s else 0
        print(f"  {key:12s}: avg={avg:.1f}/10, accuracy(≥7)={acc:.0f}% (n={len(s)})")

    pack_avg = sum(grand_scores["pack"]) / len(grand_scores["pack"]) if grand_scores["pack"] else 0
    enh_avg = (
        sum(grand_scores["enhanced"]) / len(grand_scores["enhanced"])
        if grand_scores["enhanced"]
        else 0
    )
    print(f"\n  IMPROVEMENT: Enhanced - Pack = {enh_avg - pack_avg:+.1f} points")

    # Save
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "packs_evaluated": len(packs),
        "sample_per_pack": args.sample,
        "grand_summary": {
            k: {
                "avg": sum(grand_scores[k]) / len(grand_scores[k]) if grand_scores[k] else 0,
                "accuracy": sum(1 for x in grand_scores[k] if x >= 7) / len(grand_scores[k]) * 100
                if grand_scores[k]
                else 0,
                "n": len(grand_scores[k]),
            }
            for k in ["training", "pack", "enhanced"]
        },
        "per_pack": {name: {"scores": data["scores"]} for name, data in all_results.items()},
    }
    output_path = Path("data/packs/all_packs_evaluation.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
