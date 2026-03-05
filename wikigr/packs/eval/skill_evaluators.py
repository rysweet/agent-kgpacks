"""Three-condition evaluators for skill delivery evaluation.

Implements:
  A) Baseline:        Claude alone (training knowledge only)
  B) Pack retrieval:  Claude + pre-fetched KG context in user message
  C) Skill delivery:  Claude + skill.md system prompt + KG tool_use
"""

import json
import logging
import re
import time
from pathlib import Path

from anthropic import Anthropic

from wikigr.packs.eval.kg_adapter import retrieve_from_pack
from wikigr.packs.eval.skill_models import CodingTask, TaskResult

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"
JUDGE_MODEL = "claude-opus-4-6"
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 5

# Anthropic pricing (per million tokens)
INPUT_COST_PER_MTOK = 15.0
OUTPUT_COST_PER_MTOK = 75.0

QUERY_TOOL = {
    "name": "query_knowledge_pack",
    "description": (
        "Query the domain knowledge graph for relevant information. "
        "Returns sources, entities, facts, and a synthesized answer "
        "from the knowledge pack's graph database."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Natural language query to search the knowledge graph",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (1-10)",
                "default": 5,
            },
        },
        "required": ["question"],
    },
}

TASK_JUDGE_PROMPT = """You are evaluating code/technical output quality. Score 0-10.

Task: {prompt}
Expected approach: {ground_truth_description}
Reference code (first 2000 chars):
```
{ground_truth_code}
```

Actual output (first 3000 chars):
{actual_output}

Score criteria:
- 10: Correct, complete, idiomatic, handles edge cases
- 7-9: Functionally correct, may miss minor idioms or edge cases
- 4-6: Partially correct approach, significant gaps or errors
- 1-3: Wrong approach, major errors, would not compile/run
- 0: No relevant output or completely wrong

Consider: correctness, completeness, API accuracy, idioms.

Return ONLY JSON: {{"score": N, "reason": "brief explanation"}}"""


def _calc_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * INPUT_COST_PER_MTOK + output_tokens * OUTPUT_COST_PER_MTOK) / 1_000_000


def evaluate_baseline(client: Anthropic, task: CodingTask) -> TaskResult:
    """Condition A: Claude with training knowledge only."""
    start = time.perf_counter()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": task.prompt}],
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    text = response.content[0].text if response.content else ""
    cost = _calc_cost(response.usage.input_tokens, response.usage.output_tokens)

    return TaskResult(
        task_id=task.id,
        condition="baseline",
        raw_output=text,
        latency_ms=elapsed_ms,
        cost_usd=cost,
        tool_calls_made=0,
    )


def evaluate_pack_retrieval(client: Anthropic, task: CodingTask, pack_path: Path) -> TaskResult:
    """Condition B: Claude + pre-fetched KG context in user message."""
    start = time.perf_counter()

    # Retrieve context from pack
    try:
        context = retrieve_from_pack(task.prompt, pack_path, top_k=5)
    except Exception as e:
        logger.warning(f"KG retrieval failed for {task.id}: {e}")
        context = "Knowledge graph context unavailable."

    augmented_prompt = (
        f"You have the following reference material from a knowledge graph:\n\n"
        f"{context}\n\n---\n\nTask:\n{task.prompt}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": augmented_prompt}],
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    text = response.content[0].text if response.content else ""
    cost = _calc_cost(response.usage.input_tokens, response.usage.output_tokens)

    return TaskResult(
        task_id=task.id,
        condition="pack_retrieval",
        raw_output=text,
        latency_ms=elapsed_ms,
        cost_usd=cost,
        tool_calls_made=0,
    )


def evaluate_skill_delivery(
    client: Anthropic,
    task: CodingTask,
    pack_path: Path,
    skill_md_content: str,
) -> TaskResult:
    """Condition C: Skill delivery via system prompt + tool_use."""
    start = time.perf_counter()
    messages = [{"role": "user", "content": task.prompt}]
    tool_calls_made = 0
    total_input = 0
    total_output = 0

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=skill_md_content,
            tools=[QUERY_TOOL],
            messages=messages,
        )
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens

        if response.stop_reason == "tool_use":
            # Handle ALL tool_use blocks in this response
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            tool_results = []
            for tool_block in tool_blocks:
                tool_calls_made += 1
                question = tool_block.input.get("question", task.prompt)
                max_results = tool_block.input.get("max_results", 5)
                try:
                    kg_result = retrieve_from_pack(question, pack_path, top_k=max_results)
                except Exception as e:
                    kg_result = f"Error querying knowledge pack: {e}"
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": kg_result,
                    }
                )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    elapsed_ms = (time.perf_counter() - start) * 1000
    final_text = "".join(b.text for b in response.content if hasattr(b, "text"))
    cost = _calc_cost(total_input, total_output)

    return TaskResult(
        task_id=task.id,
        condition="skill_delivery",
        raw_output=final_text,
        latency_ms=elapsed_ms,
        cost_usd=cost,
        tool_calls_made=tool_calls_made,
    )


def judge_task_output(client: Anthropic, task: CodingTask, actual_output: str) -> tuple[int, str]:
    """Judge task output quality, returning (score, reason)."""
    prompt = TASK_JUDGE_PROMPT.format(
        prompt=task.prompt,
        ground_truth_description=task.ground_truth_description,
        ground_truth_code=task.ground_truth_code[:2000],
        actual_output=actual_output[:3000],
    )
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text if response.content else '{"score": 0}'
    try:
        result = json.loads(text)
        return min(10, int(result["score"])), result.get("reason", "")
    except (json.JSONDecodeError, KeyError, ValueError):
        match = re.search(r'"score"\s*:\s*(\d+)', text)
        if match:
            return min(10, int(match.group(1))), text[:100]
        match = re.search(r"\b(\d+)\b", text)
        return min(10, int(match.group(1))) if match else 0, text[:100]


def compute_composite_score(result: TaskResult) -> float:
    """Compute composite score from judge + validation (0.0-1.0)."""
    judge_norm = result.judge_score / 10.0
    v = result.validation

    if v is None:
        return judge_norm

    syntax_score = 1.0 if v.syntax_valid else 0.0

    required_score = (
        sum(v.contains_required.values()) / len(v.contains_required) if v.contains_required else 1.0
    )
    forbidden_score = (
        1.0 - sum(v.contains_forbidden.values()) / len(v.contains_forbidden)
        if v.contains_forbidden
        else 1.0
    )
    construct_score = (
        sum(v.constructs_found.values()) / len(v.constructs_found) if v.constructs_found else 1.0
    )

    score = (
        0.40 * judge_norm
        + 0.15 * syntax_score
        + 0.15 * required_score
        + 0.10 * forbidden_score
        + 0.10 * construct_score
    )

    if v.execution_passed is not None:
        score += 0.10 * (1.0 if v.execution_passed else 0.0)
    else:
        score += 0.10 * judge_norm  # redistribute to judge

    return round(score, 4)
