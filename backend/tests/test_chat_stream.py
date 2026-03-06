"""
Tests for the GET /api/v1/chat/stream SSE endpoint.

TDD specification for the chat_stream fix:
- generator MUST call agent.query(), not the deleted private methods
  _plan_query / _execute_query / _build_synthesis_context
- SSE stream must emit: sources → token → done
- Error handling must emit an 'error' event on failure
- Input validation must reject invalid query parameters

Note on status codes: the app's RequestValidationError handler (main.py:131)
converts FastAPI's default 422 to 400.

Note on event loop: sse-starlette 2.x binds AppStatus.should_exit_event to the
event loop created when the first SSE request is handled.  Using a module-scoped
fixture (single TestClient per module) avoids the "different event loop" error
that occurs when each test creates its own TestClient.
"""

import json
import os
import shutil
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _parse_sse(text: str) -> list[tuple[str, str]]:
    """Parse a raw SSE response body into a list of (event_type, data) tuples."""
    events = []
    current_event = None
    current_data_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data_lines.append(line[len("data:") :].strip())
        elif line == "" and current_event is not None:
            events.append((current_event, "\n".join(current_data_lines)))
            current_event = None
            current_data_lines = []

    # Flush a trailing event with no blank-line terminator
    if current_event is not None:
        events.append((current_event, "\n".join(current_data_lines)))

    return events


@pytest.fixture(autouse=True)
def reset_sse_app_status():
    """
    Reset sse-starlette's AppStatus.should_exit_event before and after each test.

    sse-starlette 2.x creates an anyio.Event bound to the current event loop the
    first time a streaming response is served.  Subsequent SSE requests running in
    a *different* event loop context (as each starlette TestClient request does) try
    to await the same Event object and raise "bound to a different event loop".

    Setting it to None before each test forces sse-starlette to create a fresh
    Event in the correct event loop for that request.
    """
    try:
        from sse_starlette.sse import AppStatus

        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass
    yield
    try:
        from sse_starlette.sse import AppStatus

        AppStatus.should_exit_event = None
    except (ImportError, AttributeError):
        pass


@pytest.fixture(scope="module")
def stream_client(tmp_path_factory):
    """
    Module-scoped TestClient with a throwaway Kuzu database.

    Module scope is required because sse-starlette 2.x binds
    AppStatus.should_exit_event to the first event loop it sees.
    Re-creating a TestClient in a different test (with a new event loop)
    causes a "bound to a different event loop" RuntimeError.  By keeping
    one client for the whole module we stay on one loop throughout.
    """
    import real_ladybug as kuzu

    tmp_path = tmp_path_factory.mktemp("stream_db")
    db_path = str(tmp_path / "stream_test.db")
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Article(title STRING, PRIMARY KEY(title))")
    del conn, db

    os.environ["WIKIGR_DATABASE_PATH"] = db_path
    os.environ["WIKIGR_RATE_LIMIT_ENABLED"] = "false"

    from backend.db.connection import ConnectionManager

    ConnectionManager._instance = None

    from backend.main import app

    client = TestClient(app)
    yield client

    ConnectionManager._instance = None
    shutil.rmtree(db_path, ignore_errors=True)


def _make_happy_path_mocks(mock_result: dict):
    """Return (mock_agent, mock_manager) for a happy-path stream test."""
    mock_agent = MagicMock()
    mock_agent.query.return_value = mock_result

    mock_conn = MagicMock()
    mock_manager = MagicMock()
    mock_manager.get_connection.return_value = mock_conn
    return mock_agent, mock_manager


class TestChatStreamInputValidation:
    """Input validation for GET /api/v1/chat/stream.

    The app's RequestValidationError handler converts FastAPI's 422 → 400
    (see backend/main.py:131-163), so we assert 400.
    """

    def test_returns_503_when_no_api_key(self, stream_client):
        """Should return 503 JSON (not SSE) when ANTHROPIC_API_KEY is absent."""
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?"},
            )
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "AGENT_UNAVAILABLE"

    def test_rejects_empty_question(self, stream_client):
        """Should return 400 when question is empty string (R-IV-1: min_length=1)."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": ""},
            )
        assert response.status_code == 400

    def test_rejects_question_exceeding_500_chars(self, stream_client):
        """Should return 400 when question length > 500 (app converts 422 → 400)."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "q" * 501},
            )
        assert response.status_code == 400

    def test_accepts_question_at_max_length(self, stream_client):
        """Should not reject a 500-char question (boundary value)."""
        mock_result = {"answer": "ok", "sources": [], "query_type": "entity_search"}
        mock_agent, mock_manager = _make_happy_path_mocks(mock_result)

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "q" * 500},
            )
        assert response.status_code == 200

    def test_rejects_max_results_below_1(self, stream_client):
        """Should return 400 when max_results < 1 (app converts 422 → 400)."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?", "max_results": 0},
            )
        assert response.status_code == 400

    def test_rejects_max_results_above_50(self, stream_client):
        """Should return 400 when max_results > 50 (app converts 422 → 400)."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?", "max_results": 51},
            )
        assert response.status_code == 400

    def test_accepts_max_results_minimum_boundary(self, stream_client):
        """Should accept max_results=1 (lower inclusive boundary)."""
        mock_result = {"answer": "ok", "sources": [], "query_type": "entity_search"}
        mock_agent, mock_manager = _make_happy_path_mocks(mock_result)

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            r = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?", "max_results": 1},
            )
        assert r.status_code == 200

    def test_accepts_max_results_maximum_boundary(self, stream_client):
        """Should accept max_results=50 (upper inclusive boundary)."""
        mock_result = {"answer": "ok", "sources": [], "query_type": "entity_search"}
        mock_agent, mock_manager = _make_happy_path_mocks(mock_result)

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            r = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?", "max_results": 50},
            )
        assert r.status_code == 200


