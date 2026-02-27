"""Tests for scripts/generate_eval_questions.py."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Load generate_eval_questions module directly from file path to avoid
# package discovery issues with pytest's importlib mode.
_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "generate_eval_questions.py"
_spec = importlib.util.spec_from_file_location("generate_eval_questions", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["generate_eval_questions"] = _mod
_spec.loader.exec_module(_mod)

from generate_eval_questions import (  # noqa: E402  # isort:skip
    DOMAIN_DESCRIPTIONS,
    build_generation_prompt,
    generate_eval_questions,
    get_domain_name,
    parse_questions_from_response,
    sample_db_context,
)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


def test_get_domain_name():
    assert get_domain_name("azure-lighthouse") == "azure_lighthouse"
    assert get_domain_name("security-copilot") == "security_copilot"
    assert get_domain_name("sentinel-graph") == "sentinel_graph"
    assert get_domain_name("physics-expert") == "physics_expert"


def test_domain_descriptions_exist_for_known_packs():
    """Known packs must have domain descriptions."""
    for pack in ["azure-lighthouse", "security-copilot", "sentinel-graph", "fabric-graphql-expert"]:
        assert pack in DOMAIN_DESCRIPTIONS
        assert len(DOMAIN_DESCRIPTIONS[pack]) > 50


def test_build_generation_prompt_contains_difficulty():
    prompt = build_generation_prompt(
        pack_name="azure-lighthouse",
        domain_description="Azure cross-tenant management",
        db_context="",
        difficulty="medium",
        count=10,
        id_prefix="al",
        id_start=1,
    )
    assert "medium" in prompt
    assert "10" in prompt
    assert "azure-lighthouse" in prompt
    assert "azure_lighthouse" in prompt  # domain name
    assert "al_001" in prompt  # ID prefix


def test_build_generation_prompt_includes_db_context():
    prompt = build_generation_prompt(
        pack_name="physics-expert",
        domain_description="Physics knowledge",
        db_context="Pack contains 10 articles including:\n- Newton's laws",
        difficulty="easy",
        count=5,
        id_prefix="pe",
        id_start=1,
    )
    assert "Newton's laws" in prompt
    assert "PACK DATABASE CONTEXT" in prompt


def test_build_generation_prompt_no_db_context():
    prompt = build_generation_prompt(
        pack_name="physics-expert",
        domain_description="Physics knowledge",
        db_context="",
        difficulty="easy",
        count=5,
        id_prefix="pe",
        id_start=1,
    )
    assert "PACK DATABASE CONTEXT" not in prompt


def test_parse_questions_from_response_valid():
    questions_data = [
        {
            "id": "al_001",
            "domain": "azure_lighthouse",
            "difficulty": "easy",
            "question": "What is Azure Lighthouse?",
            "ground_truth": "A cross-tenant management service.",
            "source": "overview",
        },
        {
            "id": "al_002",
            "domain": "azure_lighthouse",
            "difficulty": "medium",
            "question": "How do you delegate resources in Azure Lighthouse?",
            "ground_truth": "Using Azure Resource Manager templates.",
            "source": "delegation",
        },
    ]
    response_text = json.dumps(questions_data)
    result = parse_questions_from_response(response_text, 2, "azure-lighthouse")
    assert len(result) == 2
    assert result[0]["id"] == "al_001"
    assert result[0]["domain"] == "azure_lighthouse"


def test_parse_questions_from_response_with_surrounding_text():
    """JSON array embedded in surrounding text should still parse."""
    questions_data = [
        {
            "id": "sc_001",
            "domain": "security_copilot",
            "difficulty": "easy",
            "question": "What is Security Copilot?",
            "ground_truth": "An AI security tool.",
            "source": "overview",
        }
    ]
    response_text = f"Here are the questions:\n{json.dumps(questions_data)}\n\nDone."
    result = parse_questions_from_response(response_text, 1, "security-copilot")
    assert len(result) == 1
    assert result[0]["domain"] == "security_copilot"


def test_parse_questions_from_response_missing_field_skipped():
    """Questions missing required fields should be skipped."""
    questions_data = [
        {
            "id": "al_001",
            "difficulty": "easy",
            # Missing: domain, question, ground_truth, source
        },
        {
            "id": "al_002",
            "domain": "azure_lighthouse",
            "difficulty": "easy",
            "question": "What is Azure Lighthouse?",
            "ground_truth": "Cross-tenant management.",
            "source": "overview",
        },
    ]
    result = parse_questions_from_response(json.dumps(questions_data), 2, "azure-lighthouse")
    assert len(result) == 1
    assert result[0]["id"] == "al_002"


def test_parse_questions_from_response_invalid_difficulty_fixed():
    """Invalid difficulty should be fixed to 'medium'."""
    questions_data = [
        {
            "id": "al_001",
            "domain": "azure_lighthouse",
            "difficulty": "super-hard",
            "question": "Test question?",
            "ground_truth": "Answer.",
            "source": "test",
        }
    ]
    result = parse_questions_from_response(json.dumps(questions_data), 1, "azure-lighthouse")
    assert len(result) == 1
    assert result[0]["difficulty"] == "medium"


def test_parse_questions_from_response_no_json_array():
    with pytest.raises(ValueError, match="No JSON array found"):
        parse_questions_from_response("This is not JSON", 5, "test-pack")


def test_parse_questions_normalizes_domain():
    """Domain field should always be set to pack's domain name."""
    questions_data = [
        {
            "id": "sg_001",
            "domain": "wrong_domain",
            "difficulty": "easy",
            "question": "What is Sentinel?",
            "ground_truth": "A SIEM solution.",
            "source": "overview",
        }
    ]
    result = parse_questions_from_response(json.dumps(questions_data), 1, "sentinel-graph")
    assert result[0]["domain"] == "sentinel_graph"


