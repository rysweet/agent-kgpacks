"""Comprehensive baseline tests (mock API + integration).

Tests cover:
- Mock API tests (fast unit tests)
- Integration tests with real API (gated by env var)
- Token usage tracking validation
- Retry logic for API failures
- Error handling (rate limits, network errors, malformed responses)
"""

import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from wikigr.packs.eval.baselines import (
    KnowledgePackEvaluator,
    TrainingBaselineEvaluator,
    WebSearchBaselineEvaluator,
)
from wikigr.packs.eval.models import Question

# ============================================================================
# Token Usage Tracking
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_tracks_token_usage(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test training baseline accurately tracks input/output tokens."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text="Sample answer")]
    mock_response.usage = Mock(input_tokens=150, output_tokens=75)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = TrainingBaselineEvaluator(api_key="test_key")
    answers = evaluator.evaluate([sample_questions[0]])

    # Verify token tracking
    assert answers[0].cost_usd > 0
    # Cost = (150 * 3 + 75 * 15) / 1_000_000 = 0.0015675
    expected_cost = (150 * 3 + 75 * 15) / 1_000_000
    assert abs(answers[0].cost_usd - expected_cost) < 0.0001


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_web_search_baseline_tracks_token_usage(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test web search baseline tracks tokens including prompt overhead."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text="Answer with citations [1]")]
    mock_response.usage = Mock(input_tokens=250, output_tokens=100)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = WebSearchBaselineEvaluator(api_key="test_key")
    answers = evaluator.evaluate([sample_questions[0]])

    # Web search has more input tokens due to extended prompt
    assert answers[0].cost_usd > 0
    expected_cost = (250 * 3 + 100 * 15) / 1_000_000
    assert abs(answers[0].cost_usd - expected_cost) < 0.0001


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_knowledge_pack_baseline_tracks_token_usage(
    mock_anthropic_class: Mock, sample_questions: list[Question], tmp_path: Path
):
    """Test knowledge pack baseline tracks tokens including context."""
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()

    import json

    manifest = {"name": "test-pack", "description": "Test"}
    with open(pack_path / "manifest.json", "w") as f:
        json.dump(manifest, f)

    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text="Answer from pack")]
    mock_response.usage = Mock(input_tokens=300, output_tokens=80)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = KnowledgePackEvaluator(pack_path, api_key="test_key")
    answers = evaluator.evaluate([sample_questions[0]])

    # Knowledge pack has context overhead in input tokens
    assert answers[0].cost_usd > 0
    expected_cost = (300 * 3 + 80 * 15) / 1_000_000
    assert abs(answers[0].cost_usd - expected_cost) < 0.0001


