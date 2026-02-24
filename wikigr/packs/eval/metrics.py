"""Metrics calculation for evaluation results.

This module provides functions for calculating evaluation metrics:
- Accuracy: semantic similarity to ground truth
- Hallucination rate: detection of unsupported claims
- Citation quality: validation of citations
"""

import re

from wikigr.packs.eval.models import Answer, EvalMetrics, Question


def calculate_accuracy(answers: list[Answer], questions: list[Question]) -> float:
    """Calculate accuracy by comparing answers to ground truth.

    For MVP, uses simple semantic similarity based on:
    - Exact match: 1.0
    - Contains ground truth: 0.8
    - Partial overlap: 0.5
    - No overlap: 0.0

    Args:
        answers: List of generated answers
        questions: List of corresponding questions with ground truth

    Returns:
        Average accuracy score (0.0 to 1.0)
    """
    if not answers or not questions:
        return 0.0

    # Create question lookup by ID
    q_by_id = {q.id: q for q in questions}

    scores = []
    for answer in answers:
        question = q_by_id.get(answer.question_id)
        if not question:
            continue

        # Normalize text for comparison
        answer_norm = answer.answer.lower().strip()
        truth_norm = question.ground_truth.lower().strip()

        # Calculate similarity
        if answer_norm == truth_norm:
            score = 1.0  # Exact match
        elif truth_norm in answer_norm:
            score = 0.8  # Contains ground truth
        elif any(word in answer_norm for word in truth_norm.split() if len(word) > 3):
            score = 0.5  # Partial overlap
        else:
            score = 0.0  # No overlap

        scores.append(score)

    return sum(scores) / len(scores) if scores else 0.0


def calculate_hallucination_rate(answers: list[Answer]) -> float:
    """Detect claims not supported by source material.

    For MVP, uses heuristic detection:
    - Checks for hedging language (suggests model is unsure)
    - Checks for citation markers (suggests grounded in sources)
    - Binary classification: has hallucination markers or not

    Args:
        answers: List of generated answers

    Returns:
        Rate of answers with hallucination markers (0.0 to 1.0)
    """
    if not answers:
        return 0.0

    # Hedging phrases that suggest uncertainty or lack of grounding
    hedging_phrases = [
        "i think",
        "i believe",
        "probably",
        "maybe",
        "might be",
        "could be",
        "possibly",
        "not sure",
        "uncertain",
    ]

    # Citation markers that suggest grounded in sources
    citation_patterns = [
        r"\[\d+\]",  # [1], [2], etc.
        r"\([A-Za-z]+ \d{4}\)",  # (Smith 2020) or (smith 2020)
        r"(?i)according to",  # Case-insensitive
        r"(?i)source:",  # Case-insensitive
        r"(?i)citation:",  # Case-insensitive
    ]

    hallucinations = 0
    for answer in answers:
        answer_lower = answer.answer.lower()

        # Check for hedging without citations
        has_hedging = any(phrase in answer_lower for phrase in hedging_phrases)
        has_citations = any(re.search(pattern, answer.answer) for pattern in citation_patterns)

        # If hedging without citations, flag as potential hallucination
        if has_hedging and not has_citations:
            hallucinations += 1

    return hallucinations / len(answers)


def calculate_citation_quality(answers: list[Answer]) -> float:
    """Check if citations are accurate and relevant.

    For MVP, uses binary classification:
    - Has citation markers: 1.0
    - No citation markers: 0.0

    Args:
        answers: List of generated answers

    Returns:
        Rate of answers with valid citations (0.0 to 1.0)
    """
    if not answers:
        return 0.0

    # Citation patterns
    citation_patterns = [
        r"\[\d+\]",  # [1], [2], etc.
        r"\([A-Za-z]+ \d{4}\)",  # (Smith 2020) or (smith 2020)
        r"(?i)according to",  # Case-insensitive
        r"(?i)source:",  # Case-insensitive
        r"(?i)citation:",  # Case-insensitive
        r"(?i)reference:",  # Case-insensitive
    ]

    citations_found = 0
    for answer in answers:
        # Check if any citation pattern exists
        if any(re.search(pattern, answer.answer) for pattern in citation_patterns):
            citations_found += 1

    return citations_found / len(answers)


def aggregate_metrics(answers: list[Answer], questions: list[Question]) -> EvalMetrics:
    """Aggregate all metrics for a set of answers.

    Args:
        answers: List of generated answers
        questions: List of questions with ground truth

    Returns:
        EvalMetrics with all calculated metrics
    """
    accuracy = calculate_accuracy(answers, questions)
    hallucination_rate = calculate_hallucination_rate(answers)
    citation_quality = calculate_citation_quality(answers)

    # Calculate latency and cost
    latencies = [a.latency_ms for a in answers] if answers else [0.0]
    costs = [a.cost_usd for a in answers] if answers else [0.0]

    avg_latency_ms = sum(latencies) / len(latencies)
    total_cost_usd = sum(costs)

    return EvalMetrics(
        accuracy=accuracy,
        hallucination_rate=hallucination_rate,
        citation_quality=citation_quality,
        avg_latency_ms=avg_latency_ms,
        total_cost_usd=total_cost_usd,
    )