# ---------------------------------------------------------------------------
# Tests for sample_db_context
# ---------------------------------------------------------------------------


def test_sample_db_context_nonexistent_path(tmp_path: Path):
    """Should return empty string for nonexistent DB path."""
    result = sample_db_context(tmp_path / "nonexistent.db")
    assert result == ""


def test_sample_db_context_kuzu_error(tmp_path: Path):
    """Should gracefully return empty string on kuzu errors."""
    # Create a fake .db path (not a real kuzu DB)
    fake_db = tmp_path / "fake.db"
    fake_db.mkdir()
    result = sample_db_context(fake_db)
    assert result == ""


# ---------------------------------------------------------------------------
# Integration-style tests (mocked Claude API)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_claude_questions_response() -> Mock:
    """Mock Anthropic API response with valid question JSON."""
    questions = [
        {
            "id": "al_001",
            "domain": "azure_lighthouse",
            "difficulty": "easy",
            "question": "What is Azure Lighthouse used for?",
            "ground_truth": "Cross-tenant resource management.",
            "source": "overview",
        },
        {
            "id": "al_002",
            "domain": "azure_lighthouse",
            "difficulty": "easy",
            "question": "What is delegated resource management?",
            "ground_truth": "A feature allowing service providers to manage customer resources.",
            "source": "delegation",
        },
    ]
    response = Mock()
    response.content = [Mock(text=json.dumps(questions))]
    return response


@patch("generate_eval_questions.anthropic.Anthropic")
def test_generate_eval_questions_creates_files(
    mock_anthropic_class: Mock,
    mock_claude_questions_response: Mock,
    tmp_path: Path,
):
    """End-to-end test that files are created with correct format."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_claude_questions_response
    mock_anthropic_class.return_value = mock_client

    output_dir = tmp_path / "eval"
    questions = generate_eval_questions(
        pack_name="azure-lighthouse",
        db_path=None,
        output_dir=output_dir,
        total_count=4,  # Small count for speed
    )

    assert (output_dir / "questions.json").exists()
    assert (output_dir / "questions.jsonl").exists()
    assert len(questions) > 0

    # Verify JSON array format
    with open(output_dir / "questions.json") as f:
        loaded = json.load(f)
    assert isinstance(loaded, list)
    assert all(isinstance(q, dict) for q in loaded)

    # Verify JSONL format
    with open(output_dir / "questions.jsonl") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) == len(loaded)
    for line in lines:
        q = json.loads(line)
        assert "id" in q
        assert "question" in q
        assert "ground_truth" in q


@patch("generate_eval_questions.anthropic.Anthropic")
def test_generate_eval_questions_ids_sequential(
    mock_anthropic_class: Mock,
    mock_claude_questions_response: Mock,
    tmp_path: Path,
):
    """IDs should be sequential across all difficulty levels."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_claude_questions_response
    mock_anthropic_class.return_value = mock_client

    questions = generate_eval_questions(
        pack_name="azure-lighthouse",
        db_path=None,
        output_dir=tmp_path / "eval",
        total_count=4,
    )

    ids = [q["id"] for q in questions]
    # All IDs should start with the same prefix
    prefixes = {id_.rsplit("_", 1)[0] for id_ in ids}
    assert len(prefixes) == 1


@patch("generate_eval_questions.anthropic.Anthropic")
def test_generate_eval_questions_deduplication(
    mock_anthropic_class: Mock,
    tmp_path: Path,
):
    """Duplicate questions should be removed."""
    duplicate_questions = [
        {
            "id": "al_001",
            "domain": "azure_lighthouse",
            "difficulty": "easy",
            "question": "What is Azure Lighthouse?",  # Exact duplicate
            "ground_truth": "Cross-tenant management.",
            "source": "overview",
        },
        {
            "id": "al_002",
            "domain": "azure_lighthouse",
            "difficulty": "easy",
            "question": "What is Azure Lighthouse?",  # Exact duplicate
            "ground_truth": "Another answer.",
            "source": "overview2",
        },
    ]
    response = Mock()
    response.content = [Mock(text=json.dumps(duplicate_questions))]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = response
    mock_anthropic_class.return_value = mock_client

    questions = generate_eval_questions(
        pack_name="azure-lighthouse",
        db_path=None,
        output_dir=tmp_path / "eval",
        total_count=4,
    )

    # Duplicates should be removed
    question_texts = [q["question"] for q in questions]
    assert len(question_texts) == len(set(question_texts))


@patch("generate_eval_questions.anthropic.Anthropic")
def test_generate_eval_questions_output_dir_created(
    mock_anthropic_class: Mock,
    mock_claude_questions_response: Mock,
    tmp_path: Path,
):
    """Output directory should be created automatically."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_claude_questions_response
    mock_anthropic_class.return_value = mock_client

    output_dir = tmp_path / "deep" / "nested" / "eval"
    assert not output_dir.exists()

    generate_eval_questions(
        pack_name="azure-lighthouse",
        db_path=None,
        output_dir=output_dir,
        total_count=4,
    )

    assert output_dir.exists()
    assert (output_dir / "questions.json").exists()
