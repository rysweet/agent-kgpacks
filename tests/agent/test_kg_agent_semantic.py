"""Tests for KnowledgeGraphAgent.semantic_search free-text support."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


@pytest.fixture()
def agent():
    """Create a KnowledgeGraphAgent with mocked Kuzu and Anthropic dependencies."""
    with (
        patch("wikigr.agent.kg_agent.kuzu") as mock_kuzu,
        patch("wikigr.agent.kg_agent.Anthropic"),
    ):
        mock_db = MagicMock()
        mock_kuzu.Database.return_value = mock_db
        mock_conn = MagicMock()
        mock_kuzu.Connection.return_value = mock_conn

        from wikigr.agent.kg_agent import KnowledgeGraphAgent

        ag = KnowledgeGraphAgent(db_path="/fake/db", anthropic_api_key="fake-key")
        yield ag
        ag.close()


def _make_execute_result(df: pd.DataFrame) -> MagicMock:
    """Build a mock Kuzu query result that returns the given DataFrame."""
    result = MagicMock()
    result.get_as_df.return_value = df
    return result


# --------------------------------------------------------------------------
# Fast path: article title matches an existing article
# --------------------------------------------------------------------------
class TestSemanticSearchFastPath:
    """When the query matches an article title, use its existing embedding."""

    def test_uses_existing_embedding(self, agent):
        """semantic_search should use the article's section embedding when available."""
        fake_embedding = [0.1] * 384

        # First call: article lookup returns an embedding
        article_df = pd.DataFrame({"embedding": [fake_embedding]})
        # Second call: vector search returns results
        vector_df = pd.DataFrame(
            {
                "node": [{"section_id": "Machine learning#intro"}],
                "distance": [0.05],
            }
        )
        agent.conn.execute.side_effect = [
            _make_execute_result(article_df),
            _make_execute_result(vector_df),
        ]

        results = agent.semantic_search("Machine learning", top_k=5)

        assert len(results) == 1
        assert results[0]["title"] == "Machine learning"
        assert results[0]["similarity"] == pytest.approx(0.95)

        # Should NOT have initialized the embedding generator
        assert agent._embedding_generator is None

    def test_returns_empty_when_vector_search_empty(self, agent):
        """If the vector index returns nothing, return an empty list."""
        fake_embedding = [0.1] * 384
        article_df = pd.DataFrame({"embedding": [fake_embedding]})
        empty_df = pd.DataFrame()

        agent.conn.execute.side_effect = [
            _make_execute_result(article_df),
            _make_execute_result(empty_df),
        ]

        results = agent.semantic_search("Machine learning", top_k=5)
        assert results == []


# --------------------------------------------------------------------------
# Fallback path: free-text query generates embedding on the fly
# --------------------------------------------------------------------------
class TestSemanticSearchFreeText:
    """When the query does NOT match an article, generate an embedding."""

    def test_generates_embedding_for_free_text(self, agent):
        """Non-article queries should use the embedding generator fallback."""
        fake_embedding = np.array([[0.2] * 384])

        # First call: article lookup returns empty (no matching title)
        empty_df = pd.DataFrame()
        # Second call: vector search returns results
        vector_df = pd.DataFrame(
            {
                "node": [
                    {"section_id": "Deep learning#overview"},
                    {"section_id": "Neural network#intro"},
                ],
                "distance": [0.1, 0.3],
            }
        )
        agent.conn.execute.side_effect = [
            _make_execute_result(empty_df),
            _make_execute_result(vector_df),
        ]

        mock_generator = MagicMock()
        mock_generator.generate.return_value = fake_embedding

        with patch(
            "bootstrap.src.embeddings.generator.EmbeddingGenerator",
            return_value=mock_generator,
        ):
            results = agent.semantic_search("what is backpropagation", top_k=5)

        assert len(results) == 2
        titles = [r["title"] for r in results]
        assert "Deep learning" in titles
        assert "Neural network" in titles

        # Embedding generator should have been called with the query text
        mock_generator.generate.assert_called_once_with(["what is backpropagation"])

    def test_lazy_initialization_only_once(self, agent):
        """The embedding generator should be created once and reused."""
        fake_embedding = np.array([[0.5] * 384])
        mock_generator = MagicMock()
        mock_generator.generate.return_value = fake_embedding

        empty_df = pd.DataFrame()
        vector_df = pd.DataFrame(
            {
                "node": [{"section_id": "AI#intro"}],
                "distance": [0.2],
            }
        )

        with patch(
            "bootstrap.src.embeddings.generator.EmbeddingGenerator",
            return_value=mock_generator,
        ) as mock_cls:
            # Call semantic_search twice with free-text queries
            agent.conn.execute.side_effect = [
                _make_execute_result(empty_df),
                _make_execute_result(vector_df),
                _make_execute_result(empty_df),
                _make_execute_result(vector_df),
            ]

            agent.semantic_search("first query", top_k=3)
            agent.semantic_search("second query", top_k=3)

        # EmbeddingGenerator constructor should have been called only once
        assert mock_cls.call_count == 1
        # But generate should have been called twice (once per query)
        assert mock_generator.generate.call_count == 2

    def test_deduplicates_articles_across_sections(self, agent):
        """Multiple sections from the same article should be collapsed."""
        fake_embedding = np.array([[0.3] * 384])

        empty_df = pd.DataFrame()
        vector_df = pd.DataFrame(
            {
                "node": [
                    {"section_id": "Deep learning#intro"},
                    {"section_id": "Deep learning#applications"},
                    {"section_id": "Neural network#overview"},
                ],
                "distance": [0.1, 0.2, 0.15],
            }
        )

        agent.conn.execute.side_effect = [
            _make_execute_result(empty_df),
            _make_execute_result(vector_df),
        ]

        mock_generator = MagicMock()
        mock_generator.generate.return_value = fake_embedding

        with patch(
            "bootstrap.src.embeddings.generator.EmbeddingGenerator",
            return_value=mock_generator,
        ):
            results = agent.semantic_search("gradient descent", top_k=10)

        # "Deep learning" appears twice but should be deduplicated (best distance kept)
        assert len(results) == 2
        dl_result = next(r for r in results if r["title"] == "Deep learning")
        assert dl_result["distance"] == pytest.approx(0.1)  # best of 0.1 and 0.2


