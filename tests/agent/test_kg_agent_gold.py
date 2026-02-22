"""
Gold standard evaluation tests for Knowledge Graph Agent.

Evaluates agent answers against known Q&A pairs to measure
accuracy across different query types (entity search, relationship
paths, fact retrieval, semantic search, multi-hop, complex).
"""

import json
from pathlib import Path

import pytest

from wikigr.agent import KnowledgeGraphAgent

GOLD_STANDARD_PATH = Path(__file__).parent / "gold_standard.json"


@pytest.fixture(scope="module")
def agent():
    """Create agent instance for all gold standard tests."""
    db_path = "data/wikigr_30k.db"
    if not Path(db_path).exists():
        pytest.skip("30K database not available")
    agent = KnowledgeGraphAgent(db_path=db_path, read_only=True)
    yield agent
    agent.close()


@pytest.fixture(scope="module")
def gold_standard():
    """Load gold standard test cases."""
    with open(GOLD_STANDARD_PATH) as f:
        return json.load(f)


class TestGoldStandardEvaluation:
    """Evaluate agent against gold standard Q&A pairs."""

    def test_gold_standard_file_exists(self):
        """Gold standard file should exist and be valid JSON."""
        assert GOLD_STANDARD_PATH.exists()
        with open(GOLD_STANDARD_PATH) as f:
            data = json.load(f)
        assert len(data) >= 10
        for item in data:
            assert "id" in item
            assert "question" in item
            assert "expected_keywords" in item

    def test_entity_search_accuracy(self, agent, gold_standard):
        """Test entity search queries return relevant answers."""
        cases = [c for c in gold_standard if c["type"] == "entity_search"]
        assert len(cases) >= 2

        for case in cases:
            result = agent.query(case["question"])
            answer = result["answer"].lower()

            assert (
                len(result["answer"]) >= case["min_answer_length"]
            ), f"[{case['id']}] Answer too short: {len(result['answer'])} chars"

            keyword_hits = sum(1 for kw in case["expected_keywords"] if kw.lower() in answer)
            assert keyword_hits >= 1, (
                f"[{case['id']}] No expected keywords found in answer. "
                f"Expected any of: {case['expected_keywords']}"
            )

    def test_relationship_path_accuracy(self, agent, gold_standard):
        """Test relationship path queries mention related entities."""
        cases = [c for c in gold_standard if c["type"] == "relationship_path"]
        assert len(cases) >= 2

        for case in cases:
            result = agent.query(case["question"])
            answer = result["answer"].lower()

            assert (
                len(result["answer"]) >= case["min_answer_length"]
            ), f"[{case['id']}] Answer too short: {len(result['answer'])} chars"

            entity_hits = sum(1 for e in case["expected_entities"] if e.lower() in answer)
            assert entity_hits >= 1, (
                f"[{case['id']}] No expected entities found in answer. "
                f"Expected any of: {case['expected_entities']}"
            )

    def test_fact_retrieval_accuracy(self, agent, gold_standard):
        """Test fact retrieval queries contain expected facts."""
        cases = [c for c in gold_standard if c["type"] == "fact_retrieval"]
        assert len(cases) >= 2

        for case in cases:
            result = agent.query(case["question"])
            answer = result["answer"].lower()

            assert (
                len(result["answer"]) >= case["min_answer_length"]
            ), f"[{case['id']}] Answer too short: {len(result['answer'])} chars"

            keyword_hits = sum(1 for kw in case["expected_keywords"] if kw.lower() in answer)
            assert keyword_hits >= 1, (
                f"[{case['id']}] No expected keywords found in answer. "
                f"Expected any of: {case['expected_keywords']}"
            )

    def test_semantic_search_accuracy(self, agent, gold_standard):
        """Test semantic search queries find relevant topics."""
        cases = [c for c in gold_standard if c["type"] == "semantic_search"]
        assert len(cases) >= 2

        for case in cases:
            result = agent.query(case["question"])

            assert (
                len(result["answer"]) >= case["min_answer_length"]
            ), f"[{case['id']}] Answer too short: {len(result['answer'])} chars"

    def test_complex_query_accuracy(self, agent, gold_standard):
        """Test complex multi-hop and comparison queries."""
        cases = [c for c in gold_standard if c["type"] in ("multi_hop", "complex")]
        assert len(cases) >= 2

        for case in cases:
            result = agent.query(case["question"])

            assert (
                len(result["answer"]) >= case["min_answer_length"]
            ), f"[{case['id']}] Answer too short: {len(result['answer'])} chars"


class TestGoldStandardMetrics:
    """Aggregate metrics across all gold standard cases."""

    def test_overall_keyword_precision(self, agent, gold_standard):
        """At least 60% of queries should match at least one keyword."""
        total = 0
        hits = 0

        for case in gold_standard:
            result = agent.query(case["question"])
            answer = result["answer"].lower()
            total += 1

            keyword_match = any(kw.lower() in answer for kw in case["expected_keywords"])
            if keyword_match:
                hits += 1

        precision = hits / total if total > 0 else 0
        assert (
            precision >= 0.6
        ), f"Keyword precision too low: {precision:.0%} ({hits}/{total}). Target: >= 60%"
