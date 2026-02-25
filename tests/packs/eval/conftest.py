"""Shared fixtures for eval tests."""

from pathlib import Path

import pytest

from wikigr.packs.eval.models import Question
from wikigr.packs.eval.questions import load_questions_jsonl


@pytest.fixture
def physics_questions_jsonl_path() -> Path:
    """Path to physics-expert evaluation questions JSONL file."""
    return Path("data/packs/physics-expert/eval/questions.jsonl")


@pytest.fixture
def physics_question_set(physics_questions_jsonl_path: Path) -> list[Question]:
    """Load complete physics-expert question set from JSONL."""
    return load_questions_jsonl(physics_questions_jsonl_path)


@pytest.fixture
def physics_topics_path() -> Path:
    """Path to physics-expert topics file."""
    return Path("data/packs/physics-expert/topics.txt")


@pytest.fixture
def physics_topics(physics_topics_path: Path) -> list[str]:
    """Load topics from topics.txt file."""
    with open(physics_topics_path) as f:
        topics = [line.strip() for line in f if line.strip()]
    return topics
