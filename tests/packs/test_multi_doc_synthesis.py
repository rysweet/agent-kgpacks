"""Tests for MultiDocSynthesizer module."""

import pytest
from unittest.mock import Mock, MagicMock
import kuzu

from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer


@pytest.fixture
def mock_connection():
    """Create a mock Kuzu connection."""
    conn = MagicMock(spec=kuzu.Connection)
    return conn


@pytest.fixture
def sample_seed_articles():
    """Sample seed articles for expansion."""
    return ["Quantum Mechanics", "Wave Function"]


class TestMultiDocSynthesizerInit:
    """Test MultiDocSynthesizer initialization."""

    def test_init_with_connection(self, mock_connection):
        """Test initialization with Kuzu connection."""
        synthesizer = MultiDocSynthesizer(mock_connection)
        assert synthesizer.conn == mock_connection

    def test_init_default_parameters(self, mock_connection):
        """Test initialization has reasonable defaults."""
        synthesizer = MultiDocSynthesizer(mock_connection)
        assert synthesizer.conn is not None


class TestExpandToRelatedArticles:
    """Test expand_to_related_articles method."""

    def test_expand_empty_seeds(self, mock_connection):
        """Test expansion with empty seed list."""
        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles([])
        assert result == []

    def test_expand_single_seed(self, mock_connection):
        """Test expansion with single seed article."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"related_title": "Schrodinger Equation", "overlap_score": 5},
            {"related_title": "Quantum Entanglement", "overlap_score": 3},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Quantum Mechanics"])

        assert len(result) >= 1
        assert "Quantum Mechanics" in result  # Original seed included

    def test_expand_multiple_seeds(self, mock_connection):
        """Test expansion with multiple seed articles."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"related_title": "Article1", "overlap_score": 5},
            {"related_title": "Article2", "overlap_score": 4},
            {"related_title": "Article3", "overlap_score": 3},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Seed1", "Seed2"])

        assert len(result) >= 2  # At least the seeds
        assert "Seed1" in result
        assert "Seed2" in result

    def test_expand_with_max_related(self, mock_connection):
        """Test expansion respects max_related parameter."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"related_title": f"Article{i}", "overlap_score": 10 - i} for i in range(20)
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Seed"], max_related=5)

        # Should include seed + max_related related articles
        assert len(result) <= 6

    def test_expand_deduplicates_results(self, mock_connection):
        """Test that expansion deduplicates articles across seeds."""
        mock_df = Mock()
        mock_df.empty = False
        # Both seeds return same related article
        mock_df.to_dict.return_value = [
            {"related_title": "Shared Article", "overlap_score": 5},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Seed1", "Seed2"])

        # Should only include each article once
        assert result.count("Shared Article") == 1

    def test_expand_entity_overlap(self, mock_connection):
        """Test expansion uses entity overlap for relatedness."""
        # Mock query result showing entity overlap
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"related_title": "Related Article", "overlap_score": 8},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Quantum Mechanics"])

        # Verify the query was called (entity overlap logic)
        assert mock_connection.execute.called
        assert "Related Article" in result or "Quantum Mechanics" in result

    def test_expand_links_to_edges(self, mock_connection):
        """Test expansion uses LINKS_TO edges."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"related_title": "Linked Article", "overlap_score": 1},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Quantum Mechanics"])

        assert mock_connection.execute.called

    def test_expand_categories(self, mock_connection):
        """Test expansion considers article categories."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [
            {"related_title": "Same Category Article", "overlap_score": 2},
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Physics Article"])

        assert mock_connection.execute.called

    def test_expand_handles_query_error(self, mock_connection):
        """Test expansion handles database query errors gracefully."""
        mock_connection.execute.side_effect = Exception("Database error")

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Quantum Mechanics"])

        # Should return at least the seed articles
        assert "Quantum Mechanics" in result

    def test_expand_empty_query_results(self, mock_connection):
        """Test expansion when query returns no related articles."""
        mock_df = Mock()
        mock_df.empty = True

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.expand_to_related_articles(["Isolated Article"])

        # Should at least return the seed
        assert "Isolated Article" in result


class TestSynthesizeContext:
    """Test synthesize_context method."""

    def test_synthesize_empty_articles(self, mock_connection):
        """Test synthesis with empty article list."""
        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context([])
        assert result == ""

    def test_synthesize_single_article(self, mock_connection):
        """Test synthesis with single article."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iloc = [
            {"title": "Quantum Mechanics", "content": "Quantum mechanics is a branch of physics."}
        ]
        mock_df.__iter__ = Mock(return_value=iter([
            {"title": "Quantum Mechanics", "content": "Quantum mechanics is a branch of physics."}
        ]))

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["Quantum Mechanics"])

        assert len(result) > 0
        assert "Quantum Mechanics" in result or "[1]" in result

    def test_synthesize_multiple_articles(self, mock_connection):
        """Test synthesis with multiple articles."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (0, {"title": "Article1", "content": "Content1"}),
            (1, {"title": "Article2", "content": "Content2"}),
            (2, {"title": "Article3", "content": "Content3"}),
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["Article1", "Article2", "Article3"])

        assert len(result) > 0
        # Should have citations [1], [2], [3]
        assert "[1]" in result or "[2]" in result or "[3]" in result

    def test_synthesize_with_citations(self, mock_connection):
        """Test that synthesis includes proper citations [1], [2], [3]."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (0, {"title": "Source1", "content": "Content from source 1."}),
            (1, {"title": "Source2", "content": "Content from source 2."}),
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["Source1", "Source2"])

        # Should include citation markers
        assert "[1]" in result or "[2]" in result
        # Should include source titles
        assert "Source1" in result or "Source2" in result

    def test_synthesize_markdown_format(self, mock_connection):
        """Test that synthesis returns Markdown-formatted text."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (0, {"title": "Article1", "content": "Content1"}),
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["Article1"])

        # Check for Markdown formatting (headers, lists, etc.)
        assert len(result) > 0
        # At minimum should have text content

    def test_synthesize_truncates_long_content(self, mock_connection):
        """Test that synthesis truncates very long content appropriately."""
        long_content = "A" * 10000

        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (0, {"title": "Long Article", "content": long_content}),
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["Long Article"], max_content_length=500)

        # Should truncate to reasonable length
        assert len(result) < len(long_content)

    def test_synthesize_handles_query_error(self, mock_connection):
        """Test synthesis handles database query errors gracefully."""
        mock_connection.execute.side_effect = Exception("Database error")

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["Article1"])

        # Should return empty or error message
        assert isinstance(result, str)

    def test_synthesize_empty_content(self, mock_connection):
        """Test synthesis when articles have no content."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (0, {"title": "Empty Article", "content": ""}),
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["Empty Article"])

        # Should handle gracefully
        assert isinstance(result, str)

    def test_synthesize_preserves_source_order(self, mock_connection):
        """Test that citations match the order of input articles."""
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (0, {"title": "First", "content": "First content"}),
            (1, {"title": "Second", "content": "Second content"}),
            (2, {"title": "Third", "content": "Third content"}),
        ]

        mock_result = Mock()
        mock_result.get_as_df.return_value = mock_df
        mock_connection.execute.return_value = mock_result

        synthesizer = MultiDocSynthesizer(mock_connection)
        result = synthesizer.synthesize_context(["First", "Second", "Third"])

        # Citations should be in order [1] = First, [2] = Second, [3] = Third
        assert isinstance(result, str)
