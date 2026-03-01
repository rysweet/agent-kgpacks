#!/usr/bin/env python3
"""Evaluate a single knowledge pack: Training baseline vs Pack (KG Agent).

Loads evaluation questions from a pack's eval/questions.jsonl, asks each
question to both a plain LLM (training baseline) and the KG Agent backed
by the pack database, then uses a judge model to score answers 0-10.

Usage:
    python scripts/eval_single_pack.py <pack_name> [--sample N]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from anthropic import Anthropic

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

ANSWER_MODEL = "claude-opus-4-6"
JUDGE_MODEL = "claude-opus-4-6"

# Match pack names: lowercase alphanumeric and hyphens, no path traversal
PACK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$")


def load_questions(path: Path, limit: int = 0) -> list[dict]:
    """Load evaluation questions from a JSONL file.

    Args:
        path: Path to the questions.jsonl file.
        limit: Maximum number of questions to load (0 = all).

    Returns:
        List of question dicts with 'question' and 'ground_truth' keys.
    """
    questions: list[dict] = []
    with open(path) as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            questions.append(json.loads(stripped))
            if limit and len(questions) >= limit:
                break
    return questions


def judge_score(
    client: Anthropic,
    question: str,
    expected: str,
    actual: str,
) -> int:
    """Ask the judge model to score an answer 0-10.

    Args:
        client: Anthropic API client.
        question: The evaluation question.
        expected: The ground-truth answer.
        actual: The answer to score.

    Returns:
        Integer score 0-10 (capped). Returns 0 on any failure.
    """
    prompt = (
        f"Score 0-10.\n"
        f"Q: {question}\n"
        f"Expected: {expected}\n"
        f"Actual: {actual}\n"
        f"Number only."
    )
    try:
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()
        digits = "".join(ch for ch in raw_text if ch.isdigit())[:2]
        if not digits:
            logger.warning("Judge returned no digits: %r", raw_text)
            return 0
        return min(10, int(digits))
    except Exception:
        logger.exception("Judge scoring failed for question: %s", question[:80])
        return 0


def validate_pack_name(name: str) -> str:
    """Validate pack name to prevent path traversal.

    Args:
        name: The pack name to validate.

    Returns:
        The validated pack name.

    Raises:
        SystemExit: If the name is invalid.
    """
    if not PACK_NAME_RE.match(name):
        print(json.dumps({"error": f"invalid pack name: {name!r}"}))
        sys.exit(1)
    return name


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a single knowledge pack")
    parser.add_argument("pack", help="Pack name (e.g. 'rust-expert')")
    parser.add_argument("--sample", type=int, default=0, help="Limit to N questions (0 = all)")
    args = parser.parse_args()

    pack_name = validate_pack_name(args.pack)
    db_path = Path(f"data/packs/{pack_name}/pack.db")
    questions_path = Path(f"data/packs/{pack_name}/eval/questions.jsonl")

    if not db_path.exists() or not questions_path.exists():
        print(json.dumps({"error": "missing pack database or questions file"}))
        sys.exit(1)

    questions = load_questions(questions_path, limit=args.sample)
    if not questions:
        print(json.dumps({"error": "no questions loaded"}))
        sys.exit(1)

    client = Anthropic()

    from wikigr.agent.kg_agent import KnowledgeGraphAgent

    training_scores: list[int] = []
    pack_scores: list[int] = []

    for question_data in questions:
        question_text = question_data.get("question", question_data.get("query", ""))
        expected_answer = question_data.get("ground_truth", question_data.get("answer", ""))

        # Training baseline: plain LLM answer
        try:
            response = client.messages.create(
                model=ANSWER_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": question_text}],
            )
            training_answer = response.content[0].text
        except Exception:
            logger.exception("Training baseline failed for: %s", question_text[:80])
            training_answer = ""

        training_scores.append(judge_score(client, question_text, expected_answer, training_answer))

        # Pack: KG Agent answer
        try:
            agent = KnowledgeGraphAgent(str(db_path), few_shot_path=str(questions_path))
            result = agent.query(question_text)
            pack_answer = result.get("answer", "")
            agent.close()
        except Exception:
            logger.exception("KG Agent failed for: %s", question_text[:80])
            pack_answer = ""

        pack_scores.append(judge_score(client, question_text, expected_answer, pack_answer))

    num_questions = len(questions)
    training_avg = round(sum(training_scores) / num_questions, 1)
    pack_avg = round(sum(pack_scores) / num_questions, 1)
    training_acc = round(sum(1 for s in training_scores if s >= 7) / num_questions * 100)
    pack_acc = round(sum(1 for s in pack_scores if s >= 7) / num_questions * 100)

    output = {
        "pack_name": pack_name,
        "n": num_questions,
        "training": {"avg": training_avg, "acc": training_acc, "scores": training_scores},
        "pack": {"avg": pack_avg, "acc": pack_acc, "scores": pack_scores},
        "delta": round(pack_avg - training_avg, 1),
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
