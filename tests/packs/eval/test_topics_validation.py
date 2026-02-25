"""Tests for topics file validation.

The topics file (topics.txt) contains Wikipedia article titles used to build
the knowledge pack. This module validates:
- Count requirements (200-500 topics)
- No duplicates
- Domain balance (4 domains represented)
- Wikipedia title format
"""

from pathlib import Path

import pytest

from wikigr.packs.eval.models import Question

# ============================================================================
# Topics File Existence and Format
# ============================================================================


def test_topics_file_exists(physics_topics_path: Path):
    """Verify topics.txt file exists."""
    assert physics_topics_path.exists(), f"Topics file not found: {physics_topics_path}"


def test_topics_file_not_empty(physics_topics_path: Path):
    """Verify topics file contains content."""
    content = physics_topics_path.read_text().strip()
    assert content, "Topics file is empty"


def test_topics_file_has_one_topic_per_line(physics_topics_path: Path):
    """Verify topics file format: one Wikipedia title per line."""
    lines = physics_topics_path.read_text().strip().split("\n")

    # Check no lines contain multiple topics (comma-separated)
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        # Wikipedia titles shouldn't contain commas in this context
        assert "," not in line, f"Line {i} contains comma - should be one topic per line: '{line}'"


# ============================================================================
# Topics Count Requirements
# ============================================================================


def test_topics_count_within_range(physics_topics: list[str]):
    """Verify 200-500 topics for optimal pack quality."""
    count = len(physics_topics)
    min_topics = 200
    max_topics = 500

    assert min_topics <= count <= max_topics, (
        f"Topics count {count} outside valid range [{min_topics}, {max_topics}]. "
        f"Too few topics → insufficient coverage, too many → scope creep."
    )


def test_topics_minimum_seed_count(physics_topics: list[str]):
    """Verify at least 200 seed topics (minimum for quality pack)."""
    min_topics = 200
    count = len(physics_topics)

    assert (
        count >= min_topics
    ), f"Only {count} seed topics found, minimum is {min_topics} for adequate coverage"


def test_topics_maximum_seed_count(physics_topics: list[str]):
    """Verify at most 500 seed topics (prevent scope creep)."""
    max_topics = 500
    count = len(physics_topics)

    assert count <= max_topics, (
        f"Too many seed topics ({count}), maximum is {max_topics}. "
        f"Large seed sets → unmanageable pack sizes."
    )


# ============================================================================
# Duplicate Detection
# ============================================================================


def test_no_duplicate_topics(physics_topics: list[str]):
    """Verify no duplicate topic titles."""
    duplicates = [topic for topic in physics_topics if physics_topics.count(topic) > 1]

    assert len(physics_topics) == len(
        set(physics_topics)
    ), f"Found {len(set(duplicates))} duplicate topics: {set(duplicates)[:5]}..."


def test_no_case_insensitive_duplicates(physics_topics: list[str]):
    """Verify no duplicates when case-insensitive comparison."""
    topics_lower = [t.lower() for t in physics_topics]
    duplicates = [t for t in topics_lower if topics_lower.count(t) > 1]

    assert len(topics_lower) == len(
        set(topics_lower)
    ), f"Found case-insensitive duplicates: {set(duplicates)[:5]}..."


def test_no_whitespace_variation_duplicates(physics_topics: list[str]):
    """Verify no duplicates due to whitespace differences."""
    topics_normalized = [" ".join(t.split()) for t in physics_topics]
    duplicates = [t for t in topics_normalized if topics_normalized.count(t) > 1]

    assert len(topics_normalized) == len(
        set(topics_normalized)
    ), f"Found whitespace-variation duplicates: {set(duplicates)[:5]}..."


# ============================================================================
# Domain Balance
# ============================================================================