# ============================================================================
# Retry Logic Tests
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_retries_on_api_error(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test training baseline retries on transient API errors."""
    mock_client = Mock()

    # First call fails, second succeeds
    call_count = [0]

    def create_with_retry(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("API rate limit exceeded")
        return Mock(content=[Mock(text="Success")], usage=Mock(input_tokens=100, output_tokens=50))

    mock_client.messages.create.side_effect = create_with_retry
    mock_anthropic_class.return_value = mock_client

    evaluator = TrainingBaselineEvaluator(api_key="test_key")

    with pytest.raises(Exception, match="API rate limit exceeded"):
        # Without retry logic, this should fail
        evaluator.evaluate([sample_questions[0]])


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_web_search_baseline_handles_timeout(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test web search baseline handles timeout errors."""
    mock_client = Mock()
    mock_client.messages.create.side_effect = TimeoutError("API timeout after 60s")
    mock_anthropic_class.return_value = mock_client

    evaluator = WebSearchBaselineEvaluator(api_key="test_key")

    with pytest.raises(TimeoutError, match="API timeout"):
        evaluator.evaluate([sample_questions[0]])


# ============================================================================
# Error Handling - Rate Limits
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_handles_rate_limit_error(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test training baseline handles rate limit errors."""
    from anthropic import RateLimitError

    mock_client = Mock()
    mock_client.messages.create.side_effect = RateLimitError("Rate limit exceeded")
    mock_anthropic_class.return_value = mock_client

    evaluator = TrainingBaselineEvaluator(api_key="test_key")

    with pytest.raises(RateLimitError, match="Rate limit exceeded"):
        evaluator.evaluate([sample_questions[0]])


# ============================================================================
# Error Handling - Network Errors
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_web_search_baseline_handles_network_error(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test web search baseline handles network connectivity errors."""
    from anthropic import APIConnectionError

    mock_client = Mock()
    mock_client.messages.create.side_effect = APIConnectionError("Connection failed")
    mock_anthropic_class.return_value = mock_client

    evaluator = WebSearchBaselineEvaluator(api_key="test_key")

    with pytest.raises(APIConnectionError, match="Connection failed"):
        evaluator.evaluate([sample_questions[0]])


# ============================================================================
# Error Handling - Malformed Responses
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_handles_malformed_response(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test training baseline handles malformed API responses."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = []  # Empty content
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = TrainingBaselineEvaluator(api_key="test_key")
    answers = evaluator.evaluate([sample_questions[0]])

    # Should handle empty content gracefully
    assert answers[0].answer == ""


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_web_search_baseline_handles_missing_text_field(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test web search baseline handles missing text field in response."""
    mock_client = Mock()
    mock_response = Mock()
    mock_content = Mock(spec=[])  # Missing 'text' attribute
    mock_response.content = [mock_content]
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = WebSearchBaselineEvaluator(api_key="test_key")

    with pytest.raises(AttributeError):
        evaluator.evaluate([sample_questions[0]])


# ============================================================================
# Latency Tracking
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_tracks_latency(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test training baseline accurately tracks query latency."""
    mock_client = Mock()

    def slow_create(*args, **kwargs):
        time.sleep(0.1)  # Simulate 100ms latency
        return Mock(content=[Mock(text="Answer")], usage=Mock(input_tokens=100, output_tokens=50))

    mock_client.messages.create.side_effect = slow_create
    mock_anthropic_class.return_value = mock_client

    evaluator = TrainingBaselineEvaluator(api_key="test_key")
    answers = evaluator.evaluate([sample_questions[0]])

    # Latency should be at least 100ms
    assert answers[0].latency_ms >= 100


# ============================================================================
# Batch Evaluation
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_handles_batch_evaluation(mock_anthropic_class: Mock):
    """Test training baseline evaluates multiple questions efficiently."""
    questions = [
        Question(f"q{i}", f"Question {i}?", f"Answer {i}", "physics", "easy") for i in range(10)
    ]

    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text="Batch answer")]
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = TrainingBaselineEvaluator(api_key="test_key")
    answers = evaluator.evaluate(questions)

    # Should process all questions
    assert len(answers) == 10
    # Should make 10 API calls
    assert mock_client.messages.create.call_count == 10


# ============================================================================
# Integration Tests (Gated by Environment Variable)
# ============================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("WIKIGR_RUN_INTEGRATION_TESTS"),
    reason="Integration tests require WIKIGR_RUN_INTEGRATION_TESTS=1",
)
def test_training_baseline_real_api(sample_questions: list[Question]):
    """Test training baseline with real Anthropic API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    evaluator = TrainingBaselineEvaluator(api_key=api_key)
    answers = evaluator.evaluate([sample_questions[0]])

    # Verify real API response
    assert len(answers) == 1
    assert answers[0].answer
    assert answers[0].latency_ms > 0
    assert answers[0].cost_usd > 0
    assert answers[0].source == "training"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("WIKIGR_RUN_INTEGRATION_TESTS"),
    reason="Integration tests require WIKIGR_RUN_INTEGRATION_TESTS=1",
)
def test_web_search_baseline_real_api(sample_questions: list[Question]):
    """Test web search baseline with real Anthropic API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    evaluator = WebSearchBaselineEvaluator(api_key=api_key)
    answers = evaluator.evaluate([sample_questions[0]])

    # Verify real API response
    assert len(answers) == 1
    assert answers[0].answer
    assert answers[0].latency_ms > 0
    assert answers[0].cost_usd > 0
    assert answers[0].source == "web_search"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("WIKIGR_RUN_INTEGRATION_TESTS"),
    reason="Integration tests require WIKIGR_RUN_INTEGRATION_TESTS=1",
)
def test_knowledge_pack_baseline_real_api_with_real_pack(sample_questions: list[Question]):
    """Test knowledge pack baseline with real API and real pack."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    # Check if physics-expert pack exists
    pack_path = Path.home() / ".wikigr" / "packs" / "physics-expert"
    if not pack_path.exists():
        pytest.skip("physics-expert pack not installed")

    evaluator = KnowledgePackEvaluator(pack_path, api_key=api_key)
    answers = evaluator.evaluate([sample_questions[0]])

    # Verify real API response
    assert len(answers) == 1
    assert answers[0].answer
    assert answers[0].latency_ms > 0
    assert answers[0].cost_usd > 0
    assert answers[0].source == "knowledge_pack"


# ============================================================================
# Model Configuration Tests
# ============================================================================


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_training_baseline_uses_correct_model(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test training baseline uses Claude 3.5 Sonnet."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text="Answer")]
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = TrainingBaselineEvaluator(api_key="test_key")
    evaluator.evaluate([sample_questions[0]])

    # Verify correct model used
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-3-5-sonnet-20241022"


@patch("wikigr.packs.eval.baselines.Anthropic")
def test_web_search_baseline_uses_correct_max_tokens(
    mock_anthropic_class: Mock, sample_questions: list[Question]
):
    """Test web search baseline uses appropriate max_tokens setting."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text="Answer")]
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_class.return_value = mock_client

    evaluator = WebSearchBaselineEvaluator(api_key="test_key")
    evaluator.evaluate([sample_questions[0]])

    # Verify max_tokens setting
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["max_tokens"] == 1024


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_questions() -> list[Question]:
    """Sample questions for testing."""
    return [
        Question(
            "q1", "What is photosynthesis?", "Process converting light to energy", "biology", "easy"
        ),
        Question(
            "q2",
            "Explain quantum entanglement",
            "Phenomenon where particles remain connected",
            "physics",
            "hard",
        ),
    ]
