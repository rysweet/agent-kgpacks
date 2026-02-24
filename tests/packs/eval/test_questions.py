"""Tests for question loading and validation."""

import json
from pathlib import Path

import pytest

from wikigr.packs.eval.models import Question
from wikigr.packs.eval.questions import load_questions_jsonl, validate_questions


@pytest.fixture
def questions_file(tmp_path: Path) -> Path:
    """Create a temporary questions JSONL file."""
    path = tmp_path / "questions.jsonl"
    questions = [
        {
            "id": "q1",
            "question": "What is E=mc²?",
            "ground_truth": "Einstein's mass-energy equivalence formula.",
            "domain": "physics",
            "difficulty": "easy",
        },
        {
            "id": "q2",
            "question": "Explain quantum entanglement.",
            "ground_truth": "A quantum phenomenon where particles remain connected.",
            "domain": "physics",
            "difficulty": "hard",
        },
    ]

    with open(path, "w") as f:
        for q in questions:
            f.write(json.dumps(q) + "\n")

    return path


def test_load_questions_jsonl(questions_file: Path):
    """Test loading questions from JSONL file."""
    questions = load_questions_jsonl(questions_file)

    assert len(questions) == 2
    assert questions[0].id == "q1"
    assert questions[0].question == "What is E=mc²?"
    assert questions[0].domain == "physics"
    assert questions[0].difficulty == "easy"


def test_load_questions_nonexistent_file():
    """Test loading from nonexistent file raises error."""
    with pytest.raises(FileNotFoundError):
        load_questions_jsonl(Path("/nonexistent/file.jsonl"))


def test_load_questions_malformed_json(tmp_path: Path):
    """Test loading malformed JSON raises error."""
    path = tmp_path / "bad.jsonl"
    with open(path, "w") as f:
        f.write("{not valid json}\n")

    with pytest.raises(ValueError, match="Error parsing line"):
        load_questions_jsonl(path)


def test_load_questions_missing_field(tmp_path: Path):
    """Test loading question with missing field raises error."""
    path = tmp_path / "missing.jsonl"
    with open(path, "w") as f:
        f.write(json.dumps({"id": "q1", "question": "Test?"}) + "\n")

    with pytest.raises(ValueError, match="Error parsing line"):
        load_questions_jsonl(path)


def test_validate_questions_empty():
    """Test validating empty list returns error."""
    errors = validate_questions([])
    assert len(errors) == 1
    assert "No questions" in errors[0]


def test_validate_questions_valid():
    """Test validating valid questions returns no errors."""
    questions = [
        Question("q1", "Test?", "Answer", "physics", "easy"),
        Question("q2", "Test2?", "Answer2", "physics", "medium"),
    ]

    errors = validate_questions(questions)
    assert len(errors) == 0


def test_validate_questions_duplicate_ids():
    """Test validating duplicate IDs returns error."""
    questions = [
        Question("q1", "Test?", "Answer", "physics", "easy"),
        Question("q1", "Test2?", "Answer2", "physics", "medium"),
    ]

    errors = validate_questions(questions)
    assert any("Duplicate question IDs" in e for e in errors)


def test_validate_questions_empty_fields():
    """Test validating empty fields returns errors."""
    questions = [
        Question("", "Test?", "Answer", "physics", "easy"),
        Question("q2", "", "Answer", "physics", "medium"),
        Question("q3", "Test?", "", "physics", "hard"),
        Question("q4", "Test?", "Answer", "", "easy"),
    ]

    errors = validate_questions(questions)
    assert len(errors) == 4
    assert any("ID cannot be empty" in e for e in errors)
    assert any("question cannot be empty" in e for e in errors)
    assert any("ground_truth cannot be empty" in e for e in errors)
    assert any("domain cannot be empty" in e for e in errors)


def test_validate_questions_invalid_difficulty():
    """Test validating invalid difficulty returns error."""
    questions = [Question("q1", "Test?", "Answer", "physics", "super-hard")]

    errors = validate_questions(questions)
    assert len(errors) == 1
    assert "difficulty must be one of" in errors[0]