def test_topics_cover_all_four_domains(physics_topics: list[str]):
    """Verify topics cover classical mechanics, quantum, thermo, relativity."""
    # Domain indicators (keywords in article titles)
    domain_keywords = {
        "classical_mechanics": [
            "mechanics",
            "motion",
            "force",
            "newton",
            "momentum",
            "energy",
            "rotation",
            "angular",
            "torque",
            "gravity",
            "orbital",
            "kepler",
        ],
        "quantum_mechanics": [
            "quantum",
            "wave",
            "particle",
            "heisenberg",
            "schrödinger",
            "entanglement",
            "superposition",
            "pauli",
            "fermion",
            "boson",
        ],
        "thermodynamics": [
            "thermodynamic",
            "entropy",
            "temperature",
            "heat",
            "carnot",
            "ideal_gas",
            "statistical",
            "boltzmann",
            "thermal",
            "phase",
        ],
        "relativity": [
            "relativity",
            "einstein",
            "spacetime",
            "lorentz",
            "minkowski",
            "gravitational",
            "time_dilation",
            "length_contraction",
            "schwarzschild",
        ],
    }

    # Count topics matching each domain
    domain_matches = {domain: 0 for domain in domain_keywords}

    for topic in physics_topics:
        topic_lower = topic.lower().replace(" ", "_")
        for domain, keywords in domain_keywords.items():
            if any(kw in topic_lower for kw in keywords):
                domain_matches[domain] += 1
                break  # Count each topic only once

    # Each domain should have at least 10% of topics
    total = len(physics_topics)
    min_per_domain = int(0.10 * total)

    for domain, count in domain_matches.items():
        assert count >= min_per_domain, (
            f"Domain '{domain}' has only {count} topics, "
            f"minimum is {min_per_domain} (10% of {total})"
        )


def test_topics_balanced_across_domains(physics_topics: list[str]):
    """Verify no single domain dominates (>40% of topics)."""
    # Domain indicators
    domain_keywords = {
        "classical_mechanics": ["mechanics", "motion", "force", "newton", "momentum"],
        "quantum_mechanics": ["quantum", "wave", "particle", "heisenberg", "schrödinger"],
        "thermodynamics": ["thermodynamic", "entropy", "temperature", "heat", "carnot"],
        "relativity": ["relativity", "einstein", "spacetime", "lorentz"],
    }

    domain_matches = {domain: 0 for domain in domain_keywords}

    for topic in physics_topics:
        topic_lower = topic.lower().replace(" ", "_")
        for domain, keywords in domain_keywords.items():
            if any(kw in topic_lower for kw in keywords):
                domain_matches[domain] += 1
                break

    total = len(physics_topics)
    max_per_domain = int(0.40 * total)  # No domain should exceed 40%

    for domain, count in domain_matches.items():
        assert count <= max_per_domain, (
            f"Domain '{domain}' dominates with {count} topics ({count/total:.0%}), "
            f"maximum is {max_per_domain} (40%)"
        )


# ============================================================================
# Wikipedia Title Format Validation
# ============================================================================


def test_topics_use_wikipedia_title_format(physics_topics: list[str]):
    """Verify topics follow Wikipedia title conventions."""
    for topic in physics_topics:
        # Wikipedia titles:
        # - Use underscores for spaces (sometimes)
        # - Start with capital letter
        # - Don't have leading/trailing whitespace
        # - Don't have special characters like | or #

        assert topic == topic.strip(), f"Topic has leading/trailing whitespace: '{topic}'"

        assert (
            topic[0].isupper() or topic[0].isdigit()
        ), f"Topic doesn't start with capital letter: '{topic}'"

        invalid_chars = ["|", "#", "[", "]", "{", "}"]
        for char in invalid_chars:
            assert char not in topic, f"Topic contains invalid character '{char}': '{topic}'"


def test_topics_not_redirect_syntax(physics_topics: list[str]):
    """Verify topics aren't Wikipedia redirect syntax."""
    for topic in physics_topics:
        # Common redirect patterns to avoid
        redirect_patterns = ["#REDIRECT", "See also:", "Redirect to", "Main article:"]

        for pattern in redirect_patterns:
            assert pattern not in topic, f"Topic appears to be redirect syntax: '{topic}'"


def test_topics_not_disambiguation_pages(physics_topics: list[str]):
    """Verify topics aren't disambiguation pages."""
    for topic in physics_topics:
        # Disambiguation pages typically end with " (disambiguation)"
        assert not topic.endswith("(disambiguation)"), f"Topic is disambiguation page: '{topic}'"


def test_topics_not_wikipedia_meta_pages(physics_topics: list[str]):
    """Verify topics aren't Wikipedia meta pages."""
    meta_prefixes = ["Wikipedia:", "Help:", "Template:", "Category:", "Portal:", "File:", "User:"]

    for topic in physics_topics:
        for prefix in meta_prefixes:
            assert not topic.startswith(prefix), f"Topic is Wikipedia meta page: '{topic}'"


# ============================================================================
# Content Quality Checks
# ============================================================================


def test_topics_not_empty_strings(physics_topics: list[str]):
    """Verify no empty topic strings."""
    for i, topic in enumerate(physics_topics):
        assert topic and topic.strip(), f"Topic {i} is empty or whitespace-only"


