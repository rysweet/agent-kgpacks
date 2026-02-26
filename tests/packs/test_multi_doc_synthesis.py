"""Tests for multi-document synthesis functionality.

This module tests the MultiDocSynthesizer which expands search results by
traversing the knowledge graph and synthesizing content with citations.

TDD Approach: These tests are written BEFORE implementation and will fail initially.
"""

from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer


@pytest.fixture
def mock_kuzu_conn():
    """Create a mock Kuzu connection for testing."""
    conn = MagicMock()
    return conn


@pytest.fixture
def synthesizer(mock_kuzu_conn):
    """Create a MultiDocSynthesizer instance with mock connection."""
    return MultiDocSynthesizer(mock_kuzu_conn)


class TestExpandToRelatedArticles:
    """Test MultiDocSynthesizer.expand_to_related_articles() with various graph structures."""

    def test_expand_zero_hops(self, synthesizer, mock_kuzu_conn):
        """Test expansion with zero hops returns only seed articles."""
        seed_articles = [1, 2, 3]

        # Mock article content retrieval
        mock_result = Mock()
        mock_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3],
                "title": ["Article 1", "Article 2", "Article 3"],
                "content": ["Content 1", "Content 2", "Content 3"],
            }
        )
        mock_kuzu_conn.execute.return_value = mock_result

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=0)

        assert len(expanded) == 3
        assert all(aid in [1, 2, 3] for aid in expanded)

    def test_expand_one_hop(self, synthesizer, mock_kuzu_conn):
        """Test expansion with one hop includes immediate neighbors."""
        seed_articles = [1]

        # First call: Get neighbors
        # Second call: Get article content
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame({"article_id": [2, 3], "hop": [1, 1]})

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3],
                "title": ["Seed", "Neighbor 1", "Neighbor 2"],
                "content": ["Seed content", "Neighbor 1 content", "Neighbor 2 content"],
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=1)

        assert len(expanded) == 3
        assert 1 in expanded  # Seed
        assert 2 in expanded  # Neighbor
        assert 3 in expanded  # Neighbor

    def test_expand_two_hops(self, synthesizer, mock_kuzu_conn):
        """Test expansion with two hops includes 2-hop neighbors."""
        seed_articles = [1]

        # BFS traversal: discover articles at each hop level
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [2, 3, 4, 5], "hop": [1, 1, 2, 2]}
        )

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4, 5],
                "title": ["Seed", "Hop1-A", "Hop1-B", "Hop2-A", "Hop2-B"],
                "content": ["Content"] * 5,
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=2)

        assert len(expanded) == 5
        assert all(aid in [1, 2, 3, 4, 5] for aid in expanded)

    def test_expand_multiple_seeds(self, synthesizer, mock_kuzu_conn):
        """Test expansion from multiple seed articles."""
        seed_articles = [1, 2]

        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [3, 4, 5], "hop": [1, 1, 1]}
        )

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4, 5],
                "title": ["Seed1", "Seed2", "N1", "N2", "N3"],
                "content": ["Content"] * 5,
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=1)

        assert len(expanded) == 5

    def test_expand_removes_duplicates(self, synthesizer, mock_kuzu_conn):
        """Test that duplicate articles are removed during expansion."""
        seed_articles = [1, 2]

        # Article 3 is neighbor to both seeds
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [3, 3, 4],  # Duplicate 3
                "hop": [1, 1, 1],
            }
        )

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4],
                "title": ["Seed1", "Seed2", "Shared", "N1"],
                "content": ["Content"] * 4,
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=1)

        # Article 3 should appear only once
        assert len(expanded) == 4
        assert list(expanded.keys()).count(3) == 1

    def test_expand_disconnected_articles(self, synthesizer, mock_kuzu_conn):
        """Test expansion of disconnected articles (no neighbors)."""
        seed_articles = [1, 2]

        # No neighbors found
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame({"article_id": [], "hop": []})

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2],
                "title": ["Isolated1", "Isolated2"],
                "content": ["Content1", "Content2"],
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=1)

        # Should return only seeds
        assert len(expanded) == 2
        assert all(aid in [1, 2] for aid in expanded)