# --------------------------------------------------------------------------
# Validation and edge cases
# --------------------------------------------------------------------------
class TestSemanticSearchValidation:
    """Parameter validation and close() cleanup."""

    def test_rejects_invalid_top_k(self, agent):
        with pytest.raises(ValueError, match="top_k must be an integer"):
            agent.semantic_search("anything", top_k=0)

        with pytest.raises(ValueError, match="top_k must be an integer"):
            agent.semantic_search("anything", top_k=501)

        with pytest.raises(ValueError, match="top_k must be an integer"):
            agent.semantic_search("anything", top_k="five")

    def test_raises_after_close(self, agent):
        agent.close()
        with pytest.raises(RuntimeError, match="closed"):
            agent.semantic_search("anything")

    def test_close_clears_embedding_generator(self, agent):
        """close() should set _embedding_generator to None."""
        agent._embedding_generator = MagicMock()
        agent.close()
        assert agent._embedding_generator is None


# --------------------------------------------------------------------------
# Priority 5: Vector search as primary retrieval
# --------------------------------------------------------------------------
class TestVectorPrimaryRetrieval:
    """Vector search is primary; LLM Cypher is fallback for low-confidence results."""

    def test_high_confidence_returns_results(self, agent):
        """When max similarity >= 0.6, _vector_primary_retrieve returns results."""
        fake_emb = [0.1] * 384
        agent.conn.execute.side_effect = [
            _make_execute_result(pd.DataFrame({"embedding": [fake_emb]})),
            _make_execute_result(
                pd.DataFrame(
                    {
                        "node": [{"section_id": "Python#intro"}],
                        "distance": [0.05],
                    }
                )
            ),
        ]
        results, max_sim = agent._vector_primary_retrieve("What is Python?", 10)
        assert results is not None
        assert max_sim >= 0.6
        assert "Python" in results["sources"]
        assert results["entities"] == []
        assert results["facts"] == []

    def test_empty_vector_results_returns_none(self, agent):
        """When vector index returns nothing, returns (None, 0.0)."""
        fake_emb = [0.1] * 384
        agent.conn.execute.side_effect = [
            _make_execute_result(pd.DataFrame({"embedding": [fake_emb]})),
            _make_execute_result(pd.DataFrame()),
        ]
        results, max_sim = agent._vector_primary_retrieve("test", 10)
        assert results is None
        assert max_sim == 0.0

    def test_exception_returns_none(self, agent):
        """If vector search raises, returns (None, 0.0) gracefully."""
        agent.conn.execute.side_effect = Exception("DB error")
        results, max_sim = agent._vector_primary_retrieve("test", 10)
        assert results is None
        assert max_sim == 0.0

    def test_low_similarity_returns_results_with_low_sim(self, agent):
        """Low-confidence results are returned with max_sim < 0.6."""
        fake_emb = [0.1] * 384
        agent.conn.execute.side_effect = [
            _make_execute_result(pd.DataFrame({"embedding": [fake_emb]})),
            _make_execute_result(
                pd.DataFrame(
                    {
                        "node": [{"section_id": "Unrelated#intro"}],
                        "distance": [0.9],  # similarity = 0.1
                    }
                )
            ),
        ]
        results, max_sim = agent._vector_primary_retrieve("test", 10)
        assert results is not None
        assert max_sim < 0.6

    def test_query_skips_llm_when_high_confidence(self, agent):
        """query() should not call _plan_query when vector similarity >= 0.6."""
        fake_emb = [0.1] * 384
        agent.conn.execute.side_effect = [
            _make_execute_result(pd.DataFrame({"embedding": [fake_emb]})),
            _make_execute_result(
                pd.DataFrame(
                    {
                        "node": [{"section_id": "Physics#intro"}],
                        "distance": [0.05],
                    }
                )
            ),
        ] + [_make_execute_result(pd.DataFrame())] * 10
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="answer")]
        agent.claude.messages.create.return_value = mock_response

        with patch.object(agent, "_plan_query") as mock_plan:
            result = agent.query("physics question")

        mock_plan.assert_not_called()
        assert result["query_type"] == "vector_search"

    def test_query_never_calls_llm_cypher(self, agent):
        """query() never calls _plan_query — vector-only retrieval (Experiment 2)."""
        fake_emb = [0.1] * 384
        agent.conn.execute.side_effect = [
            _make_execute_result(pd.DataFrame({"embedding": [fake_emb]})),
            _make_execute_result(
                pd.DataFrame(
                    {
                        "node": [{"section_id": "Unrelated#intro"}],
                        "distance": [0.9],
                    }
                )
            ),
        ]
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="answer")]
        agent.claude.messages.create.return_value = mock_response

        with (
            patch.object(agent, "_plan_query") as mock_plan_fn,
            patch.object(agent, "_execute_query") as mock_exec_fn,
            patch.object(agent, "_direct_title_lookup", return_value=[]),
            patch.object(agent, "_hybrid_retrieve", return_value={"sources": [], "facts": []}),
        ):
            result = agent.query("obscure query")

        # LLM Cypher path is completely removed
        mock_plan_fn.assert_not_called()
        mock_exec_fn.assert_not_called()
        assert result["query_type"] == "vector_search"


