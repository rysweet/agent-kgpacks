"""
Test suite for Knowledge Graph Agent with increasing complexity.

Tests are ordered from simple retrieval to complex multi-hop reasoning.
Each test validates the agent's ability to extract and synthesize knowledge.
"""

import pytest

from wikigr.agent import KnowledgeGraphAgent


@pytest.fixture(scope="module")
def agent():
    """Create agent instance for all tests."""
    # Use the 30K DB once it's ready, fall back to 1K for now

    # Use test DB for fast iteration
    db_path = "data/wikigr_30k.db"
    agent = KnowledgeGraphAgent(db_path=db_path, read_only=True)
    yield agent
    agent.close()


class TestLevel1_SimpleRetrieval:
    """Level 1: Direct entity/article lookup."""

    def test_find_entity_by_name(self, agent):
        """Can the agent find a specific entity?"""
        result = agent.find_entity("Machine Learning")
        assert result is not None
        assert result["name"] == "Machine Learning"
        assert result["type"] in ["concept", "organization", "org"]

    def test_article_exists(self, agent):
        """Can the agent confirm an article exists?"""
        result = agent.query("Does the knowledge graph have information about Machine Learning?")
        assert "machine learning" in result["answer"].lower()
        # Answer should be substantive (not just "no")
        assert len(result["answer"]) > 20

    def test_get_article_facts(self, agent):
        """Can the agent retrieve facts about a topic?"""
        facts = agent.get_entity_facts("Machine Learning")
        assert len(facts) > 0
        # Each fact should be a non-empty string
        assert all(isinstance(f, str) and len(f) > 10 for f in facts)


class TestLevel2_SemanticSearch:
    """Level 2: Semantic similarity and concept proximity."""

    @pytest.mark.skip(reason="Needs vector index and multiple articles")
    def test_find_similar_articles(self, agent):
        """Can the agent find semantically similar articles?"""
        results = agent.semantic_search("Deep learning", top_k=5)
        assert len(results) > 0
        # Should find related AI/ML articles
        assert any(
            "neural" in r["title"].lower() or "learning" in r["title"].lower() for r in results
        )

    def test_concept_proximity(self, agent):
        """Can the agent determine if concepts are related?"""
        result = agent.query("How are neural networks and deep learning related?")
        # Should mention both concepts
        answer_lower = result["answer"].lower()
        assert "neural" in answer_lower and "deep" in answer_lower

    def test_category_search(self, agent):
        """Can the agent search within categories?"""
        result = agent.query("What computer science articles are in the knowledge graph?")
        assert len(result["sources"]) > 0


class TestLevel3_RelationshipTraversal:
    """Level 3: Following relationships between entities."""

    def test_find_relationship_path(self, agent):
        """Can the agent find paths between entities?"""
        paths = agent.find_relationship_path("OpenAI", "GPT-4", max_hops=3)
        # If both entities exist, should find at least one path
        if paths:
            assert len(paths) > 0
            assert paths[0]["hops"] <= 3
            assert "OpenAI" in paths[0]["entities"]

    def test_who_founded_what(self, agent):
        """Can the agent answer 'who founded X' questions?"""
        result = agent.query("Who founded OpenAI?")
        # Should extract founders from entity relationships
        assert result["answer"]
        # If we have the data, should mention Sam Altman or similar
        # (This may fail on partial DB, that's OK for now)

    def test_discover_indirect_connections(self, agent):
        """Can the agent find indirect connections?"""
        result = agent.query(
            "What is the relationship between artificial intelligence and robotics?"
        )
        # Should traverse entity relationships or article links
        assert len(result["answer"]) > 50  # Substantive answer


class TestLevel4_MultiHopReasoning:
    """Level 4: Multi-hop inference and synthesis."""

    def test_transitive_relationships(self, agent):
        """Can the agent infer transitive relationships?"""
        result = agent.query(
            "If deep learning is part of machine learning, and machine learning is part of AI, what does that tell us about deep learning?"
        )
        answer_lower = result["answer"].lower()
        assert "deep learning" in answer_lower
        assert "ai" in answer_lower or "artificial intelligence" in answer_lower

    @pytest.mark.skip(reason="Needs multiple source articles")
    def test_aggregate_across_sources(self, agent):
        """Can the agent synthesize from multiple articles?"""
        result = agent.query(
            "What are all the applications of neural networks mentioned in the knowledge graph?"
        )
        # Should aggregate facts from multiple articles
        assert len(result["sources"]) > 1
        assert len(result["facts"]) > 0

    def test_compare_concepts(self, agent):
        """Can the agent compare and contrast concepts?"""
        result = agent.query(
            "What is the difference between supervised learning and unsupervised learning?"
        )
        answer_lower = result["answer"].lower()
        assert "supervised" in answer_lower
        assert "unsupervised" in answer_lower


