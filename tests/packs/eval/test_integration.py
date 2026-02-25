"""Integration test for complete evaluation workflow."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wikigr.packs.eval import (
    EvalRunner,
    Question,
    load_questions_jsonl,
    validate_questions,
)


@pytest.fixture
def temp_pack(tmp_path: Path) -> Path:
    """Create a temporary pack directory with manifest."""
    pack_dir = tmp_path / "test_pack"
    pack_dir.mkdir()

    manifest = {
        "name": "test-pack",
        "version": "1.0.0",
        "description": "Test pack for integration testing",
        "graph_stats": {"articles": 100, "entities": 200, "relationships": 150, "size_mb": 10},
        "eval_scores": {"accuracy": 0.0, "hallucination_rate": 0.0, "citation_quality": 0.0},
        "source_urls": ["https://example.com"],
        "created": "2024-01-01T00:00:00Z",
        "license": "MIT",
    }

    with open(pack_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    return pack_dir


@pytest.fixture
def temp_questions(tmp_path: Path) -> Path:
    """Create a temporary questions file."""
    questions_file = tmp_path / "questions.jsonl"

    questions = [
        {
            "id": "q1",
            "question": "What is photosynthesis?",
            "ground_truth": "Process converting light to energy",
            "domain": "biology",
            "difficulty": "easy",
        },
        {
            "id": "q2",
            "question": "Explain gravity",
            "ground_truth": "Force attracting objects",
            "domain": "physics",
            "difficulty": "medium",
        },
    ]

    with open(questions_file, "w") as f:
        for q in questions:
            f.write(json.dumps(q) + "\n")

    return questions_file


@pytest.mark.integration
def test_end_to_end_evaluation_workflow(temp_pack: Path, temp_questions: Path, tmp_path: Path):
    """Test complete evaluation workflow from questions to results."""
    # 1. Load questions
    questions = load_questions_jsonl(temp_questions)
    assert len(questions) == 2

    # 2. Validate questions
    errors = validate_questions(questions)
    assert len(errors) == 0

    # 3. Mock Anthropic API
    mock_response = Mock()
    mock_response.content = [Mock(text="Sample answer with citation [1]")]
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)

    with patch("wikigr.packs.eval.baselines.Anthropic") as mock_anthropic_class:
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # 4. Run evaluation
        runner = EvalRunner(temp_pack, api_key="test_key")
        result = runner.run_evaluation(questions)

        # 5. Verify result structure
        assert result.pack_name == "test-pack"
        assert result.questions_tested == 2
        assert 0.0 <= result.training_baseline.accuracy <= 1.0
        assert result.web_search_baseline is None
        assert 0.0 <= result.knowledge_pack.accuracy <= 1.0

        # 6. Save results
        output_file = tmp_path / "results.json"
        runner.save_results(result, output_file)

        # 7. Verify saved file
        assert output_file.exists()
        with open(output_file) as f:
            saved_data = json.load(f)

        assert saved_data["pack_name"] == "test-pack"
        assert saved_data["questions_tested"] == 2
        assert "training_baseline" in saved_data
        assert saved_data["web_search_baseline"] is None
        assert "knowledge_pack" in saved_data
        assert isinstance(saved_data["surpasses_training"], bool)
        assert isinstance(saved_data["surpasses_web"], bool)


@pytest.mark.integration
def test_evaluation_with_invalid_questions(temp_pack: Path, tmp_path: Path):
    """Test that evaluation fails gracefully with invalid questions."""
    # Create invalid questions file
    invalid_file = tmp_path / "invalid.jsonl"
    with open(invalid_file, "w") as f:
        f.write('{"id": "q1"}\n')  # Missing required fields

    # Should raise ValueError
    with pytest.raises(ValueError, match="Error parsing"):
        load_questions_jsonl(invalid_file)


@pytest.mark.integration
def test_question_validation_catches_errors(temp_pack: Path):
    """Test that validation catches various error conditions."""
    # Duplicate IDs
    questions = [
        Question("q1", "Test?", "Answer", "domain", "easy"),
        Question("q1", "Test2?", "Answer", "domain", "medium"),
    ]
    errors = validate_questions(questions)
    assert any("Duplicate" in e for e in errors)

    # Invalid difficulty
    questions = [Question("q1", "Test?", "Answer", "domain", "impossible")]
    errors = validate_questions(questions)
    assert any("difficulty must be one of" in e for e in errors)

    # Empty fields
    questions = [Question("", "Test?", "Answer", "domain", "easy")]
    errors = validate_questions(questions)
    assert any("ID cannot be empty" in e for e in errors)