class TestSynthesizeWithCitations:
    """Test MultiDocSynthesizer.synthesize_with_citations() for citation formatting."""

    def test_synthesize_single_article(self, synthesizer):
        """Test synthesis with single article produces [1] citations."""
        articles = {1: {"title": "Physics", "content": "Physics is the study of matter."}}

        result = synthesizer.synthesize_with_citations(articles, "What is physics?")

        assert "[1]" in result
        assert "Physics" in result
        assert "References:" in result or "Sources:" in result

    def test_synthesize_multiple_articles(self, synthesizer):
        """Test synthesis with multiple articles produces sequential citations."""
        articles = {
            1: {"title": "Physics", "content": "Physics is the study of matter."},
            2: {"title": "Chemistry", "content": "Chemistry is the study of substances."},
            3: {"title": "Biology", "content": "Biology is the study of life."},
        }

        result = synthesizer.synthesize_with_citations(articles, "What are the sciences?")

        # Should contain all citation numbers
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result

    def test_synthesize_truncates_long_content(self, synthesizer):
        """Test that long article content is truncated to 500 chars."""
        long_content = "A" * 1000  # 1000 chars
        articles = {1: {"title": "Long Article", "content": long_content}}

        result = synthesizer.synthesize_with_citations(articles, "Test query")

        # Content should be truncated
        citation_section = (
            result.split("References:")[1]
            if "References:" in result
            else result.split("Sources:")[1]
        )
        # Check that the content in citation is truncated
        assert len(citation_section) < len(long_content) + 100  # Some buffer for formatting

    def test_synthesize_citation_format(self, synthesizer):
        """Test citation format: [1] Title - Content..."""
        articles = {1: {"title": "Test Article", "content": "Test content here."}}

        result = synthesizer.synthesize_with_citations(articles, "Test query")

        # Should have reference section with proper format
        assert "Test Article" in result
        assert "Test content" in result

    def test_synthesize_preserves_citation_order(self, synthesizer):
        """Test that citations are numbered in consistent order."""
        articles = {
            5: {"title": "Article Five", "content": "Content 5"},
            2: {"title": "Article Two", "content": "Content 2"},
            8: {"title": "Article Eight", "content": "Content 8"},
        }

        result = synthesizer.synthesize_with_citations(articles, "Test query")

        # Citations should be sequential [1], [2], [3] regardless of article IDs
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result

    def test_synthesize_empty_articles(self, synthesizer):
        """Test synthesis with empty article set."""
        result = synthesizer.synthesize_with_citations({}, "Test query")

        assert "no articles" in result.lower() or "not found" in result.lower()


class TestBFSTraversal:
    """Test BFS traversal logic in expansion."""

    def test_bfs_respects_max_hops(self, synthesizer, mock_kuzu_conn):
        """Test that BFS stops at max_hops depth."""
        seed_articles = [1]

        # Graph has 3 hop levels, but we limit to 2
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [2, 3, 4, 5, 6],
                "hop": [1, 1, 2, 2, 3],  # Hop 3 should be excluded
            }
        )

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4, 5],  # No article 6
                "title": ["S", "H1-A", "H1-B", "H2-A", "H2-B"],
                "content": ["C"] * 5,
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=2)

        # Should not include hop 3 article (ID 6)
        assert 6 not in expanded
        assert len(expanded) == 5

    def test_bfs_explores_breadth_first(self, synthesizer, mock_kuzu_conn):
        """Test that BFS explores all hop-1 nodes before hop-2."""
        seed_articles = [1]

        # Neighbors at different hop levels
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame(
            {"article_id": [2, 3, 4, 5], "hop": [1, 1, 2, 2]}
        )

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3, 4, 5],
                "title": ["S", "H1-A", "H1-B", "H2-A", "H2-B"],
                "content": ["C"] * 5,
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=2)

        # All hop-1 and hop-2 nodes should be present
        assert all(aid in expanded for aid in [1, 2, 3, 4, 5])


