# Evaluation Methodology

This page explains how Knowledge Packs are evaluated: what we measure, how we measure it, and how to interpret the results.

## What We Measure

The evaluation framework answers one question: **Does the pack improve answer quality compared to Claude answering from training alone?**

We measure three metrics:

| Metric | Definition | Calculation |
|--------|-----------|-------------|
| **Accuracy** | Percentage of answers scored >= 7 out of 10 | `count(score >= 7) / total_questions * 100` |
| **Average Score** | Mean judge score across all questions | `sum(scores) / total_questions` |
| **Delta** | Accuracy difference between Pack and Training | `pack_accuracy - training_accuracy` |

A score of 7+ indicates the answer is substantially correct and useful. Scores below 7 indicate significant errors, omissions, or hallucinations.

## The Two Conditions

Every pack is evaluated under two conditions, using the same set of questions:

### 1. Training Baseline

Claude Opus answers the question with **no pack context** -- purely from its training data. This establishes what the model already knows about the domain.

```
Prompt:
  Answer the following question:
  Q: {question}
```

### 2. Pack (KG Agent)

The KG Agent retrieves content from the pack database with the full retrieval pipeline enabled: confidence gating, graph reranking, multi-document synthesis, content quality scoring, and few-shot examples. This tests whether the pack adds value beyond training.

```
Pipeline:
  question → vector search → confidence gate →
  graph rerank → multi-doc expand →
  quality filter → few-shot inject → synthesis
```

## The Judge Model

Answers are scored by a **judge model** (Claude Opus `claude-opus-4-6`) on a 0-10 scale.

### Scoring Prompt

```
Score 0-10.
Q: {question}
Expected: {ground_truth}
Actual: {answer}
Number only.
```

The judge compares the generated answer against the `ground_truth` from the evaluation question set and returns a single integer.

### Judge Model Configuration

Both evaluation scripts use Claude Opus (`claude-opus-4-6`) as the judge model. Opus provides more accurate, nuanced scoring than smaller models — it evaluates semantic correctness rather than surface-level keyword matching.

| Consideration | Decision |
|--------------|----------|
| Accuracy | Opus provides the most accurate relevance judgments |
| Consistency | Produces stable, reproducible scores at temperature 0 |
| Fewer false negatives | Evaluates semantic correctness, not just keyword overlap |
| Simplicity | Single-number output avoids parsing complexity |

### Scoring Rubric

The judge model assigns scores based on correctness relative to the ground truth:

| Score Range | Meaning |
|-------------|---------|
| **9-10** | Fully correct, comprehensive, may exceed ground truth |
| **7-8** | Substantially correct with minor gaps or imprecisions |
| **5-6** | Partially correct -- some key facts present, others missing |
| **3-4** | Mostly incorrect with some relevant information |
| **1-2** | Severely wrong, major hallucinations or misunderstandings |
| **0** | Completely irrelevant or no answer |

The accuracy threshold of 7 captures answers that are "good enough to be useful" while excluding answers with significant errors.

### Answer Model

The model that generates answers for evaluation is Claude Opus (`claude-opus-4-6`). This is the same model used in production, ensuring evaluation results reflect real-world performance.

## Question Format

Evaluation questions are stored in `eval/questions.jsonl` (one JSON object per line):