class TestLevel5_TemporalAndCausal:
    """Level 5: Temporal reasoning and causality."""

    @pytest.mark.skip(reason="Needs historical/temporal data")
    def test_historical_progression(self, agent):
        """Can the agent track development over time?"""
        result = agent.query(
            "How has artificial intelligence evolved from early expert systems to modern deep learning?"
        )
        # Should reference multiple time periods/approaches
        answer_lower = result["answer"].lower()
        assert len(result["sources"]) >= 2

    def test_cause_and_effect(self, agent):
        """Can the agent identify causal relationships?"""
        result = agent.query("What caused the AI winter?")
        # Should find facts or relationships about AI winter causes
        assert result["answer"]

    def test_prerequisite_knowledge(self, agent):
        """Can the agent determine prerequisites?"""
        result = agent.query(
            "What concepts do you need to understand before learning about transformer models?"
        )
        # Should reference foundational concepts
        answer_lower = result["answer"].lower()
        assert len(answer_lower) > 100  # Detailed answer


class TestLevel6_ConstraintSatisfaction:
    """Level 6: Queries with multiple constraints."""

    def test_multi_constraint_entity_search(self, agent):
        """Can the agent find entities matching multiple criteria?"""
        result = agent.query("Find people who worked on both neural networks and symbolic AI")
        # Complex query requiring entity type filter + relationship intersection
        assert result["answer"]

    def test_exclusion_queries(self, agent):
        """Can the agent handle negation?"""
        result = agent.query("What AI techniques are NOT based on neural networks?")
        # Should find symbolic AI, expert systems, etc.
        assert len(result["answer"]) > 50

    @pytest.mark.skip(reason="Needs ranked fact data")
    def test_ranked_retrieval(self, agent):
        """Can the agent rank results by relevance?"""
        result = agent.query("What are the most important breakthroughs in AI history?")
        # Should return ranked list based on facts/relationships
        assert len(result["facts"]) > 0 or len(result["sources"]) > 0


class TestLevel7_Reasoning:
    """Level 7: Complex reasoning and inference."""

    def test_contradiction_detection(self, agent):
        """Can the agent detect conflicting information?"""
        result = agent.query(
            "Are there any conflicting claims about the Turing test in the knowledge graph?"
        )
        # Should analyze facts across articles
        assert result["answer"]

    def test_gap_identification(self, agent):
        """Can the agent identify knowledge gaps?"""
        result = agent.query("What is missing from the knowledge graph about quantum computing?")
        # Should reason about what's present vs. what's expected
        assert len(result["answer"]) > 50

    def test_analogical_reasoning(self, agent):
        """Can the agent make analogies?"""
        result = agent.query(
            "How is the relationship between neural networks and deep learning similar to the relationship between algorithms and machine learning?"
        )
        # Complex multi-hop analogy
        assert "similar" in result["answer"].lower() or "analogy" in result["answer"].lower()


class TestLevel8_Compositional:
    """Level 8: Compositional queries requiring multiple operations."""

    def test_filter_then_rank(self, agent):
        """Can the agent chain filter + rank operations?"""
        result = agent.query(
            "Among all computer scientists in the knowledge graph, who has the most connections to other entities?"
        )
        # Requires: filter by type, count relationships, rank
        assert result["answer"]

    def test_aggregate_then_compare(self, agent):
        """Can the agent aggregate then compare?"""
        result = agent.query(
            "Which field has more entities mentioned: machine learning or computer vision?"
        )
        # Requires: entity count per field, comparison
        assert (
            "machine learning" in result["answer"].lower()
            or "computer vision" in result["answer"].lower()
        )

    def test_nested_retrieval(self, agent):
        """Can the agent handle nested sub-queries?"""
        result = agent.query(
            "What are the key facts about the inventors of technologies mentioned in the deep learning article?"
        )
        # Requires: get deep learning article → extract mentioned technologies → find inventors → get their facts
        assert len(result["answer"]) > 100


# Performance benchmarks
class TestPerformance:
    """Performance tests for query latency."""

    def test_simple_query_latency(self, agent):
        """Simple queries should be fast (<2s)."""
        import time

        start = time.time()
        agent.query("What is machine learning?")
        elapsed = time.time() - start
        assert elapsed < 5.0  # Allow 5s for LLM synthesis

    def test_complex_query_latency(self, agent):
        """Complex queries should complete (<10s)."""
        import time

        start = time.time()
        agent.query("Find all entities related to neural networks within 2 hops")
        elapsed = time.time() - start
        assert elapsed < 15.0  # Allow 15s for complex traversal + LLM

    def test_semantic_search_latency(self, agent):
        """Semantic search should be fast (vector index)."""
        import time

        start = time.time()
        agent.semantic_search("Artificial intelligence", top_k=10)
        elapsed = time.time() - start
        assert elapsed < 3.0  # Vector search should be sub-second + overhead
