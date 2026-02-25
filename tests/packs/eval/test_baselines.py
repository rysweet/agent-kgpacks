"""Tests for baseline evaluators (with mocking)."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from wikigr.packs.eval.baselines import (
    KnowledgePackEvaluator,
    TrainingBaselineEvaluator,
)
from wikigr.packs.eval.models import Question


@pytest.fixture
def sample_questions() -> list[Question]:
    """Sample questions for testing."""
    return [
        Question(
            "q1", "What is photosynthesis?", "Process converting light to energy", "biology", "easy"
        ),
    ]


@pytest.fixture
def mock_anthropic_response() -> Mock:
    """Mock Anthropic API response."""
    response = Mock()
    response.content = [Mock(text="Sample answer text")]
    response.usage = Mock(input_tokens=100, output_tokens=50)
    return response


def test_training_baseline_evaluator_init():
    """Test TrainingBaselineEvaluator initialization."""
    evaluator = TrainingBaselineEvaluator(api_key="test_key")
    assert evaluator.model == "claude-sonnet-4-5-20250929"


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_evaluate(
    mock_anthropic_class: Mock,
    sample_questions: list[Question],
    mock_anthropic_response: Mock,
):
    """Test TrainingBaselineEvaluator.evaluate()."""
    # Setup mock
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    # Test
    evaluator = TrainingBaselineEvaluator(api_key="test_key")
    answers = evaluator.evaluate(sample_questions)

    assert len(answers) == 1
    assert answers[0].question_id == "q1"
    assert answers[0].answer == "Sample answer text"
    assert answers[0].source == "training"
    assert answers[0].latency_ms > 0
    assert answers[0].cost_usd > 0


def test_knowledge_pack_evaluator_init(tmp_path: Path):
    """Test KnowledgePackEvaluator initialization."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()

    evaluator = KnowledgePackEvaluator(pack_path, api_key="test_key")
    assert evaluator.pack_path == pack_path
    assert evaluator.model == "claude-sonnet-4-5-20250929"


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_knowledge_pack_evaluate(
    mock_anthropic_class: Mock,
    sample_questions: list[Question],
    mock_anthropic_response: Mock,
    tmp_path: Path,
):
    """Test KnowledgePackEvaluator.evaluate()."""
    # Setup pack directory with manifest
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    manifest = {
        "name": "test-pack",
        "description": "Test pack for evaluation",
    }
    import json

    with open(pack_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # Setup mock
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    # Test
    evaluator = KnowledgePackEvaluator(pack_path, api_key="test_key")
    answers = evaluator.evaluate(sample_questions)

    assert len(answers) == 1
    assert answers[0].question_id == "q1"
    assert answers[0].answer == "Sample answer text"
    assert answers[0].source == "knowledge_pack"
    assert answers[0].latency_ms > 0
    assert answers[0].cost_usd > 0


def test_knowledge_pack_retrieve_context_no_manifest(tmp_path: Path):
    """Test _retrieve_context when no manifest exists."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()

    evaluator = KnowledgePackEvaluator(pack_path, api_key="test_key")
    context = evaluator._retrieve_context("Test question")

    assert "Knowledge graph unavailable" in context


def test_knowledge_pack_retrieve_context_with_manifest(tmp_path: Path):
    """Test _retrieve_context with valid manifest."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()

    manifest = {
        "name": "test-pack",
        "description": "Test pack with physics knowledge",
    }
    import json

    with open(pack_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    evaluator = KnowledgePackEvaluator(pack_path, api_key="test_key")
    context = evaluator._retrieve_context("What is gravity?")

    assert "Test pack with physics knowledge" in context
