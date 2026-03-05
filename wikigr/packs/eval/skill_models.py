"""Data models for skill delivery evaluation.

These models support the A/B/C evaluation harness that compares:
  A) Baseline (Claude alone)
  B) Pack retrieval (Claude + pre-fetched KG context)
  C) Skill delivery (Claude + skill.md system prompt + KG tool)
"""

from dataclasses import dataclass, field


@dataclass
class TaskValidation:
    """Validation criteria for a coding task."""

    language: str
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    expected_constructs: list[str] = field(default_factory=list)
    execution_test: str | None = None


@dataclass
class CodingTask:
    """A coding/development task for skill delivery evaluation.

    Unlike Question (Q&A), this represents a real development task
    where the output is code, configuration, or technical artifacts.
    """

    id: str
    pack_name: str
    task_type: str  # code_gen, debug, config, explain, refactor
    difficulty: str  # easy, medium, hard
    prompt: str
    ground_truth_code: str
    ground_truth_description: str
    validation: TaskValidation
    tags: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating task output."""

    syntax_valid: bool
    syntax_errors: list[str]
    contains_required: dict[str, bool]  # token -> found
    contains_forbidden: dict[str, bool]  # token -> found (True = bad)
    constructs_found: dict[str, bool]  # construct -> found
    execution_passed: bool | None  # None if no execution test
    execution_output: str | None


@dataclass
class TaskResult:
    """Result of evaluating a single task under one condition."""

    task_id: str
    condition: str  # "baseline", "pack_retrieval", "skill_delivery"
    raw_output: str
    judge_score: int = 0  # 0-10
    judge_reason: str = ""
    validation: ValidationResult | None = None
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    tool_calls_made: int = 0


@dataclass
class ConditionSummary:
    """Aggregate metrics for one condition across all tasks."""

    avg_judge_score: float
    avg_composite_score: float
    syntax_pass_rate: float
    accuracy_gte7: float  # % of tasks with judge score >= 7
    avg_latency_ms: float
    total_cost_usd: float
    avg_tool_calls: float


@dataclass
class SkillDeliveryResult:
    """Complete evaluation result for one pack."""

    pack_name: str
    timestamp: str
    tasks_evaluated: int
    conditions: dict[str, list[TaskResult]]  # condition_name -> results
    summary: dict[str, ConditionSummary]  # condition_name -> aggregate