# --------------------------------------------------------------------------
# Priority 7: A/B testing flags
# --------------------------------------------------------------------------
class TestABTestingFlags:
    """Test enable_reranker, enable_multidoc, enable_fewshot constructor flags."""

    def _make_enhanced_agent(self, **kwargs):
        with (
            patch("wikigr.agent.kg_agent.kuzu") as mock_kuzu,
            patch("wikigr.agent.kg_agent.Anthropic"),
            patch("wikigr.agent.few_shot.FewShotManager"),
            patch("wikigr.agent.multi_doc_synthesis.MultiDocSynthesizer"),
            patch("wikigr.agent.reranker.GraphReranker"),
            patch(
                "wikigr.agent.kg_agent.KnowledgeGraphAgent._resolve_few_shot_path",
                return_value="/fake/few_shot.json",
            ),
        ):
            mock_kuzu.Database.return_value = MagicMock()
            mock_kuzu.Connection.return_value = MagicMock()
            from wikigr.agent.kg_agent import KnowledgeGraphAgent

            return KnowledgeGraphAgent(db_path="/fake/db", use_enhancements=True, **kwargs)

    def test_all_enabled_by_default(self):
        """With use_enhancements=True, all 3 components default to enabled."""
        agent = self._make_enhanced_agent()
        assert agent.reranker is not None
        assert agent.synthesizer is not None
        assert agent.few_shot is not None
        assert agent.enable_reranker is True
        assert agent.enable_multidoc is True
        assert agent.enable_fewshot is True

    def test_disable_reranker(self):
        """enable_reranker=False: reranker is None, others active."""
        agent = self._make_enhanced_agent(enable_reranker=False)
        assert agent.reranker is None
        assert agent.synthesizer is not None
        assert agent.enable_reranker is False

    def test_disable_multidoc(self):
        """enable_multidoc=False: synthesizer is None, others active."""
        agent = self._make_enhanced_agent(enable_multidoc=False)
        assert agent.synthesizer is None
        assert agent.reranker is not None
        assert agent.enable_multidoc is False

    def test_disable_fewshot(self):
        """enable_fewshot=False: few_shot is None, others active."""
        agent = self._make_enhanced_agent(enable_fewshot=False)
        assert agent.few_shot is None
        assert agent.reranker is not None
        assert agent.enable_fewshot is False

    def test_all_disabled(self):
        """All flags False: all components are None."""
        agent = self._make_enhanced_agent(
            enable_reranker=False, enable_multidoc=False, enable_fewshot=False
        )
        assert agent.reranker is None
        assert agent.synthesizer is None
        assert agent.few_shot is None

    def test_from_connection_sets_defaults(self):
        """from_connection() initializes new attributes to safe defaults."""
        with patch("wikigr.agent.kg_agent.kuzu"), patch("wikigr.agent.kg_agent.Anthropic"):
            from wikigr.agent.kg_agent import KnowledgeGraphAgent

            ag = KnowledgeGraphAgent.from_connection(MagicMock(), MagicMock())
        assert ag.use_enhancements is False
        assert ag.enable_reranker is True
        assert ag.enable_multidoc is True
        assert ag.enable_fewshot is True
        assert ag.reranker is None
        assert ag.synthesizer is None
        assert ag.few_shot is None