class TestChatStreamAgentCall:
    """The generator must delegate to agent.query(), not deleted private methods."""

    def test_calls_agent_query_with_correct_args(self, stream_client):
        """
        CRITICAL regression: generator must call agent.query(question=..., max_results=...).

        If the old broken code were still present (calling _plan_query /
        _execute_query / _build_synthesis_context), mock_agent.query would
        never be invoked and the test would fail.
        """
        mock_result = {
            "answer": "AI is artificial intelligence.",
            "sources": ["Artificial intelligence"],
            "query_type": "entity_search",
        }
        mock_agent, mock_manager = _make_happy_path_mocks(mock_result)

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?", "max_results": 15},
            )

        mock_agent.query.assert_called_once_with(question="What is AI?", max_results=15)

    def test_does_not_call_deleted_private_methods(self, stream_client):
        """
        Verify _plan_query, _execute_query, _build_synthesis_context are NOT called.

        These methods were deleted in the dead-code cleanup; any call to them
        would raise AttributeError at runtime.
        """
        mock_result = {"answer": "ok", "sources": [], "query_type": "entity_search"}
        mock_agent, mock_manager = _make_happy_path_mocks(mock_result)

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "Tell me about X."},
            )

        for deleted_method in ("_plan_query", "_execute_query", "_build_synthesis_context"):
            child_mock = getattr(mock_agent, deleted_method, None)
            if child_mock is not None:
                child_mock.assert_not_called()

    def test_passes_default_max_results_10(self, stream_client):
        """max_results defaults to 10 when not supplied."""
        mock_result = {"answer": "ok", "sources": [], "query_type": "entity_search"}
        mock_agent, mock_manager = _make_happy_path_mocks(mock_result)

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?"},
            )

        mock_agent.query.assert_called_once_with(question="What is AI?", max_results=10)


class TestChatStreamSSEEvents:
    """SSE event contract: sources → token → done in that order."""

    def _stream(self, stream_client, mock_result, question="What is AI?", **params):
        """Helper: run a stream request and return parsed SSE events."""
        mock_agent, mock_manager = _make_happy_path_mocks(mock_result)

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": question, **params},
            )

        assert response.status_code == 200
        return _parse_sse(response.text)

    def test_event_order_is_sources_token_done(self, stream_client):
        """SSE events must arrive in order: sources → token → done."""
        events = self._stream(
            stream_client,
            {"answer": "Test answer.", "sources": ["Article A"], "query_type": "entity_search"},
        )
        event_types = [t for t, _ in events]
        assert event_types == [
            "sources",
            "token",
            "done",
        ], f"Expected ['sources', 'token', 'done'], got {event_types}"

    def test_sources_event_contains_json_array(self, stream_client):
        """'sources' event data must be a JSON array of article title strings."""
        events = self._stream(
            stream_client,
            {
                "answer": "AI is artificial intelligence.",
                "sources": ["Artificial intelligence", "Machine learning"],
                "query_type": "entity_search",
            },
        )
        sources_events = [(t, d) for t, d in events if t == "sources"]
        assert len(sources_events) == 1
        data = json.loads(sources_events[0][1])
        assert data == ["Artificial intelligence", "Machine learning"]

    def test_token_event_contains_answer_text(self, stream_client):
        """'token' event data must be the plain-text answer string."""
        events = self._stream(
            stream_client,
            {
                "answer": "AI is artificial intelligence.",
                "sources": [],
                "query_type": "entity_search",
            },
        )
        token_events = [(t, d) for t, d in events if t == "token"]
        assert len(token_events) == 1
        assert token_events[0][1] == "AI is artificial intelligence."

    def test_done_event_contains_query_type(self, stream_client):
        """'done' event data must include 'query_type'."""
        events = self._stream(
            stream_client,
            {"answer": "Some answer.", "sources": [], "query_type": "relationship_query"},
        )
        done_events = [(t, d) for t, d in events if t == "done"]
        assert len(done_events) == 1
        done_data = json.loads(done_events[0][1])
        assert done_data["query_type"] == "relationship_query"

    def test_done_event_contains_execution_time_ms(self, stream_client):
        """'done' event data must include a non-negative numeric 'execution_time_ms'."""
        events = self._stream(
            stream_client,
            {"answer": "ok", "sources": [], "query_type": "entity_search"},
        )
        done_events = [(t, d) for t, d in events if t == "done"]
        assert len(done_events) == 1
        done_data = json.loads(done_events[0][1])
        assert "execution_time_ms" in done_data
        assert isinstance(done_data["execution_time_ms"], int | float)
        assert done_data["execution_time_ms"] >= 0

    def test_sources_defaults_to_empty_list(self, stream_client):
        """'sources' event should be [] when result dict has no 'sources' key."""
        events = self._stream(
            stream_client,
            {"answer": "Some answer.", "query_type": "entity_search"},
        )
        sources_events = [(t, d) for t, d in events if t == "sources"]
        assert len(sources_events) == 1
        assert json.loads(sources_events[0][1]) == []

    def test_token_defaults_to_empty_string(self, stream_client):
        """'token' event data should be '' when result dict has no 'answer' key."""
        events = self._stream(
            stream_client,
            {"sources": [], "query_type": "entity_search"},
        )
        token_events = [(t, d) for t, d in events if t == "token"]
        assert len(token_events) == 1
        assert token_events[0][1] == ""

    def test_done_query_type_defaults_to_unknown(self, stream_client):
        """'done' event query_type should be 'unknown' when result has no 'query_type' key."""
        events = self._stream(
            stream_client,
            {"answer": "Some answer.", "sources": []},
        )
        done_events = [(t, d) for t, d in events if t == "done"]
        assert len(done_events) == 1
        assert json.loads(done_events[0][1])["query_type"] == "unknown"

    def test_exactly_one_of_each_event(self, stream_client):
        """Each event type (sources, token, done) appears exactly once."""
        events = self._stream(
            stream_client,
            {"answer": "ok", "sources": ["X"], "query_type": "entity_search"},
        )
        for event_type in ("sources", "token", "done"):
            count = sum(1 for t, _ in events if t == event_type)
            assert count == 1, f"Expected exactly 1 '{event_type}' event, got {count}"


