"""
Tests for RyuGraphOrchestrator._process_one keyword-argument contract.

Regression suite for the bug where `process_article` was called with
the positional keyword `title=title` instead of the correct parameter
name `title_or_url=title`, which would raise:
    TypeError: process_article() got an unexpected keyword argument 'title'

Tests pass with the corrected call site (`title_or_url=title`) and
would fail if the old call (`title=title`) were reinstated.
"""

from unittest.mock import MagicMock, patch

import pytest

from bootstrap.src.expansion.orchestrator import RyuGraphOrchestrator

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_article_info(title="Python (programming language)", depth=0, category="Technology"):
    return {"title": title, "expansion_depth": depth, "category": category}


@pytest.fixture
def orch_with_mocks():
    """Yield (orch, worker_conn, mock_processor, mock_link_disc) with deps patched."""
    worker_conn = MagicMock()
    mock_processor = MagicMock()
    mock_link_disc = MagicMock()
    mock_link_disc.discover_links.return_value = 0  # int: count of new articles

    with (
        patch(
            "bootstrap.src.expansion.orchestrator.ArticleProcessor",
            return_value=mock_processor,
        ),
        patch("bootstrap.src.expansion.orchestrator.WorkQueueManager"),
        patch(
            "bootstrap.src.expansion.orchestrator.LinkDiscovery",
            return_value=mock_link_disc,
        ),
        patch("bootstrap.src.expansion.orchestrator.kuzu"),
    ):
        orch = object.__new__(RyuGraphOrchestrator)
        orch.max_depth = 2
        orch._shared_embedding_generator = MagicMock()
        yield orch, worker_conn, mock_processor, mock_link_disc


# ---------------------------------------------------------------------------
# Unit tests – _process_one keyword argument contract
# ---------------------------------------------------------------------------


class TestProcessOneKeywordArgContract:
    """_process_one must call process_article with title_or_url=, not title=."""

    def test_process_article_called_with_title_or_url_keyword(self, orch_with_mocks):
        """The keyword argument passed to process_article must be title_or_url."""
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        mock_processor.process_article.return_value = (True, ["Link A"], None)

        orch._process_one(_make_article_info("Python (programming language)", depth=0), worker_conn)

        _, kwargs = mock_processor.process_article.call_args
        assert (
            "title_or_url" in kwargs
        ), f"process_article must be called with title_or_url=, but was called with kwargs: {kwargs}"

    def test_process_article_not_called_with_title_keyword(self, orch_with_mocks):
        """The forbidden legacy keyword 'title' must NOT appear in the call."""
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        mock_processor.process_article.return_value = (True, [], None)

        orch._process_one(_make_article_info("Recursion", depth=0), worker_conn)

        _, kwargs = mock_processor.process_article.call_args
        assert (
            "title" not in kwargs
        ), f"process_article must NOT be called with the legacy keyword 'title', but kwargs were: {kwargs}"

    def test_title_value_forwarded_correctly(self, orch_with_mocks):
        """The article title string must be the value of title_or_url."""
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        mock_processor.process_article.return_value = (True, [], None)

        orch._process_one(_make_article_info("Turing completeness", depth=1), worker_conn)

        _, kwargs = mock_processor.process_article.call_args
        assert kwargs["title_or_url"] == "Turing completeness"


# ---------------------------------------------------------------------------
# Unit tests – _process_one other keyword arguments
# ---------------------------------------------------------------------------


class TestProcessOneOtherArgs:
    """Verify the remaining kwargs passed to process_article are correct."""

    def test_category_forwarded_from_article_info(self, orch_with_mocks):
        """category from article_info must be forwarded to process_article."""
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        mock_processor.process_article.return_value = (True, [], None)

        orch._process_one(_make_article_info("AI", depth=0, category="Science"), worker_conn)

        _, kwargs = mock_processor.process_article.call_args
        assert kwargs["category"] == "Science"

    def test_category_defaults_to_general_when_absent(self, orch_with_mocks):
        """When article_info has no category, process_article gets 'General'."""
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        mock_processor.process_article.return_value = (True, [], None)

        orch._process_one({"title": "Recursion", "expansion_depth": 0}, worker_conn)

        _, kwargs = mock_processor.process_article.call_args
        assert kwargs["category"] == "General"

    def test_expansion_depth_forwarded(self, orch_with_mocks):
        """expansion_depth from article_info must be forwarded to process_article."""
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        # depth=2 equals max_depth=2 so discover_links won't be called
        mock_processor.process_article.return_value = (True, [], None)

        orch._process_one(_make_article_info("Fibonacci", depth=2), worker_conn)

        _, kwargs = mock_processor.process_article.call_args
        assert kwargs["expansion_depth"] == 2


