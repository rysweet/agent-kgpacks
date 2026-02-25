"""Tests for evaluation runner."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wikigr.packs.eval.models import Answer, EvalMetrics, Question
from wikigr.packs.eval.runner import EvalRunner


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
            Answer("q1", "Light energy conversion [1]", "training", 250.0, 0.001),
            Answer("q2", "Force of attraction", "training", 300.0, 0.0015),
        ],
        "knowledge_pack": [
            Answer("q1", "Process converting light to energy [1]", "knowledge_pack", 200.0, 0.0008),
            Answer("q2", "Force attracting objects [2]", "knowledge_pack", 220.0, 0.0012),
        ],
    }


@pytest.fixture
def pack_path_with_manifest(tmp_path: Path) -> Path:
    """Create a pack directory with manifest."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()

    manifest = {
        "name": "test-pack",
        "version": "1.0.0",
        "description": "Test pack",
        "graph_stats": {"articles": 100, "entities": 200, "relationships": 150, "size_mb": 10},
        "eval_scores": {"accuracy": 0.0, "hallucination_rate": 0.0, "citation_quality": 0.0},
        "source_urls": ["https://example.com"],
        "created": "2024-01-01T00:00:00Z",
        "license": "MIT",
    }

    with open(pack_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    return pack_path


def test_eval_runner_init(pack_path_with_manifest: Path):
    """Test EvalRunner initialization."""
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    assert runner.pack_path == pack_path_with_manifest
    assert runner.training_eval is not None
    assert runner.pack_eval is not None


@patch("wikigr.packs.eval.runner.TrainingBaselineEvaluator")
@patch("wikigr.packs.eval.runner.KnowledgePackEvaluator")
def test_run_evaluation(
    mock_pack_eval: Mock,
    mock_training_eval: Mock,
    pack_path_with_manifest: Path,
    sample_questions: list[Question],
    mock_answers: dict[str, list[Answer]],
):
    """Test complete evaluation run."""
    # Setup mocks
    mock_training_instance = Mock()
    mock_training_instance.evaluate.return_value = mock_answers["training"]
    mock_training_eval.return_value = mock_training_instance

    mock_pack_instance = Mock()
    mock_pack_instance.evaluate.return_value = mock_answers["knowledge_pack"]
    mock_pack_eval.return_value = mock_pack_instance

    # Run evaluation
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    result = runner.run_evaluation(sample_questions)

    # Verify result structure
    assert result.pack_name == "test-pack"
    assert result.questions_tested == 2
    assert isinstance(result.training_baseline, EvalMetrics)
    assert result.web_search_baseline is None
    assert isinstance(result.knowledge_pack, EvalMetrics)
    assert isinstance(result.surpasses_training, bool)
    assert isinstance(result.surpasses_web, bool)


def test_save_results(pack_path_with_manifest: Path, tmp_path: Path):
    """Test saving evaluation results."""
    # Create a mock result
    from wikigr.packs.eval.models import EvalResult

    result = EvalResult(
        pack_name="test-pack",
        timestamp="2024-01-01T00:00:00Z",
        training_baseline=EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05),
        web_search_baseline=None,
        knowledge_pack=EvalMetrics(0.9, 0.05, 0.95, 250.0, 0.03),
        surpasses_training=True,
        surpasses_web=False,
        questions_tested=10,
    )

    # Save results
    output_path = tmp_path / "eval" / "results.json"
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key")
    runner.save_results(result, output_path)

    # Verify file was created
    assert output_path.exists()

    # Verify content
    with open(output_path) as f:
        data = json.load(f)

    assert data["pack_name"] == "test-pack"
    assert data["questions_tested"] == 10
    assert data["surpasses_training"] is True
    assert data["surpasses_web"] is False
    assert "training_baseline" in data
    assert data["web_search_baseline"] is None
    assert "knowledge_pack" in data


def test_surpasses_determination():
    """Test logic for determining if pack surpasses baselines."""
    # Pack with better metrics should surpass
    pack_metrics = EvalMetrics(0.9, 0.05, 0.95, 250.0, 0.03)
    training_metrics = EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05)

    # Pack surpasses if: higher accuracy, lower hallucination, higher citation quality
    surpasses = (
        pack_metrics.accuracy > training_metrics.accuracy
        and pack_metrics.hallucination_rate < training_metrics.hallucination_rate
        and pack_metrics.citation_quality > training_metrics.citation_quality
    )

    assert surpasses is True


def test_does_not_surpass_determination():
    """Test logic for pack that does not surpass baseline."""
    # Pack with worse metrics should not surpass
    pack_metrics = EvalMetrics(0.6, 0.3, 0.4, 250.0, 0.03)
    training_metrics = EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05)

    surpasses = (
        pack_metrics.accuracy > training_metrics.accuracy
        and pack_metrics.hallucination_rate < training_metrics.hallucination_rate
        and pack_metrics.citation_quality > training_metrics.citation_quality
    )

    assert surpasses is False


def test_dry_run_mode(pack_path_with_manifest: Path, sample_questions: list[Question]):
    """Test evaluation in dry-run mode (no API calls)."""
    # Create runner in dry-run mode
    runner = EvalRunner(pack_path_with_manifest, api_key="test_key", dry_run=True)

    # Run evaluation (should not make API calls)
    result = runner.run_evaluation(sample_questions, show_progress=False)

    # Verify result structure
    assert result.pack_name == "test-pack"
    assert result.questions_tested == 2
    assert isinstance(result.training_baseline, EvalMetrics)
    assert result.web_search_baseline is None
    assert isinstance(result.knowledge_pack, EvalMetrics)


def test_generate_mock_answers(pack_path_with_manifest: Path, sample_questions: list[Question]):
    """Test mock answer generation for dry-run."""
    runner = EvalRunner(pack_path_with_manifest, dry_run=True)

    # Generate mock answers
    answers = runner._generate_mock_answers(sample_questions, "training")

    # Verify structure
    assert len(answers) == 2
    assert all(a.source == "training" for a in answers)
    assert all(a.latency_ms > 0 for a in answers)
    assert all(a.cost_usd > 0 for a in answers)
    assert answers[0].question_id == "q1"
    assert answers[1].question_id == "q2"


def test_show_progress_flag(pack_path_with_manifest: Path, sample_questions: list[Question]):
    """Test that show_progress flag controls progress bar display."""
    runner = EvalRunner(pack_path_with_manifest, dry_run=True)

    # Should work with show_progress=False
    result = runner.run_evaluation(sample_questions, show_progress=False)
    assert result.questions_tested == 2

    # Should work with show_progress=True (default)
    result = runner.run_evaluation(sample_questions, show_progress=True)
    assert result.questions_tested == 2