def test_topics_have_minimum_length(physics_topics: list[str]):
    """Verify topics have meaningful length (>2 characters)."""
    min_length = 2

    for topic in physics_topics:
        assert len(topic) >= min_length, f"Topic too short ({len(topic)} chars): '{topic}'"


def test_topics_not_just_punctuation(physics_topics: list[str]):
    """Verify topics contain alphabetic characters."""
    for topic in physics_topics:
        has_alpha = any(c.isalpha() for c in topic)
        assert has_alpha, f"Topic contains no letters: '{topic}'"


# ============================================================================
# Physics-Specific Validation
# ============================================================================


def test_topics_include_foundational_concepts(physics_topics: list[str]):
    """Verify essential physics concepts are included."""
    essential_topics = [
        # Classical Mechanics
        "Newton's laws of motion",
        "Conservation of energy",
        "Angular momentum",
        # Quantum Mechanics
        "Quantum mechanics",
        "Wave-particle duality",
        "Heisenberg uncertainty principle",
        # Thermodynamics
        "Laws of thermodynamics",
        "Entropy",
        "Second law of thermodynamics",
        # Relativity
        "Special relativity",
        "General relativity",
        "Theory of relativity",
    ]

    # Normalize for comparison (handle spaces vs underscores)
    topics_normalized = {t.lower().replace("_", " ") for t in physics_topics}

    missing_essential = []
    for essential in essential_topics:
        essential_normalized = essential.lower().replace("_", " ")
        if essential_normalized not in topics_normalized:
            # Also check if a similar topic exists
            similar_found = any(
                essential_normalized.replace("'", "") in topic
                or topic in essential_normalized.replace("'", "")
                for topic in topics_normalized
            )
            if not similar_found:
                missing_essential.append(essential)

    # Allow some flexibility - at least 70% of essential topics should be present
    coverage = 1 - (len(missing_essential) / len(essential_topics))
    assert coverage >= 0.70, (
        f"Missing {len(missing_essential)} essential physics topics ({coverage:.0%} coverage): "
        f"{missing_essential[:5]}..."
    )


def test_topics_include_famous_physicists(physics_topics: list[str]):
    """Verify famous physicists are included for historical context."""
    famous_physicists = [
        "Isaac Newton",
        "Albert Einstein",
        "Niels Bohr",
        "Werner Heisenberg",
        "Erwin Schrödinger",
        "Max Planck",
        "Richard Feynman",
        "Stephen Hawking",
    ]

    topics_normalized = {t.lower().replace("_", " ") for t in physics_topics}
    found_physicists = sum(
        1 for physicist in famous_physicists if physicist.lower() in topics_normalized
    )

    # At least 50% of famous physicists should be included
    coverage = found_physicists / len(famous_physicists)
    assert coverage >= 0.50, (
        f"Only {found_physicists}/{len(famous_physicists)} famous physicists included "
        f"({coverage:.0%} coverage)"
    )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def physics_topics_path() -> Path:
    """Path to physics-expert topics file."""
    path = Path("data/packs/physics-expert/topics.txt")
    return path


@pytest.fixture
def physics_topics(physics_topics_path: Path) -> list[str]:
    """Load topics from topics.txt file."""
    with open(physics_topics_path) as f:
        # Read non-empty lines, strip whitespace
        topics = [line.strip() for line in f if line.strip()]
    return topics


# ============================================================================
# Integration Test with Question Set
# ============================================================================


def test_topics_align_with_question_domains(
    physics_topics: list[str], physics_question_set: list[Question]
):
    """Verify topics cover domains represented in question set."""
    # Get domains from question set
    question_domains = {q.domain for q in physics_question_set}

    # Map domain keywords
    domain_keywords = {
        "classical_mechanics": ["mechanics", "motion", "force", "newton"],
        "quantum_mechanics": ["quantum", "wave", "particle", "heisenberg"],
        "thermodynamics": ["thermodynamic", "entropy", "temperature", "heat"],
        "relativity": ["relativity", "einstein", "spacetime"],
    }

    # Check each question domain is represented in topics
    for domain in question_domains:
        keywords = domain_keywords.get(domain, [])
        topics_lower = [t.lower().replace(" ", "_") for t in physics_topics]

        has_coverage = any(any(kw in topic for kw in keywords) for topic in topics_lower)

        assert has_coverage, (
            f"Question domain '{domain}' not represented in topics. "
            f"Add topics matching keywords: {keywords}"
        )