class TestChatStreamErrorHandling:
    """The generator must emit an 'error' SSE event on failure."""

    def _stream_with_error(self, stream_client, exc):
        """Helper: run a stream request where agent.query() raises exc."""
        mock_conn = MagicMock()
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_conn

        mock_agent = MagicMock()
        mock_agent.query.side_effect = exc

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
        ):
            mock_cls.from_connection.return_value = mock_agent
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?"},
            )
        return _parse_sse(response.text)

    def test_emits_error_event_when_agent_raises(self, stream_client):
        """Should emit a single 'error' event when agent.query() raises."""
        events = self._stream_with_error(stream_client, RuntimeError("DB connection failed"))
        error_events = [(t, d) for t, d in events if t == "error"]
        assert len(error_events) == 1, f"Expected 1 error event, got {len(error_events)}"
        assert error_events[0][1] == "AgentError"
        assert "RuntimeError" not in error_events[0][1]

    def test_no_done_event_after_error(self, stream_client):
        """A 'done' event should NOT be emitted when the generator raises."""
        events = self._stream_with_error(stream_client, ValueError("Something went wrong"))
        done_events = [t for t, _ in events if t == "done"]
        assert done_events == [], "No 'done' event should follow an error"

    def test_does_not_leak_exception_class_name(self, stream_client):
        """Error events must NOT leak internal exception class names."""
        events = self._stream_with_error(stream_client, ConnectionError("Network error"))
        error_events = [(t, d) for t, d in events if t == "error"]
        assert len(error_events) == 1
        assert error_events[0][1] == "AgentError"
        assert "ConnectionError" not in error_events[0][1]

    def test_emits_error_event_on_timeout(self, stream_client):
        """
        R-DOS-1: should emit a single 'error' SSE event with 'TimeoutError' data
        when agent.query() does not complete within STREAM_TIMEOUT_S seconds.
        """
        release = threading.Event()

        def slow_query(**kwargs):
            release.wait(timeout=5)
            return {"answer": "too late", "sources": [], "query_type": "entity_search"}

        mock_conn = MagicMock()
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_conn
        mock_agent = MagicMock()
        mock_agent.query.side_effect = slow_query

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("backend.db.connection._manager", mock_manager),
            patch("wikigr.agent.kg_agent.KnowledgeGraphAgent") as mock_cls,
            patch("backend.api.v1.chat.STREAM_TIMEOUT_S", 0.1),
        ):
            mock_cls.from_connection.return_value = mock_agent
            response = stream_client.get(
                "/api/v1/chat/stream",
                params={"question": "What is AI?"},
            )

        release.set()  # unblock the background thread
        events = _parse_sse(response.text)
        error_events = [(t, d) for t, d in events if t == "error"]
        assert len(error_events) == 1, f"Expected 1 error event, got {error_events}"
        assert "TimeoutError" in error_events[0][1]
        # No 'done' event should follow a timeout
        assert not any(t == "done" for t, _ in events)