# ---------------------------------------------------------------------------
# Unit tests – _process_one return value contract
# ---------------------------------------------------------------------------


class TestProcessOneReturnValue:
    """_process_one must return (title, success, error_or_None)."""

    def test_returns_tuple_on_success(self, orch_with_mocks):
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        mock_processor.process_article.return_value = (True, ["L1", "L2"], None)

        result = orch._process_one(_make_article_info("Graph theory", depth=0), worker_conn)

        title, success, error = result
        assert title == "Graph theory"
        assert success is True
        assert error is None

    def test_returns_tuple_on_failure(self, orch_with_mocks):
        orch, worker_conn, mock_processor, _ = orch_with_mocks
        mock_processor.process_article.return_value = (False, [], "Article not found: Graph theory")

        result = orch._process_one(_make_article_info("Graph theory", depth=0), worker_conn)

        title, success, error = result
        assert title == "Graph theory"
        assert success is False
        assert error is not None

    def test_mark_failed_called_on_failure_path(self):
        """On process_article failure, mark_failed must be called with the article title."""
        worker_conn = MagicMock()
        mock_processor = MagicMock()
        mock_processor.process_article.return_value = (False, [], "fetch error")
        mock_queue_cls = MagicMock()
        mock_queue_instance = MagicMock()
        mock_queue_cls.return_value = mock_queue_instance

        with (
            patch(
                "bootstrap.src.expansion.orchestrator.ArticleProcessor", return_value=mock_processor
            ),
            patch("bootstrap.src.expansion.orchestrator.WorkQueueManager", mock_queue_cls),
            patch("bootstrap.src.expansion.orchestrator.LinkDiscovery"),
            patch("bootstrap.src.expansion.orchestrator.kuzu"),
        ):
            orch = object.__new__(RyuGraphOrchestrator)
            orch.max_depth = 2
            orch._shared_embedding_generator = MagicMock()
            orch._process_one(_make_article_info("Failing Article", depth=0), worker_conn)

        mock_queue_instance.mark_failed.assert_called_once_with("Failing Article", "fetch error")


# ---------------------------------------------------------------------------
# Integration-style test – ArticleProcessor.process_article real signature
# ---------------------------------------------------------------------------


class TestProcessArticleSignature:
    """Verify ArticleProcessor.process_article accepts title_or_url= kwarg."""

    def test_process_article_accepts_title_or_url_keyword(self):
        """Calling process_article(title_or_url=...) must not raise TypeError."""
        import inspect

        from bootstrap.src.expansion.processor import ArticleProcessor

        params = list(inspect.signature(ArticleProcessor.process_article).parameters)
        assert (
            "title_or_url" in params
        ), f"ArticleProcessor.process_article must have 'title_or_url' parameter; found: {params}"

    def test_process_article_does_not_have_title_parameter(self):
        """ArticleProcessor.process_article must NOT have a bare 'title' parameter."""
        import inspect

        from bootstrap.src.expansion.processor import ArticleProcessor

        params = list(inspect.signature(ArticleProcessor.process_article).parameters)
        assert (
            "title" not in params
        ), f"ArticleProcessor.process_article must NOT have 'title' parameter; found: {params}"

    def test_calling_with_title_kwarg_raises_type_error(self):
        """Calling process_article(title=...) must raise TypeError – legacy regression guard."""
        with patch("bootstrap.src.expansion.processor.kuzu"):
            from bootstrap.src.expansion.processor import ArticleProcessor

            processor = object.__new__(ArticleProcessor)
            processor.conn = MagicMock()
            processor.embedding_generator = MagicMock()
            processor.llm_extractor = None
            processor.content_source = MagicMock()

            with pytest.raises(TypeError, match="unexpected keyword argument"):
                processor.process_article(title="Python", category="Tech", expansion_depth=0)
