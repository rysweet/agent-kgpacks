"""Comprehensive evaluation runner tests.

Tests cover:
- Dry-run mode validation (no API calls made)
- Progress tracking validation
- Results JSON schema validation
- Comparative metrics computation
- Error handling (partial failures, baseline failures)
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wikigr.packs.eval.models import Answer, EvalMetrics, EvalResult, Question
from wikigr.packs.eval.runner import EvalRunner

# ============================================================================
# Dry-Run Mode Tests
# ============================================================================


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_dry_run_mode_makes_no_api_calls(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
):
    """Test dry-run mode validates without making API calls."""
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    result = runner.run_evaluation(sample_questions, dry_run=True)

    # No evaluator methods should be called
    mock_training_eval.return_value.evaluate.assert_not_called()
    mock_web_eval.return_value.evaluate.assert_not_called()
    mock_pack_eval.return_value.evaluate.assert_not_called()

    # Should return placeholder result
    assert result.pack_name == "test-pack"
    assert result.questions_tested == len(sample_questions)


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_dry_run_mode_validates_question_format(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
):
    """Test dry-run mode validates question format."""
    invalid_questions = [
        Question("", "What?", "Answer", "domain", "easy")  # Empty ID
    ]

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")

    with pytest.raises(ValueError, match="Question validation failed"):
        runner.run_evaluation(invalid_questions, dry_run=True)


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_dry_run_mode_checks_pack_validity(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    tmp_path: Path,
    sample_questions: list[Question],
):
    """Test dry-run mode validates pack before evaluation."""
    # Pack without manifest
    pack_path = tmp_path / "invalid_pack"
    pack_path.mkdir()

    runner = EvalRunner(pack_path, api_key="test_key")

    with pytest.raises(FileNotFoundError, match="manifest.json not found"):
        runner.run_evaluation(sample_questions, dry_run=True)


# ============================================================================
# Progress Tracking Tests
# ============================================================================


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_runner_tracks_progress(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
    mock_answers: dict[str, list[Answer]],
):
    """Test runner reports progress during evaluation."""
    # Setup mocks
    mock_training_eval.return_value.evaluate.return_value = mock_answers["training"]
    mock_web_eval.return_value.evaluate.return_value = mock_answers["web_search"]
    mock_pack_eval.return_value.evaluate.return_value = mock_answers["knowledge_pack"]

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")

    progress_updates = []

    def progress_callback(stage: str, progress: float):
        progress_updates.append((stage, progress))

    runner.run_evaluation(sample_questions, progress_callback=progress_callback)

    # Should have progress updates for each baseline
    assert len(progress_updates) >= 3
    assert any("training" in stage.lower() for stage, _ in progress_updates)
    assert any("web" in stage.lower() for stage, _ in progress_updates)
    assert any("pack" in stage.lower() for stage, _ in progress_updates)


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_runner_progress_updates_are_monotonic(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
    mock_answers: dict[str, list[Answer]],
):
    """Test progress values increase monotonically."""
    mock_training_eval.return_value.evaluate.return_value = mock_answers["training"]
    mock_web_eval.return_value.evaluate.return_value = mock_answers["web_search"]
    mock_pack_eval.return_value.evaluate.return_value = mock_answers["knowledge_pack"]

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")

    progress_values = []

    def progress_callback(stage: str, progress: float):
        progress_values.append(progress)

    runner.run_evaluation(sample_questions, progress_callback=progress_callback)

    # Progress should be non-decreasing
    for i in range(1, len(progress_values)):
        assert progress_values[i] >= progress_values[i - 1]


# ============================================================================
# Results JSON Schema Validation
# ============================================================================


def test_save_results_creates_valid_json(pack_path_with_manifest: Path, tmp_path: Path):
    """Test saved results conform to JSON schema."""
    result = EvalResult(
        pack_name="test-pack",
        timestamp="2024-01-01T00:00:00Z",
        training_baseline=EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05),
        web_search_baseline=EvalMetrics(0.8, 0.15, 0.7, 400.0, 0.08),
        knowledge_pack=EvalMetrics(0.9, 0.05, 0.95, 250.0, 0.03),
        surpasses_training=True,
        surpasses_web=True,
        questions_tested=10,
    )

    output_path = tmp_path / "results.json"
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    runner.save_results(result, output_path)

    # Load and validate schema
    with open(output_path) as f:
        data = json.load(f)

    required_fields = [
        "pack_name",
        "timestamp",
        "training_baseline",
        "web_search_baseline",
        "knowledge_pack",
        "surpasses_training",
        "surpasses_web",
        "questions_tested",
    ]

    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


def test_save_results_metrics_have_correct_types(pack_path_with_manifest: Path, tmp_path: Path):
    """Test saved metrics have correct types."""
    result = EvalResult(
        pack_name="test-pack",
        timestamp="2024-01-01T00:00:00Z",
        training_baseline=EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05),
        web_search_baseline=EvalMetrics(0.8, 0.15, 0.7, 400.0, 0.08),
        knowledge_pack=EvalMetrics(0.9, 0.05, 0.95, 250.0, 0.03),
        surpasses_training=True,
        surpasses_web=True,
        questions_tested=10,
    )

    output_path = tmp_path / "results.json"
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    runner.save_results(result, output_path)

    with open(output_path) as f:
        data = json.load(f)

    # Check types
    assert isinstance(data["pack_name"], str)
    assert isinstance(data["timestamp"], str)
    assert isinstance(data["surpasses_training"], bool)
    assert isinstance(data["surpasses_web"], bool)
    assert isinstance(data["questions_tested"], int)

    # Check metrics structure
    for baseline_key in ["training_baseline", "web_search_baseline", "knowledge_pack"]:
        metrics = data[baseline_key]
        assert isinstance(metrics["accuracy"], float)
        assert isinstance(metrics["hallucination_rate"], float)
        assert isinstance(metrics["citation_quality"], float)
        assert isinstance(metrics["avg_latency_ms"], float)
        assert isinstance(metrics["total_cost_usd"], float)


# ============================================================================
# Comparative Metrics Computation
# ============================================================================


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_runner_computes_improvement_over_training(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
):
    """Test runner computes improvement percentage over training baseline."""
    # Pack significantly better than training
    training_answers = [
        Answer("q1", "Mediocre answer", "training", 300.0, 0.01),
        Answer("q2", "Another answer", "training", 320.0, 0.012),
    ]
    pack_answers = [
        Answer("q1", "Excellent answer with citations [1]", "knowledge_pack", 200.0, 0.008),
        Answer("q2", "Great answer [1][2]", "knowledge_pack", 220.0, 0.009),
    ]

    mock_training_eval.return_value.evaluate.return_value = training_answers
    mock_web_eval.return_value.evaluate.return_value = training_answers
    mock_pack_eval.return_value.evaluate.return_value = pack_answers

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    result = runner.run_evaluation(sample_questions)

    # Pack should surpass training
    assert result.surpasses_training


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_runner_computes_improvement_over_web_search(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
):
    """Test runner computes improvement percentage over web search baseline."""
    web_answers = [
        Answer("q1", "Good answer [1]", "web_search", 400.0, 0.02),
        Answer("q2", "Decent answer [1]", "web_search", 450.0, 0.022),
    ]
    pack_answers = [
        Answer("q1", "Excellent answer [1][2][3]", "knowledge_pack", 200.0, 0.008),
        Answer("q2", "Superior answer [1][2]", "knowledge_pack", 220.0, 0.009),
    ]

    mock_training_eval.return_value.evaluate.return_value = web_answers
    mock_web_eval.return_value.evaluate.return_value = web_answers
    mock_pack_eval.return_value.evaluate.return_value = pack_answers

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    result = runner.run_evaluation(sample_questions)

    # Pack should surpass web search
    assert result.surpasses_web


# ============================================================================
# Error Handling - Partial Failures
# ============================================================================


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_runner_handles_partial_training_baseline_failure(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
    mock_answers: dict[str, list[Answer]],
):
    """Test runner handles failure in training baseline."""
    mock_training_eval.return_value.evaluate.side_effect = Exception("Training baseline failed")
    mock_web_eval.return_value.evaluate.return_value = mock_answers["web_search"]
    mock_pack_eval.return_value.evaluate.return_value = mock_answers["knowledge_pack"]

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")

    with pytest.raises(Exception, match="Training baseline failed"):
        runner.run_evaluation(sample_questions)


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_runner_handles_pack_evaluation_failure(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
    mock_answers: dict[str, list[Answer]],
):
    """Test runner handles failure in pack evaluation."""
    mock_training_eval.return_value.evaluate.return_value = mock_answers["training"]
    mock_web_eval.return_value.evaluate.return_value = mock_answers["web_search"]
    mock_pack_eval.return_value.evaluate.side_effect = Exception("Pack evaluation failed")

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")

    with pytest.raises(Exception, match="Pack evaluation failed"):
        runner.run_evaluation(sample_questions)


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.WebSearchBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_runner_continues_on_single_question_failure(
    mock_pack_eval: Mock,
    mock_web_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
):
    """Test runner continues if single question fails but others succeed."""
    questions = [
        Question("q1", "Valid question?", "Answer", "physics", "easy"),
        Question("q2", "Another valid?", "Answer2", "physics", "medium"),
    ]

    # First question succeeds, second fails for training baseline
    def training_eval_with_failure(qs):
        answers = []
        for i, q in enumerate(qs):
            if i == 1:
                raise Exception("Question 2 failed")
            answers.append(Answer(q.id, "Answer", "training", 300.0, 0.01))
        return answers

    mock_training_eval.return_value.evaluate.side_effect = training_eval_with_failure
    mock_web_eval.return_value.evaluate.return_value = [
        Answer("q1", "A1", "web_search", 400.0, 0.02),
        Answer("q2", "A2", "web_search", 450.0, 0.022),
    ]
    mock_pack_eval.return_value.evaluate.return_value = [
        Answer("q1", "A1", "knowledge_pack", 200.0, 0.008),
        Answer("q2", "A2", "knowledge_pack", 220.0, 0.009),
    ]

    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")

    with pytest.raises(Exception, match="Question 2 failed"):
        runner.run_evaluation(questions)


# ============================================================================
# Output File Handling
# ============================================================================


def test_save_results_creates_parent_directories(pack_path_with_manifest: Path, tmp_path: Path):
    """Test save_results creates nested directories if needed."""
    result = EvalResult(
        pack_name="test-pack",
        timestamp="2024-01-01T00:00:00Z",
        training_baseline=EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05),
        web_search_baseline=EvalMetrics(0.8, 0.15, 0.7, 400.0, 0.08),
        knowledge_pack=EvalMetrics(0.9, 0.05, 0.95, 250.0, 0.03),
        surpasses_training=True,
        surpasses_web=True,
        questions_tested=10,
    )

    output_path = tmp_path / "nested" / "dir" / "results.json"
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    runner.save_results(result, output_path)

    assert output_path.exists()
    assert output_path.parent.exists()


def test_save_results_overwrites_existing_file(pack_path_with_manifest: Path, tmp_path: Path):
    """Test save_results overwrites existing results file."""
    result1 = EvalResult(
        pack_name="test-pack-v1",
        timestamp="2024-01-01T00:00:00Z",
        training_baseline=EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05),
        web_search_baseline=EvalMetrics(0.8, 0.15, 0.7, 400.0, 0.08),
        knowledge_pack=EvalMetrics(0.9, 0.05, 0.95, 250.0, 0.03),
        surpasses_training=True,
        surpasses_web=True,
        questions_tested=10,
    )

    result2 = EvalResult(
        pack_name="test-pack-v2",
        timestamp="2024-01-02T00:00:00Z",
        training_baseline=EvalMetrics(0.75, 0.18, 0.55, 280.0, 0.045),
        web_search_baseline=EvalMetrics(0.82, 0.14, 0.72, 390.0, 0.075),
        knowledge_pack=EvalMetrics(0.92, 0.04, 0.96, 240.0, 0.028),
        surpasses_training=True,
        surpasses_web=True,
        questions_tested=10,
    )

    output_path = tmp_path / "results.json"
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")

    runner.save_results(result1, output_path)
    runner.save_results(result2, output_path)

    # Should contain v2 data
    with open(output_path) as f:
        data = json.load(f)

    assert data["pack_name"] == "test-pack-v2"
    assert data["timestamp"] == "2024-01-02T00:00:00Z"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def pack_path_with_manifest(tmp_path: Path) -> Path:
    """Create a pack directory with manifest."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()

    manifest = {
        "name": "test-pack",
        "version": "1.0.0",
        "description": "Test pack",
    }

    with open(pack_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    return pack_path


@pytest.fixture
def sample_questions() -> list[Question]:
    """Sample questions for testing."""
    return [
        Question(
            "q1", "What is photosynthesis?", "Process converting light to energy", "biology", "easy"
        ),
        Question("q2", "Explain gravity", "Force attracting objects", "physics", "medium"),
    ]


@pytest.fixture
def mock_answers() -> dict[str, list[Answer]]:
    """Mock answers for each baseline."""
    return {
        "training": [
            Answer("q1", "Light energy conversion", "training", 250.0, 0.001),
            Answer("q2", "Force of attraction", "training", 300.0, 0.0015),
        ],
        "web_search": [
            Answer("q1", "Photosynthesis converts light [1]", "web_search", 400.0, 0.002),
            Answer("q2", "Gravity attracts objects [2]", "web_search", 450.0, 0.0025),
        ],
        "knowledge_pack": [
            Answer("q1", "Process converting light to energy [1]", "knowledge_pack", 200.0, 0.0008),
            Answer("q2", "Force attracting objects [2]", "knowledge_pack", 220.0, 0.0012),
        ],
    }
