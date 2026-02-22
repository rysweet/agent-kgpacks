"""
Performance benchmark suite for Knowledge Graph Agent.

Measures query latency across different query types and reports results.
Target latencies from the KG Agent Evaluation Guide (#46):
- Simple entity search: < 5s
- Semantic search: < 5s
- Fact retrieval: < 5s
- Relationship paths: < 10s
- Complex/multi-hop: < 15s
- Graph RAG: < 15s
"""

import time
from pathlib import Path

import pytest

from wikigr.agent import KnowledgeGraphAgent

# Collect benchmark results for summary report
_benchmark_results: list[dict] = []


def _timed_call(func, *args, **kwargs):
    """Execute a function and return (result, elapsed_seconds)."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


@pytest.fixture(scope="module")
def agent():
    """Create agent instance for all benchmark tests."""
    db_path = "data/wikigr_30k.db"
    if not Path(db_path).exists():
        pytest.skip("30K database not available")
    agent = KnowledgeGraphAgent(db_path=db_path, read_only=True)
    yield agent
    agent.close()

    # Print summary after all tests
    if _benchmark_results:
        print("\n" + "=" * 70)
        print("KG AGENT PERFORMANCE BENCHMARK RESULTS")
        print("=" * 70)
        for r in _benchmark_results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f"  [{status}] {r['name']:40s} {r['elapsed']:.2f}s (target: <{r['target']}s)")
        print("=" * 70)
        passed = sum(1 for r in _benchmark_results if r["passed"])
        print(f"  {passed}/{len(_benchmark_results)} benchmarks within target latency")


class TestEntitySearchBenchmark:
    """Benchmark entity search queries (target: < 5s)."""

    TARGET = 5.0

    def test_find_entity_latency(self, agent):
        """Find entity by name should complete within target."""
        result, elapsed = _timed_call(agent.find_entity, "Machine Learning")
        _benchmark_results.append(
            {
                "name": "find_entity(Machine Learning)",
                "elapsed": elapsed,
                "target": self.TARGET,
                "passed": elapsed < self.TARGET,
            }
        )
        assert result is not None
        assert elapsed < self.TARGET, f"Entity search took {elapsed:.2f}s (target: <{self.TARGET}s)"

    def test_query_entity_latency(self, agent):
        """Query about an entity should complete within target."""
        result, elapsed = _timed_call(agent.query, "What is Machine Learning?")
        _benchmark_results.append(
            {
                "name": "query(What is Machine Learning?)",
                "elapsed": elapsed,
                "target": self.TARGET,
                "passed": elapsed < self.TARGET,
            }
        )
        assert len(result["answer"]) > 20
        assert elapsed < self.TARGET, f"Entity query took {elapsed:.2f}s (target: <{self.TARGET}s)"


class TestFactRetrievalBenchmark:
    """Benchmark fact retrieval queries (target: < 5s)."""

    TARGET = 5.0

    def test_get_facts_latency(self, agent):
        """Fact retrieval should complete within target."""
        result, elapsed = _timed_call(agent.get_entity_facts, "Machine Learning")
        _benchmark_results.append(
            {
                "name": "get_entity_facts(Machine Learning)",
                "elapsed": elapsed,
                "target": self.TARGET,
                "passed": elapsed < self.TARGET,
            }
        )
        assert len(result) > 0
        assert (
            elapsed < self.TARGET
        ), f"Fact retrieval took {elapsed:.2f}s (target: <{self.TARGET}s)"


class TestRelationshipBenchmark:
    """Benchmark relationship path queries (target: < 10s)."""

    TARGET = 10.0

    def test_relationship_path_latency(self, agent):
        """Relationship path query should complete within target."""
        result, elapsed = _timed_call(
            agent.query, "How are Machine Learning and Artificial Intelligence related?"
        )
        _benchmark_results.append(
            {
                "name": "query(ML <-> AI relationship)",
                "elapsed": elapsed,
                "target": self.TARGET,
                "passed": elapsed < self.TARGET,
            }
        )
        assert len(result["answer"]) > 20
        assert (
            elapsed < self.TARGET
        ), f"Relationship query took {elapsed:.2f}s (target: <{self.TARGET}s)"

    def test_find_path_latency(self, agent):
        """find_relationship_path should complete within target."""
        result, elapsed = _timed_call(
            agent.find_relationship_path, "Machine Learning", "Deep Learning"
        )
        _benchmark_results.append(
            {
                "name": "find_relationship_path(ML -> DL)",
                "elapsed": elapsed,
                "target": self.TARGET,
                "passed": elapsed < self.TARGET,
            }
        )
        assert elapsed < self.TARGET, f"Path finding took {elapsed:.2f}s (target: <{self.TARGET}s)"


class TestComplexQueryBenchmark:
    """Benchmark complex/multi-hop queries (target: < 15s)."""

    TARGET = 15.0

    def test_complex_comparison_latency(self, agent):
        """Complex comparison query should complete within target."""
        result, elapsed = _timed_call(
            agent.query, "Compare supervised learning and unsupervised learning"
        )
        _benchmark_results.append(
            {
                "name": "query(compare supervised vs unsupervised)",
                "elapsed": elapsed,
                "target": self.TARGET,
                "passed": elapsed < self.TARGET,
            }
        )
        assert len(result["answer"]) > 30
        assert elapsed < self.TARGET, f"Complex query took {elapsed:.2f}s (target: <{self.TARGET}s)"


class TestGraphRAGBenchmark:
    """Benchmark graph RAG queries (target: < 15s)."""

    TARGET = 15.0

    def test_graph_rag_latency(self, agent):
        """Graph RAG multi-hop query should complete within target."""
        result, elapsed = _timed_call(
            agent.graph_query, "What are the key applications of neural networks?", max_hops=2
        )
        _benchmark_results.append(
            {
                "name": "graph_query(neural network applications)",
                "elapsed": elapsed,
                "target": self.TARGET,
                "passed": elapsed < self.TARGET,
            }
        )
        assert len(result["answer"]) > 20
        assert elapsed < self.TARGET, f"Graph RAG took {elapsed:.2f}s (target: <{self.TARGET}s)"
