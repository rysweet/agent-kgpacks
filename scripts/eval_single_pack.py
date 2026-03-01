#!/usr/bin/env python3
"""Evaluate a single pack: Training vs Pack. For parallel execution."""
import argparse, json, logging, re, sys
from pathlib import Path
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
from anthropic import Anthropic

MODEL = "claude-opus-4-6"
JUDGE = "claude-haiku-4-5-20251001"
SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")

def load_questions(path, sample=0):
    questions = []
    with open(path) as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
                if sample and len(questions) >= sample:
                    break
    return questions

def judge_score(client, question, expected, actual):
    try:
        response = client.messages.create(
            model=JUDGE, max_tokens=10,
            messages=[{"role": "user", "content": f"Score 0-10 for accuracy.\nQ: {question}\nExpected: {expected}\nActual: {actual}\nReturn ONLY a number 0-10."}]
        )
        digits = "".join(c for c in response.content[0].text.strip() if c.isdigit())
        return min(10, int(digits[:2])) if digits else 0
    except Exception as e:
        logger.warning("Judge failed: %s", e)
        return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pack")
    parser.add_argument("--sample", type=int, default=0)
    args = parser.parse_args()

    if not SAFE_NAME.match(args.pack):
        print(json.dumps({"error": "invalid pack name"})); sys.exit(1)

    db_path = Path(f"data/packs/{args.pack}/pack.db")
    q_path = Path(f"data/packs/{args.pack}/eval/questions.jsonl")
    if not db_path.exists() or not q_path.exists():
        print(json.dumps({"error": "missing files"})); sys.exit(1)

    questions = load_questions(q_path, args.sample)
    if not questions:
        print(json.dumps({"error": "no questions"})); sys.exit(1)

    client = Anthropic()
    from wikigr.agent.kg_agent import KnowledgeGraphAgent

    training_scores, pack_scores = [], []
    for q in questions:
        question_text = q.get("question", q.get("query", ""))
        expected = q.get("ground_truth", q.get("answer", ""))

        # Training baseline
        try:
            r = client.messages.create(model=MODEL, max_tokens=512, messages=[{"role": "user", "content": question_text}])
            training_answer = r.content[0].text
        except Exception as e:
            logger.warning("Training API error: %s", e)
            training_answer = ""
        training_scores.append(judge_score(client, question_text, expected, training_answer))

        # Pack baseline
        try:
            agent = KnowledgeGraphAgent(str(db_path), few_shot_path=str(q_path))
            result = agent.query(question_text)
            pack_answer = result.get("answer", "")
            agent.close()
        except Exception as e:
            logger.warning("Pack query error: %s", e)
            pack_answer = str(e)
        pack_scores.append(judge_score(client, question_text, expected, pack_answer))

    n = len(questions)
    print(json.dumps({
        "pack_name": args.pack, "n": n,
        "training": {"avg": round(sum(training_scores)/n, 1), "acc": round(sum(1 for s in training_scores if s >= 7)/n*100), "scores": training_scores},
        "pack": {"avg": round(sum(pack_scores)/n, 1), "acc": round(sum(1 for s in pack_scores if s >= 7)/n*100), "scores": pack_scores},
        "delta": round(sum(pack_scores)/n - sum(training_scores)/n, 1),
    }))

if __name__ == "__main__":
    main()
