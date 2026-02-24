"""Question loading and validation for evaluation.

This module provides functions for loading questions from JSONL files
and validating their format.
"""

import json
from pathlib import Path

from wikigr.packs.eval.models import Question


def load_questions_jsonl(path: Path) -> list[Question]:
    """Load questions from JSONL file.

    Each line in the file should be a JSON object with fields:
    - id: unique identifier
    - question: the question text
    - ground_truth: expected answer
    - domain: domain/topic
    - difficulty: "easy", "medium", or "hard"

    Args:
        path: Path to JSONL file containing questions

    Returns:
        List of Question objects

    Raises:
        FileNotFoundError: If path doesn't exist
        json.JSONDecodeError: If JSONL is malformed
        KeyError: If required fields are missing
    """
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")

    questions = []
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                question = Question(
                    id=data["id"],
                    question=data["question"],
                    ground_truth=data["ground_truth"],
                    domain=data["domain"],
                    difficulty=data["difficulty"],
                )
                questions.append(question)
            except (KeyError, json.JSONDecodeError) as e:
                raise ValueError(f"Error parsing line {line_num}: {e}") from e

    return questions


def validate_questions(questions: list[Question]) -> list[str]:
    """Validate question format and return errors.

    Args:
        questions: List of questions to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not questions:
        errors.append("No questions provided")
        return errors

    # Check for duplicate IDs
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        duplicates = [qid for qid in ids if ids.count(qid) > 1]
        errors.append(f"Duplicate question IDs: {set(duplicates)}")

    # Validate each question
    for i, q in enumerate(questions):
        # Check required fields are non-empty
        if not q.id or not q.id.strip():
            errors.append(f"Question {i}: ID cannot be empty")
        if not q.question or not q.question.strip():
            errors.append(f"Question {q.id}: question cannot be empty")
        if not q.ground_truth or not q.ground_truth.strip():
            errors.append(f"Question {q.id}: ground_truth cannot be empty")
        if not q.domain or not q.domain.strip():
            errors.append(f"Question {q.id}: domain cannot be empty")

        # Validate difficulty
        valid_difficulties = {"easy", "medium", "hard"}
        if q.difficulty not in valid_difficulties:
            errors.append(
                f"Question {q.id}: difficulty must be one of {valid_difficulties}, "
                f"got '{q.difficulty}'"
            )

    return errors
