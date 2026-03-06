"""Tests for scripts/eval_skill_delivery.py — load_tasks, load_skill_md, summarize_condition."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from wikigr.packs.eval.skill_models import (  # noqa: E402
    ConditionSummary,
    TaskResult,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# Import the module under test by file path to avoid package resolution issues.
# ---------------------------------------------------------------------------
_SCRIPT_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "eval_skill_delivery.py"
_spec = importlib.util.spec_from_file_location("eval_skill_delivery", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["eval_skill_delivery"] = _mod
_spec.loader.exec_module(_mod)

load_tasks = _mod.load_tasks
load_skill_md = _mod.load_skill_md
summarize_condition = _mod.summarize_condition

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_TASK = {
    "id": "rust-001",
    "pack_name": "rust-expert",
    "task_type": "code_gen",
    "difficulty": "medium",
    "prompt": "Write a function that sorts a vector of integers.",
    "ground_truth_code": "fn sort(v: &mut Vec<i32>) { v.sort(); }",
    "ground_truth_description": "Use Vec::sort for in-place sorting.",
    "validation": {
        "language": "rust",
        "must_contain": ["fn ", "sort"],
        "must_not_contain": ["unsafe"],
        "expected_constructs": ["function_definition"],
        "execution_test": None,
    },
    "tags": ["sorting", "vectors"],
}

SAMPLE_TASK_MINIMAL = {
    "id": "py-001",
    "pack_name": "python-expert",
    "task_type": "explain",
    "difficulty": "easy",
    "prompt": "Explain list comprehensions.",
    "ground_truth_code": "[x for x in range(10)]",
    "ground_truth_description": "Basic list comprehension syntax.",
}


def _make_task_jsonl(tmp_path: Path, tasks: list[dict]) -> Path:
    """Write tasks to a JSONL file and return the path."""
    path = tmp_path / "tasks.jsonl"
    with open(path, "w") as f:
        for t in tasks:
            f.write(json.dumps(t) + "\n")
    return path


def _make_task_result(
    task_id: str = "t1",
    condition: str = "baseline",
    judge_score: int = 7,
    latency_ms: float = 500.0,
    cost_usd: float = 0.01,
    tool_calls: int = 0,
    syntax_valid: bool = True,
    validation: ValidationResult | None = None,
) -> TaskResult:
    if validation is None:
        validation = ValidationResult(
            syntax_valid=syntax_valid,
            syntax_errors=[],
            contains_required={"fn": True},
            contains_forbidden={},
            constructs_found={"function_definition": True},
            execution_passed=None,
            execution_output=None,
        )
    return TaskResult(
        task_id=task_id,
        condition=condition,
        raw_output="some code output",
        judge_score=judge_score,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        tool_calls_made=tool_calls,
        validation=validation,
    )


# ---------------------------------------------------------------------------
# load_tasks
# ---------------------------------------------------------------------------


class TestLoadTasks:
    def test_loads_single_task(self, tmp_path: Path) -> None:
        path = _make_task_jsonl(tmp_path, [SAMPLE_TASK])
        tasks = load_tasks(path)
        assert len(tasks) == 1
        assert tasks[0].id == "rust-001"
        assert tasks[0].pack_name == "rust-expert"
        assert tasks[0].validation.language == "rust"
        assert tasks[0].validation.must_contain == ["fn ", "sort"]

    def test_loads_multiple_tasks(self, tmp_path: Path) -> None:
        t2 = {**SAMPLE_TASK, "id": "rust-002"}
        path = _make_task_jsonl(tmp_path, [SAMPLE_TASK, t2])
        tasks = load_tasks(path)
        assert len(tasks) == 2
        assert tasks[1].id == "rust-002"

    def test_respects_limit(self, tmp_path: Path) -> None:
        many = [{**SAMPLE_TASK, "id": f"t-{i}"} for i in range(10)]
        path = _make_task_jsonl(tmp_path, many)
        tasks = load_tasks(path, limit=3)
        assert len(tasks) == 3

    def test_limit_zero_returns_all(self, tmp_path: Path) -> None:
        many = [{**SAMPLE_TASK, "id": f"t-{i}"} for i in range(5)]
        path = _make_task_jsonl(tmp_path, many)
        tasks = load_tasks(path, limit=0)
        assert len(tasks) == 5

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "tasks.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps(SAMPLE_TASK) + "\n")
            f.write("\n")  # blank line
            f.write("   \n")  # whitespace-only line
            f.write(json.dumps({**SAMPLE_TASK, "id": "rust-002"}) + "\n")
        tasks = load_tasks(path)
        assert len(tasks) == 2

    def test_handles_missing_optional_fields(self, tmp_path: Path) -> None:
        """Tasks with no 'validation' or 'tags' keys should use defaults."""
        path = _make_task_jsonl(tmp_path, [SAMPLE_TASK_MINIMAL])
        tasks = load_tasks(path)
        assert len(tasks) == 1
        assert tasks[0].tags == []
        assert tasks[0].validation.language == "python"
        assert tasks[0].validation.must_contain == []

    def test_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "tasks.jsonl"
        path.write_text("")
        tasks = load_tasks(path)
        assert tasks == []

    def test_preserves_tags(self, tmp_path: Path) -> None:
        path = _make_task_jsonl(tmp_path, [SAMPLE_TASK])
        tasks = load_tasks(path)
        assert tasks[0].tags == ["sorting", "vectors"]


# ---------------------------------------------------------------------------
# load_skill_md
# ---------------------------------------------------------------------------


class TestLoadSkillMd:
    def test_reads_existing_skill_md(self, tmp_path: Path) -> None:
        content = "# Rust Expert\nSome skill content."
        (tmp_path / "skill.md").write_text(content)
        result = load_skill_md(tmp_path)
        assert result == content

    def test_generates_when_not_present(self, tmp_path: Path) -> None:
        """When skill.md does not exist, it falls back to generate_skill_md."""
        mock_manifest = {"name": "rust-expert", "description": "Rust expert pack"}
        mock_skill_md = "# Generated Skill\nGenerated content."

        # Patch the inline imports inside load_skill_md
        mock_manifest_mod = MagicMock()
        mock_manifest_mod.load_manifest.return_value = mock_manifest
        mock_template_mod = MagicMock()
        mock_template_mod.generate_skill_md.return_value = mock_skill_md

        with patch.dict(
            "sys.modules",
            {
                "wikigr.packs.manifest": mock_manifest_mod,
                "wikigr.packs.skill_template": mock_template_mod,
            },
        ):
            result = load_skill_md(tmp_path)

        assert result == mock_skill_md
        mock_manifest_mod.load_manifest.assert_called_once_with(tmp_path)
        mock_template_mod.generate_skill_md.assert_called_once_with(
            mock_manifest, tmp_path / "kg_config.json"
        )

    def test_generates_handles_none_manifest(self, tmp_path: Path) -> None:
        """When load_manifest returns None, generate_skill_md receives None."""
        mock_manifest_mod = MagicMock()
        mock_manifest_mod.load_manifest.return_value = None
        mock_template_mod = MagicMock()
        mock_template_mod.generate_skill_md.return_value = "# Fallback"

        with patch.dict(
            "sys.modules",
            {
                "wikigr.packs.manifest": mock_manifest_mod,
                "wikigr.packs.skill_template": mock_template_mod,
            },
        ):
            result = load_skill_md(tmp_path)

        # Should still call generate_skill_md even with None manifest
        mock_template_mod.generate_skill_md.assert_called_once_with(
            None, tmp_path / "kg_config.json"
        )
        assert result == "# Fallback"


# ---------------------------------------------------------------------------
# summarize_condition
# ---------------------------------------------------------------------------


class TestSummarizeCondition:
    def test_empty_results(self) -> None:
        summary = summarize_condition([])
        assert isinstance(summary, ConditionSummary)
        assert summary.avg_judge_score == 0
        assert summary.avg_composite_score == 0
        assert summary.syntax_pass_rate == 0

    def test_single_result(self) -> None:
        results = [_make_task_result(judge_score=8, latency_ms=1000.0, cost_usd=0.05, tool_calls=2)]
        summary = summarize_condition(results)
        assert summary.avg_judge_score == 8.0
        assert summary.avg_latency_ms == 1000.0
        assert summary.total_cost_usd == 0.05
        assert summary.avg_tool_calls == 2.0
        assert summary.syntax_pass_rate == 1.0

    def test_multiple_results_averages(self) -> None:
        results = [
            _make_task_result(judge_score=6, latency_ms=400.0, cost_usd=0.02, tool_calls=1),
            _make_task_result(judge_score=8, latency_ms=600.0, cost_usd=0.04, tool_calls=3),
        ]
        summary = summarize_condition(results)
        assert summary.avg_judge_score == 7.0  # (6+8)/2
        assert summary.avg_latency_ms == 500.0  # (400+600)/2
        assert summary.total_cost_usd == 0.06  # 0.02+0.04
        assert summary.avg_tool_calls == 2.0  # (1+3)/2

    def test_accuracy_gte7(self) -> None:
        results = [
            _make_task_result(judge_score=5),
            _make_task_result(judge_score=7),
            _make_task_result(judge_score=9),
            _make_task_result(judge_score=3),
        ]
        summary = summarize_condition(results)
        # 2 out of 4 have score >= 7
        assert summary.accuracy_gte7 == 0.5

    def test_syntax_pass_rate_mixed(self) -> None:
        r1 = _make_task_result(syntax_valid=True)
        r2 = _make_task_result(
            syntax_valid=False,
            validation=ValidationResult(
                syntax_valid=False,
                syntax_errors=["unexpected token"],
                contains_required={},
                contains_forbidden={},
                constructs_found={},
                execution_passed=None,
                execution_output=None,
            ),
        )
        summary = summarize_condition([r1, r2])
        assert summary.syntax_pass_rate == 0.5

    def test_no_validation(self) -> None:
        """Results with validation=None should count 0 for syntax_pass."""
        r = _make_task_result(judge_score=5)
        r.validation = None
        summary = summarize_condition([r])
        assert summary.syntax_pass_rate == 0.0

    def test_composite_score_present(self) -> None:
        """avg_composite_score should be a float between 0 and 1."""
        results = [_make_task_result(judge_score=10)]
        summary = summarize_condition(results)
        assert 0.0 <= summary.avg_composite_score <= 1.0

    def test_total_cost_is_sum_not_average(self) -> None:
        """total_cost_usd should be the sum of all individual costs."""
        results = [
            _make_task_result(cost_usd=0.10),
            _make_task_result(cost_usd=0.20),
            _make_task_result(cost_usd=0.30),
        ]
        summary = summarize_condition(results)
        assert summary.total_cost_usd == 0.60
