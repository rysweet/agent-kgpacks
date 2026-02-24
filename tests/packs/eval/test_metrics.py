"""Tests for metrics calculation."""

import pytest

from wikigr.packs.eval.metrics import (
    aggregate_metrics,
    calculate_accuracy,
    calculate_citation_quality,
    calculate_hallucination_rate,
)
from wikigr.packs.eval.models import Answer, Question


@pytest.fixture
def sample_questions() -> list[Question]:
    """Sample questions for testing."""
    return [
        Question(
            "q1",
            "What is photosynthesis?",
            "Process of converting light to energy",
            "biology",
            "easy",
        ),
        Question(
            "q2", "Explain gravity", "Force that attracts objects with mass", "physics", "medium"
        ),
    ]


@pytest.fixture
def sample_answers() -> list[Answer]:
    """Sample answers for testing."""
    return [
        Answer("q1", "Process of converting light to energy", "training", 250.0, 0.001),
        Answer("q2", "Gravity is a force that attracts objects", "training", 300.0, 0.0015),
    ]


def test_calculate_accuracy_exact_match(sample_questions: list[Question]):
    """Test accuracy calculation with exact match."""
    answers = [
        Answer("q1", "Process of converting light to energy", "training", 250.0, 0.001),
    ]

    accuracy = calculate_accuracy(answers, sample_questions)
    assert accuracy == 1.0


def test_calculate_accuracy_contains_truth(sample_questions: list[Question]):
    """Test accuracy calculation when answer contains ground truth."""
    answers = [
        Answer(
            "q1",
            "Photosynthesis is the process of converting light to energy in plants.",
            "training",
            250.0,
            0.001,
        ),
    ]

    accuracy = calculate_accuracy(answers, sample_questions)
    assert accuracy == 0.8


def test_calculate_accuracy_partial_overlap(sample_questions: list[Question]):
    """Test accuracy calculation with partial word overlap."""
    answers = [
        Answer("q1", "Photosynthesis involves converting light", "training", 250.0, 0.001),
    ]

    accuracy = calculate_accuracy(answers, sample_questions)
    assert accuracy == 0.5


def test_calculate_accuracy_no_overlap(sample_questions: list[Question]):
    """Test accuracy calculation with no overlap."""
    answers = [
        Answer("q1", "Completely wrong answer", "training", 250.0, 0.001),
    ]

    accuracy = calculate_accuracy(answers, sample_questions)
    assert accuracy == 0.0


def test_calculate_accuracy_empty():
    """Test accuracy calculation with empty inputs."""
    assert calculate_accuracy([], []) == 0.0


def test_calculate_hallucination_rate_no_hedging():
    """Test hallucination rate with confident answers."""
    answers = [
        Answer("q1", "Photosynthesis converts light to energy.", "training", 250.0, 0.001),
        Answer("q2", "Gravity attracts objects with mass.", "training", 300.0, 0.0015),
    ]

    rate = calculate_hallucination_rate(answers)
    assert rate == 0.0


def test_calculate_hallucination_rate_with_hedging():
    """Test hallucination rate with hedging language."""
    answers = [
        Answer(
            "q1", "I think photosynthesis might be something about light", "training", 250.0, 0.001
        ),
        Answer("q2", "Gravity probably attracts objects", "training", 300.0, 0.0015),
    ]

    rate = calculate_hallucination_rate(answers)
    assert rate == 1.0  # Both have hedging, no citations


def test_calculate_hallucination_rate_with_citations():
    """Test hallucination rate with citations present."""
    answers = [
        Answer(
            "q1", "I think photosynthesis [1] converts light to energy", "training", 250.0, 0.001
        ),
        Answer(
            "q2", "According to Smith (2020), gravity attracts objects", "training", 300.0, 0.0015
        ),
    ]

    rate = calculate_hallucination_rate(answers)
    assert rate == 0.0  # Hedging but has citations


def test_calculate_hallucination_rate_empty():
    """Test hallucination rate with empty inputs."""
    assert calculate_hallucination_rate([]) == 0.0


def test_calculate_citation_quality_with_citations():
    """Test citation quality with various citation formats."""
    answers = [
        Answer("q1", "Photosynthesis converts light [1]", "training", 250.0, 0.001),
        Answer("q2", "According to Smith (2020), gravity works", "training", 300.0, 0.0015),
        Answer("q3", "Source: physics textbook", "training", 300.0, 0.0015),
    ]

    quality = calculate_citation_quality(answers)
    assert quality == 1.0  # All have citations


def test_calculate_citation_quality_no_citations():
    """Test citation quality without citations."""
    answers = [
        Answer("q1", "Photosynthesis converts light", "training", 250.0, 0.001),
        Answer("q2", "Gravity attracts objects", "training", 300.0, 0.0015),
    ]

    quality = calculate_citation_quality(answers)
    assert quality == 0.0


def test_calculate_citation_quality_mixed():
    """Test citation quality with mixed citations."""
    answers = [
        Answer("q1", "Photosynthesis converts light [1]", "training", 250.0, 0.001),
        Answer("q2", "Gravity attracts objects", "training", 300.0, 0.0015),
    ]

    quality = calculate_citation_quality(answers)
    assert quality == 0.5


def test_calculate_citation_quality_empty():
    """Test citation quality with empty inputs."""
    assert calculate_citation_quality([]) == 0.0


def test_aggregate_metrics(sample_answers: list[Answer], sample_questions: list[Question]):
    """Test aggregating all metrics."""
    metrics = aggregate_metrics(sample_answers, sample_questions)

    assert 0.0 <= metrics.accuracy <= 1.0
    assert 0.0 <= metrics.hallucination_rate <= 1.0
    assert 0.0 <= metrics.citation_quality <= 1.0
    assert metrics.avg_latency_ms == 275.0  # (250 + 300) / 2
    assert metrics.total_cost_usd == 0.0025  # 0.001 + 0.0015


def test_aggregate_metrics_empty():
    """Test aggregating metrics with empty inputs."""
    metrics = aggregate_metrics([], [])

    assert metrics.accuracy == 0.0
    assert metrics.hallucination_rate == 0.0
    assert metrics.citation_quality == 0.0
    assert metrics.avg_latency_ms == 0.0
    assert metrics.total_cost_usd == 0.0
