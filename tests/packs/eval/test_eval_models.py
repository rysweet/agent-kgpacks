"""Tests for evaluation data models."""

from wikigr.packs.eval.models import Answer, EvalMetrics, EvalResult, Question


def test_question_creation():
    """Test Question dataclass creation."""
    q = Question(
        id="q1",
        question="What is photosynthesis?",
        ground_truth="Photosynthesis is the process plants use to convert light into energy.",
        domain="biology",
        difficulty="easy",
    )

    assert q.id == "q1"
    assert q.question == "What is photosynthesis?"
    assert q.domain == "biology"
    assert q.difficulty == "easy"


def test_answer_creation():
    """Test Answer dataclass creation."""
    a = Answer(
        question_id="q1",
        answer="Photosynthesis converts light to energy.",
        source="training",
        latency_ms=250.5,
        cost_usd=0.001,
    )

    assert a.question_id == "q1"
    assert a.source == "training"
    assert a.latency_ms == 250.5
    assert a.cost_usd == 0.001


def test_eval_metrics_creation():
    """Test EvalMetrics dataclass creation."""
    m = EvalMetrics(
        accuracy=0.85,
        hallucination_rate=0.1,
        citation_quality=0.9,
        avg_latency_ms=300.0,
        total_cost_usd=0.05,
    )

    assert m.accuracy == 0.85
    assert m.hallucination_rate == 0.1
    assert m.citation_quality == 0.9


def test_eval_result_creation():
    """Test EvalResult dataclass creation."""
    training = EvalMetrics(0.7, 0.2, 0.5, 300.0, 0.05)
    web = EvalMetrics(0.8, 0.15, 0.7, 400.0, 0.08)
    pack = EvalMetrics(0.9, 0.05, 0.95, 250.0, 0.03)

    result = EvalResult(
        pack_name="physics-expert",
        timestamp="2024-01-01T00:00:00Z",
        training_baseline=training,
        web_search_baseline=web,
        knowledge_pack=pack,
        surpasses_training=True,
        surpasses_web=True,
        questions_tested=10,
    )

    assert result.pack_name == "physics-expert"
    assert result.surpasses_training is True
    assert result.surpasses_web is True
    assert result.questions_tested == 10
