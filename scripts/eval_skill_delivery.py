#!/usr/bin/env python3
"""Evaluate skill delivery effectiveness for knowledge packs.

Compares three conditions:
  A) Baseline:        Claude alone (training knowledge only)
  B) Pack retrieval:  Claude + pre-fetched KG context
  C) Skill delivery:  Claude + skill.md system prompt + KG tool

Usage:
    python scripts/eval_skill_delivery.py rust-expert
    python scripts/eval_skill_delivery.py --all --sample 3
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))

from wikigr.packs.eval.skill_evaluators import (  # noqa: E402
    compute_composite_score,
    evaluate_baseline,
    evaluate_pack_retrieval,
    evaluate_skill_delivery,
    judge_task_output,
)
from wikigr.packs.eval.skill_models import (  # noqa: E402
    CodingTask,
    ConditionSummary,
    SkillDeliveryResult,
    TaskValidation,
)
from wikigr.packs.eval.skill_validators import validate_task_output  # noqa: E402
from wikigr.packs.manifest import PACK_NAME_RE  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PACKS_DIR = Path("data/packs")


def load_tasks(path: Path, limit: int = 0) -> list[CodingTask]:
    """Load coding tasks from JSONL."""
    tasks = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            v = d.get("validation", {})
            task = CodingTask(
                id=d["id"],
                pack_name=d["pack_name"],
                task_type=d["task_type"],
                difficulty=d["difficulty"],
                prompt=d["prompt"],
                ground_truth_code=d["ground_truth_code"],
                ground_truth_description=d["ground_truth_description"],
                validation=TaskValidation(
                    language=v.get("language", "python"),
                    must_contain=v.get("must_contain", []),
                    must_not_contain=v.get("must_not_contain", []),
                    expected_constructs=v.get("expected_constructs", []),
                    execution_test=v.get("execution_test"),
                ),
                tags=d.get("tags", []),
            )
            tasks.append(task)
            if limit and len(tasks) >= limit:
                break
    return tasks


def load_skill_md(pack_path: Path) -> str:
    """Load skill.md content, generating it if needed."""
    skill_path = pack_path / "skill.md"
    if skill_path.exists():
        return skill_path.read_text()
    from wikigr.packs.manifest import load_manifest
    from wikigr.packs.skill_template import generate_skill_md

    manifest = load_manifest(pack_path)
    return generate_skill_md(manifest, pack_path / "kg_config.json")


def find_pilot_packs() -> list[str]:
    """Find packs that have eval/tasks.jsonl."""
    packs = []
    for pack_dir in sorted(PACKS_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue
        if (pack_dir / "eval" / "tasks.jsonl").exists() and (pack_dir / "pack.db").exists():
            packs.append(pack_dir.name)
    return packs


def summarize_condition(results: list) -> ConditionSummary:
    """Compute aggregate metrics for one condition."""
    n = len(results)
    if n == 0:
        return ConditionSummary(0, 0, 0, 0, 0, 0, 0)

    composites = [compute_composite_score(r) for r in results]
    syntax_passes = sum(1 for r in results if r.validation and r.validation.syntax_valid)

    return ConditionSummary(
        avg_judge_score=round(sum(r.judge_score for r in results) / n, 2),
        avg_composite_score=round(sum(composites) / n, 4),
        syntax_pass_rate=round(syntax_passes / n, 2),
        accuracy_gte7=round(sum(1 for r in results if r.judge_score >= 7) / n, 2),
        avg_latency_ms=round(sum(r.latency_ms for r in results) / n, 0),
        total_cost_usd=round(sum(r.cost_usd for r in results), 4),
        avg_tool_calls=round(sum(r.tool_calls_made for r in results) / n, 1),
    )


def run_single_pack(client: Anthropic, pack_name: str, sample: int) -> SkillDeliveryResult:
    """Run skill delivery evaluation for one pack."""
    pack_path = PACKS_DIR / pack_name
    tasks_path = pack_path / "eval" / "tasks.jsonl"

    tasks = load_tasks(tasks_path, limit=sample)
    skill_md = load_skill_md(pack_path)

    logger.info(f"Evaluating {pack_name}: {len(tasks)} tasks, 3 conditions")

    conditions: dict[str, list] = {"baseline": [], "pack_retrieval": [], "skill_delivery": []}

    for i, task in enumerate(tasks, 1):
        logger.info(f"  Task {i}/{len(tasks)}: {task.id} ({task.task_type}/{task.difficulty})")

        # Condition A: Baseline
        logger.info("    [A] Baseline...")
        result_a = evaluate_baseline(client, task)
        result_a.validation = validate_task_output(task, result_a.raw_output)
        score, reason = judge_task_output(client, task, result_a.raw_output)
        result_a.judge_score = score
        result_a.judge_reason = reason
        conditions["baseline"].append(result_a)

        # Condition B: Pack retrieval
        logger.info("    [B] Pack retrieval...")
        result_b = evaluate_pack_retrieval(client, task, pack_path)
        result_b.validation = validate_task_output(task, result_b.raw_output)
        score, reason = judge_task_output(client, task, result_b.raw_output)
        result_b.judge_score = score
        result_b.judge_reason = reason
        conditions["pack_retrieval"].append(result_b)

        # Condition C: Skill delivery
        logger.info("    [C] Skill delivery...")
        result_c = evaluate_skill_delivery(client, task, pack_path, skill_md)
        result_c.validation = validate_task_output(task, result_c.raw_output)
        score, reason = judge_task_output(client, task, result_c.raw_output)
        result_c.judge_score = score
        result_c.judge_reason = reason
        conditions["skill_delivery"].append(result_c)

        logger.info(
            f"    Scores: A={result_a.judge_score} B={result_b.judge_score} "
            f"C={result_c.judge_score} (tool_calls={result_c.tool_calls_made})"
        )

    summary = {name: summarize_condition(results) for name, results in conditions.items()}

    return SkillDeliveryResult(
        pack_name=pack_name,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        tasks_evaluated=len(tasks),
        conditions=conditions,
        summary=summary,
    )


def print_results(result: SkillDeliveryResult) -> None:
    """Print formatted results to stdout."""
    print(f"\n=== {result.pack_name} ({result.tasks_evaluated} tasks) ===")
    for name in ("baseline", "pack_retrieval", "skill_delivery"):
        s = result.summary[name]
        print(
            f"  {name:18s}: avg_judge={s.avg_judge_score:.1f}, "
            f"composite={s.avg_composite_score:.2f}, "
            f"syntax_pass={s.syntax_pass_rate:.0%}, "
            f"accuracy={s.accuracy_gte7:.0%}, "
            f"tool_calls={s.avg_tool_calls:.1f}"
        )
    b = result.summary["baseline"]
    s = result.summary["skill_delivery"]
    p = result.summary["pack_retrieval"]
    print(
        f"\n  SKILL vs BASELINE: {s.avg_judge_score - b.avg_judge_score:+.1f} judge, "
        f"{s.avg_composite_score - b.avg_composite_score:+.2f} composite"
    )
    print(
        f"  SKILL vs PACK:     {s.avg_judge_score - p.avg_judge_score:+.1f} judge, "
        f"{s.avg_composite_score - p.avg_composite_score:+.2f} composite"
    )


def save_results(result: SkillDeliveryResult, pack_path: Path) -> None:
    """Save results to JSON."""
    out_path = pack_path / "eval" / "skill_delivery_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "pack_name": result.pack_name,
        "timestamp": result.timestamp,
        "tasks_evaluated": result.tasks_evaluated,
        "summary": {
            name: {
                "avg_judge_score": s.avg_judge_score,
                "avg_composite_score": s.avg_composite_score,
                "syntax_pass_rate": s.syntax_pass_rate,
                "accuracy_gte7": s.accuracy_gte7,
                "avg_latency_ms": s.avg_latency_ms,
                "total_cost_usd": s.total_cost_usd,
                "avg_tool_calls": s.avg_tool_calls,
            }
            for name, s in result.summary.items()
        },
        "per_task": [
            {
                "task_id": task_id,
                "baseline": {"judge_score": b.judge_score, "composite": compute_composite_score(b)},
                "pack_retrieval": {
                    "judge_score": p.judge_score,
                    "composite": compute_composite_score(p),
                },
                "skill_delivery": {
                    "judge_score": sk.judge_score,
                    "composite": compute_composite_score(sk),
                    "tool_calls": sk.tool_calls_made,
                },
            }
            for task_id, b, p, sk in zip(
                [t.task_id for t in result.conditions["baseline"]],
                result.conditions["baseline"],
                result.conditions["pack_retrieval"],
                result.conditions["skill_delivery"],
            )
        ],
    }

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    logger.info(f"Results saved to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate skill delivery effectiveness")
    parser.add_argument("pack", nargs="?", help="Pack name to evaluate")
    parser.add_argument("--all", action="store_true", help="Evaluate all packs with tasks.jsonl")
    parser.add_argument("--sample", type=int, default=5, help="Max tasks per pack (default: 5)")
    args = parser.parse_args()

    if not args.pack and not args.all:
        parser.error("Specify a pack name or --all")

    client = Anthropic()

    if args.all:
        packs = find_pilot_packs()
        if not packs:
            print("No packs found with eval/tasks.jsonl", file=sys.stderr)
            sys.exit(1)
        logger.info(f"Found {len(packs)} packs with tasks: {', '.join(packs)}")
    else:
        if not PACK_NAME_RE.match(args.pack):
            print(f"Invalid pack name: {args.pack}", file=sys.stderr)
            sys.exit(1)
        packs = [args.pack]

    for pack_name in packs:
        pack_path = PACKS_DIR / pack_name
        if not (pack_path / "eval" / "tasks.jsonl").exists():
            logger.warning(f"Skipping {pack_name}: no eval/tasks.jsonl")
            continue

        result = run_single_pack(client, pack_name, args.sample)
        print_results(result)
        save_results(result, pack_path)


if __name__ == "__main__":
    main()
