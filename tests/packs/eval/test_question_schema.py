"""Tests for question set validation (schema, distribution, balance).

This module tests the complete question set requirements for evaluation:
- Schema validation (75 questions, all required fields)
- Domain balance (4 domains, ~25% each ±5%)
- Difficulty distribution (30% easy, 50% medium, 20% hard ±5%)
- No duplicate questions
- Reference answer quality
"""

import json
from pathlib import Path

import pytest

from wikigr.packs.eval.models import Question

# ============================================================================
# Question Set Schema Validation
# ============================================================================


def test_question_set_has_exactly_75_questions(physics_question_set: list[Question]):
    """Verify question set contains exactly 75 questions."""
    assert (
        len(physics_question_set) == 75
    ), f"Expected 75 questions for physics pack evaluation, got {len(physics_question_set)}"


def test_all_questions_have_required_fields(physics_question_set: list[Question]):
    """Verify every question has all required fields populated."""
    for i, q in enumerate(physics_question_set):
        assert q.id, f"Question {i}: missing id"
        assert q.question, f"Question {i} ({q.id}): missing question text"
        assert q.ground_truth, f"Question {i} ({q.id}): missing ground_truth"
        assert q.domain, f"Question {i} ({q.id}): missing domain"
        assert q.difficulty, f"Question {i} ({q.id}): missing difficulty"


def test_question_ids_are_unique(physics_question_set: list[Question]):
    """Verify no duplicate question IDs in the set."""
    ids = [q.id for q in physics_question_set]
    duplicates = [qid for qid in ids if ids.count(qid) > 1]

    assert len(ids) == len(set(ids)), f"Found duplicate question IDs: {set(duplicates)}"


def test_question_text_is_unique(physics_question_set: list[Question]):
    """Verify no duplicate question text (prevents redundant evaluation)."""
    questions = [q.question.lower().strip() for q in physics_question_set]
    duplicates = [qt for qt in questions if questions.count(qt) > 1]

    assert len(questions) == len(
        set(questions)
    ), f"Found {len(duplicates)} duplicate question texts"


# ============================================================================
# Domain Balance Tests
# ============================================================================


def test_domain_balance_four_domains(physics_question_set: list[Question]):
    """Verify exactly 4 physics domains are represented."""
    expected_domains = {"classical_mechanics", "quantum_mechanics", "thermodynamics", "relativity"}

    actual_domains = {q.domain for q in physics_question_set}

    assert (
        actual_domains == expected_domains
    ), f"Expected domains {expected_domains}, got {actual_domains}"


def test_domain_balance_distribution(physics_question_set: list[Question]):
    """Verify each domain has ~25% of questions (±5% tolerance)."""
    domain_counts = {}
    for q in physics_question_set:
        domain_counts[q.domain] = domain_counts.get(q.domain, 0) + 1

    total = len(physics_question_set)
    expected_per_domain = total / 4  # 75 / 4 = 18.75
    tolerance = 0.05 * total  # 5% tolerance = 3.75 questions

    for domain, count in domain_counts.items():
        percentage = (count / total) * 100
        assert abs(count - expected_per_domain) <= tolerance, (
            f"Domain '{domain}' has {count} questions ({percentage:.1f}%), "
            f"expected ~{expected_per_domain:.1f} (25% ±5%)"
        )


def test_domain_minimum_coverage(physics_question_set: list[Question]):
    """Verify each domain has at least 15 questions."""
    domain_counts = {}
    for q in physics_question_set:
        domain_counts[q.domain] = domain_counts.get(q.domain, 0) + 1

    min_questions = 15
    for domain, count in domain_counts.items():
        assert (
            count >= min_questions
        ), f"Domain '{domain}' has only {count} questions, minimum is {min_questions}"


# ============================================================================
# Difficulty Distribution Tests
# ============================================================================


def test_difficulty_values_are_valid(physics_question_set: list[Question]):
    """Verify all difficulty values are 'easy', 'medium', or 'hard'."""
    valid_difficulties = {"easy", "medium", "hard"}

    for q in physics_question_set:
        assert q.difficulty in valid_difficulties, (
            f"Question {q.id} has invalid difficulty '{q.difficulty}', "
            f"must be one of {valid_difficulties}"
        )