class TestContentFormatting:
    """Test content formatting and truncation."""

    def test_truncate_at_500_chars(self, synthesizer):
        """Test content truncation at exactly 500 characters."""
        long_content = "X" * 1000
        articles = {1: {"title": "Long", "content": long_content}}

        result = synthesizer.synthesize_with_citations(articles, "Query")

        # Extract citation content
        lines = result.split("\n")
        citation_line = next((line for line in lines if "Long" in line), "")

        # Should not contain full 1000 chars
        assert len(citation_line) < 600  # 500 + formatting buffer

    def test_truncate_adds_ellipsis(self, synthesizer):
        """Test that truncated content ends with ellipsis."""
        long_content = "Content " * 100
        articles = {1: {"title": "Article", "content": long_content}}

        result = synthesizer.synthesize_with_citations(articles, "Query")

        # Should have ellipsis for truncated content
        assert "..." in result or "…" in result

    def test_short_content_not_truncated(self, synthesizer):
        """Test that content under 500 chars is not truncated."""
        short_content = "Short content here."
        articles = {1: {"title": "Short", "content": short_content}}

        result = synthesizer.synthesize_with_citations(articles, "Query")

        assert short_content in result

    def test_markdown_citation_format(self, synthesizer):
        """Test that citations use markdown link format."""
        articles = {1: {"title": "Test", "content": "Content", "url": "http://example.com"}}

        result = synthesizer.synthesize_with_citations(articles, "Query")

        # Should have markdown link format [text](url) or [1]
        assert "[1]" in result


class TestIntegration:
    """Integration tests for complete synthesis workflow."""

    def test_full_workflow_expand_and_synthesize(self, synthesizer, mock_kuzu_conn):
        """Test complete workflow: expand then synthesize."""
        seed_articles = [1]

        # Mock expansion
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame({"article_id": [2, 3], "hop": [1, 1]})

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2, 3],
                "title": ["Main", "Related1", "Related2"],
                "content": ["Main content", "Related content 1", "Related content 2"],
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        # Expand
        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=1)

        # Synthesize
        result = synthesizer.synthesize_with_citations(expanded, "What is the topic?")

        # Should have 3 citations
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result
        assert "Main" in result
        assert "Related1" in result

    def test_stub_article_handling(self, synthesizer, mock_kuzu_conn):
        """Test handling of stub articles (very short content)."""
        seed_articles = [1]

        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame({"article_id": [2], "hop": [1]})

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": [1, 2],
                "title": ["Main", "Stub"],
                "content": ["Full article with content", "Short."],  # Stub
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(seed_articles, max_hops=1)
        result = synthesizer.synthesize_with_citations(expanded, "Query")

        # Stub should still be included
        assert "Stub" in result
        assert len(expanded) == 2

    def test_max_articles_limit(self, synthesizer, mock_kuzu_conn):
        """Test that expansion respects max_articles limit."""
        seed_articles = [1]

        # Many neighbors available
        neighbor_result = Mock()
        neighbor_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": list(range(2, 102)),  # 100 neighbors
                "hop": [1] * 100,
            }
        )

        content_result = Mock()
        content_result.get_as_df.return_value = pd.DataFrame(
            {
                "article_id": list(range(1, 52)),  # Limit to 51
                "title": [f"Article {i}" for i in range(1, 52)],
                "content": ["Content"] * 51,
            }
        )

        mock_kuzu_conn.execute.side_effect = [neighbor_result, content_result]

        expanded = synthesizer.expand_to_related_articles(
            seed_articles, max_hops=1, max_articles=50
        )

        # Should not exceed max_articles
        assert len(expanded) <= 50