```json
{"id": "ge_001", "domain": "go_expert", "difficulty": "easy", "question": "What does slices.Contains do?", "ground_truth": "slices.Contains reports whether v is present in s. E must satisfy the comparable constraint.", "source": "slices_stdlib"}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier with pack prefix (e.g., `ge_001`, `re_015`) |
| `domain` | string | Snake-case domain name (e.g., `go_expert`) |
| `difficulty` | string | One of `easy`, `medium`, `hard` |
| `question` | string | The question text posed to both conditions |
| `ground_truth` | string | Expected correct answer used by the judge for scoring |
| `source` | string | Topic slug identifying the content area |

### Difficulty Distribution

For a standard 50-question pack:

| Difficulty | Count | Purpose |
|------------|-------|---------|
| `easy` | 20 | Basic concepts the pack should definitely cover |
| `medium` | 20 | Moderate complexity requiring some depth |
| `hard` | 10 | Advanced topics, edge cases, implementation details |

### Question Design Principles

**Good questions test pack-specific knowledge:**

- Use exact API names, types, and terminology from the documentation
- Target recent features or version-specific behavior
- Require depth that goes beyond general awareness

**Bad questions test general knowledge:**

- "What is a goroutine?" (Claude already knows this perfectly)
- Generic terminology instead of specific API names
- Topics covered extensively in training data

!!! warning "Training data overlap"
    If training baseline accuracy is already 100% on a question set, the questions are testing knowledge Claude already has. The pack cannot demonstrate value. Replace generic questions with pack-specific ones targeting current documentation content.

## Statistical Considerations

### Sample Size

The number of questions affects result reliability:

| Questions | Confidence | Typical Variance | Cost (all packs) |
|-----------|------------|------------------|-------------------|
| 5 | Low | +/- 2 points | ~$0.15 |
| 10 | Moderate | +/- 1.5 points | ~$0.30 |
| 25 | Good | +/- 1 point | ~$0.75 |
| 50 | High | +/- 0.5 points | ~$1.50 |

For production evaluation, use at least 25 questions per pack. For quick iteration, 5-10 questions provide directional signal.

### Score Distributions

Individual question scores are integers from 0-10. Because both the answer model and judge model are deterministic at temperature 0, scores are reproducible across runs.

However, scores can vary if:

- The answer model is updated (different Claude version)
- The pack database is rebuilt (different content)
- Questions are modified

### Interpreting Delta

The delta (Pack accuracy - Training accuracy) is the key metric:

| Delta | Interpretation | Action |
|-------|---------------|--------|
| **+5pp or more** | Strong pack value | Pack clearly helps; deploy |
| **+1pp to +5pp** | Moderate value | Pack helps on some questions; look for improvement areas |
| **0pp** | Neutral | Pack matches training; may still provide provenance value |
| **-1pp to -5pp** | Slight regression | Investigate retrieval quality and question calibration |
| **Below -5pp** | Significant regression | Content quality issues; review URLs and rebuild |

!!! tip "Positive delta is not always required"
    A pack can provide value even with a zero delta if:

    - It provides source attribution (provenance) that training cannot
    - It handles questions about very recent content not yet in training
    - It works offline without internet access

## Running Evaluations

### Single Pack

```bash
# Quick check (5 questions, ~$0.03)
uv run python scripts/eval_single_pack.py go-expert --sample 5

# Full evaluation (all questions)
uv run python scripts/eval_single_pack.py go-expert
```

### All Packs

```bash
# Sample across all packs (10 questions each, ~$0.30)
uv run python scripts/run_all_packs_evaluation.py --sample 10

# Full evaluation
uv run python scripts/run_all_packs_evaluation.py
```

### Output

Results are saved to `data/packs/all_packs_evaluation.json`:

```json
{
  "timestamp": "2026-03-01T17:56:44Z",
  "packs_evaluated": 8,
  "sample_per_pack": 10,
  "grand_summary": {
    "training": {"avg": 8.875, "accuracy": 96.25, "n": 80},
    "pack": {"avg": 9.05, "accuracy": 97.5, "n": 80}
  },
  "per_pack": {
    "go-expert": {
      "scores": {
        "training": [5, 9, 10, 10, 9, 10, 7, 9, 9, 9],
        "pack": [9, 10, 10, 9, 9, 10, 9, 10, 10, 10]
      }
    }
  }
}
```

## Evaluation Architecture

```
questions.jsonl
  │
  ├──► Training condition
  │    Claude Opus answers without context
  │    │
  │    ▼
  │    Judge (configurable) scores 0-10 vs ground_truth
  │
  └──► Pack condition
       KG Agent retrieves + synthesizes (full pipeline)
       │
       ▼
       Judge (configurable) scores 0-10 vs ground_truth

Results:
  per-question scores
  per-condition averages and accuracy
  delta (pack - training)
```