def test_difficulty_distribution(physics_question_set: list[Question]):
    """Verify difficulty distribution: 30% easy, 50% medium, 20% hard (±5%)."""
    difficulty_counts = {"easy": 0, "medium": 0, "hard": 0}

    for q in physics_question_set:
        difficulty_counts[q.difficulty] += 1

    total = len(physics_question_set)
    tolerance = 0.05  # 5% tolerance

    # Expected: 30% easy (22.5 ±3.75 = 19-26)
    easy_expected = 0.30 * total
    easy_actual = difficulty_counts["easy"]
    assert abs(easy_actual - easy_expected) <= (
        tolerance * total
    ), f"Easy questions: expected {easy_expected:.1f} (30% ±5%), got {easy_actual}"

    # Expected: 50% medium (37.5 ±3.75 = 34-41)
    medium_expected = 0.50 * total
    medium_actual = difficulty_counts["medium"]
    assert abs(medium_actual - medium_expected) <= (
        tolerance * total
    ), f"Medium questions: expected {medium_expected:.1f} (50% ±5%), got {medium_actual}"

    # Expected: 20% hard (15 ±3.75 = 11-19)
    hard_expected = 0.20 * total
    hard_actual = difficulty_counts["hard"]
    assert abs(hard_actual - hard_expected) <= (
        tolerance * total
    ), f"Hard questions: expected {hard_expected:.1f} (20% ±5%), got {hard_actual}"


def test_each_domain_has_mixed_difficulties(physics_question_set: list[Question]):
    """Verify each domain contains easy, medium, and hard questions."""
    domain_difficulties = {}

    for q in physics_question_set:
        if q.domain not in domain_difficulties:
            domain_difficulties[q.domain] = set()
        domain_difficulties[q.domain].add(q.difficulty)

    for domain, difficulties in domain_difficulties.items():
        assert difficulties == {"easy", "medium", "hard"}, (
            f"Domain '{domain}' missing difficulty levels: "
            f"has {difficulties}, needs {{easy, medium, hard}}"
        )


# ============================================================================
# Reference Answer Quality Tests
# ============================================================================


def test_ground_truth_has_minimum_length(physics_question_set: list[Question]):
    """Verify ground truth answers are substantive (>20 characters)."""
    min_length = 20

    for q in physics_question_set:
        length = len(q.ground_truth.strip())
        assert length >= min_length, (
            f"Question {q.id}: ground_truth too short ({length} chars), "
            f"minimum is {min_length} chars for quality reference"
        )


def test_ground_truth_not_just_question_rephrased(physics_question_set: list[Question]):
    """Verify ground truth is not just the question rephrased."""
    for q in physics_question_set:
        question_words = set(q.question.lower().split())
        truth_words = set(q.ground_truth.lower().split())

        # If >80% of ground truth words are in the question, it's likely a rephrasing
        overlap = len(truth_words & question_words)
        overlap_ratio = overlap / len(truth_words) if truth_words else 0

        assert overlap_ratio < 0.8, (
            f"Question {q.id}: ground_truth appears to be question rephrased "
            f"({overlap_ratio:.0%} word overlap)"
        )


def test_ground_truth_contains_factual_content(physics_question_set: list[Question]):
    """Verify ground truth contains concrete physics terms (not vague)."""
    # Vague filler words that shouldn't dominate the answer
    vague_words = {
        "thing",
        "stuff",
        "very",
        "really",
        "basically",
        "simply",
        "something",
        "somehow",
        "somewhat",
        "kind",
        "sort",
    }

    for q in physics_question_set:
        truth_words = q.ground_truth.lower().split()
        vague_count = sum(1 for word in truth_words if word in vague_words)
        vague_ratio = vague_count / len(truth_words) if truth_words else 0

        # Vague words should be < 20% of answer
        assert vague_ratio < 0.2, (
            f"Question {q.id}: ground_truth too vague " f"({vague_ratio:.0%} vague filler words)"
        )


# ============================================================================
# JSONL Format Tests
# ============================================================================


def test_jsonl_file_exists(physics_questions_jsonl_path: Path):
    """Verify questions JSONL file exists."""
    assert (
        physics_questions_jsonl_path.exists()
    ), f"Questions JSONL file not found: {physics_questions_jsonl_path}"


def test_jsonl_format_valid(physics_questions_jsonl_path: Path):
    """Verify JSONL file has valid JSON on each line."""
    with open(physics_questions_jsonl_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                assert isinstance(data, dict), f"Line {line_num}: not a JSON object"
            except json.JSONDecodeError as e:
                pytest.fail(f"Line {line_num}: invalid JSON - {e}")


def test_jsonl_schema_compliance(physics_questions_jsonl_path: Path):
    """Verify each JSONL line has required question fields."""
    required_fields = {"id", "question", "ground_truth", "domain", "difficulty"}

    with open(physics_questions_jsonl_path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            data = json.loads(line)
            missing_fields = required_fields - set(data.keys())

            assert not missing_fields, f"Line {line_num}: missing fields {missing_fields}"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def physics_questions_jsonl_path() -> Path:
    """Path to physics-expert evaluation questions JSONL file."""
    # This file should be created by implementation
    path = Path("data/packs/physics-expert/eval/questions.jsonl")
    return path


@pytest.fixture
def physics_question_set(physics_questions_jsonl_path: Path) -> list[Question]:
    """Load complete physics-expert question set from JSONL."""
    from wikigr.packs.eval.questions import load_questions_jsonl

    # This will fail until questions.jsonl is created
    return load_questions_jsonl(physics_questions_jsonl_path)


# ============================================================================
# Edge Cases and Boundary Tests
# ============================================================================


def test_question_ids_follow_consistent_format(physics_question_set: list[Question]):
    """Verify question IDs follow consistent naming pattern."""
    # Expected pattern: q1, q2, ..., q75 or physics_001, physics_002, etc.
    import re

    # Check if all IDs match at least one consistent pattern
    patterns = [
        r"^q\d+$",  # q1, q2, etc.
        r"^physics_\d{3}$",  # physics_001, physics_002, etc.
    ]

    for q in physics_question_set:
        matches_pattern = any(re.match(pattern, q.id) for pattern in patterns)
        assert matches_pattern, f"Question ID '{q.id}' doesn't follow consistent naming pattern"


def test_no_questions_with_empty_whitespace_fields(physics_question_set: list[Question]):
    """Verify no fields contain only whitespace."""
    for q in physics_question_set:
        assert q.id.strip(), "Question has whitespace-only ID"
        assert q.question.strip(), f"Question {q.id} has whitespace-only question"
        assert q.ground_truth.strip(), f"Question {q.id} has whitespace-only ground_truth"
        assert q.domain.strip(), f"Question {q.id} has whitespace-only domain"
        assert q.difficulty.strip(), f"Question {q.id} has whitespace-only difficulty"


def test_questions_are_actually_questions(physics_question_set: list[Question]):
    """Verify question texts are interrogative (contain ? or question words)."""
    question_indicators = {"what", "why", "how", "when", "where", "which", "who", "?"}

    for q in physics_question_set:
        question_lower = q.question.lower()
        has_indicator = any(indicator in question_lower for indicator in question_indicators)

        assert has_indicator, f"Question {q.id} doesn't appear to be a question: '{q.question}'"


def test_domain_names_consistent_with_documentation(physics_question_set: list[Question]):
    """Verify domain names match those documented in EVALUATION.md."""
    documented_domains = {
        "classical_mechanics",
        "quantum_mechanics",
        "thermodynamics",
        "relativity",
    }

    actual_domains = {q.domain for q in physics_question_set}

    assert actual_domains == documented_domains, (
        f"Domain names don't match documentation. "
        f"Expected: {documented_domains}, Found: {actual_domains}"
    )
