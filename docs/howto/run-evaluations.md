# Run Evaluations

How to evaluate Knowledge Pack quality using `eval_single_pack.py` and `run_all_packs_evaluation.py`.

## Prerequisites

- `ANTHROPIC_API_KEY` environment variable set
- Pack built with `pack.db` and `eval/questions.jsonl` present
- Python dependencies installed (`uv sync`)

## Single Pack Evaluation

### Basic Usage

```bash
uv run python scripts/eval_single_pack.py <pack-name> [--sample N]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `pack-name` | Yes | Name of the pack directory under `data/packs/` |
| `--sample N` | No | Number of questions to sample (default: all) |

### Examples

```bash
# Evaluate 5 questions (quick check, ~$0.03)
uv run python scripts/eval_single_pack.py go-expert --sample 5

# Evaluate 25 questions (good confidence, ~$0.75)
uv run python scripts/eval_single_pack.py go-expert --sample 25

# Evaluate all questions
uv run python scripts/eval_single_pack.py go-expert
```

### What It Does

For each question in `data/packs/<pack-name>/eval/questions.jsonl`:

1. **Training condition**: Claude Opus answers without any pack context
2. **Pack condition**: KG Agent retrieves from the pack with the full retrieval pipeline, then Claude Opus synthesizes
3. **Judge scoring**: Claude Haiku scores each answer 0-10 against the `ground_truth`

### Output

```
Pack: go-expert  (10 questions)

Condition     Avg Score  Accuracy
──────────    ─────────  ────────
Training      8.7/10     90.0%
Pack          9.6/10     100.0%
Delta                    +10.0pp
```

### Models Used

| Role | Model | Purpose |
|------|-------|---------|
| Answer model | `claude-opus-4-6` | Generates answers for both conditions |
| Judge model | `claude-haiku-4-5-20251001` | Scores answers against ground truth |

## All-Packs Evaluation

### Basic Usage

```bash
uv run python scripts/run_all_packs_evaluation.py [--sample N] [flags]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--sample N` | No | Questions per pack (default: all) |
| `--disable-reranker` | No | Disable GraphReranker for A/B testing |
| `--disable-multidoc` | No | Disable MultiDocSynthesizer |
| `--disable-fewshot` | No | Disable FewShotManager |

### Examples

```bash
# Quick sample across all packs (~$0.15)
uv run python scripts/run_all_packs_evaluation.py --sample 5

# Standard evaluation (10 per pack, ~$0.30)
uv run python scripts/run_all_packs_evaluation.py --sample 10

# Full evaluation (all questions, ~$15)
uv run python scripts/run_all_packs_evaluation.py

# A/B test: evaluate without reranker
uv run python scripts/run_all_packs_evaluation.py --sample 10 --disable-reranker
```

### Which Packs Are Included?

The script automatically discovers packs that have both:

- `data/packs/<pack-name>/pack.db` (Kuzu database)
- `data/packs/<pack-name>/eval/questions.jsonl` (evaluation questions)

Packs missing either file are skipped.

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

### Console Output

```
=== All Packs Evaluation ===
Packs found: 8
Sample per pack: 10

[1/8] bicep-infrastructure ...
  Training:  avg=9.1  acc=100%
  Pack:      avg=9.4  acc=100%

[2/8] go-expert ...
  Training:  avg=8.7  acc=90%
  Pack:      avg=9.6  acc=100%

...

=== Grand Summary ===
Training:  avg=8.9  acc=96.2%  (n=80)
Pack:      avg=9.1  acc=97.5%  (n=80)

Results saved to data/packs/all_packs_evaluation.json
```

## Cost Estimates

Evaluation cost depends on the number of questions and conditions:

| Questions | Packs | Total API Calls | Estimated Cost |
|-----------|-------|----------------|---------------|
| 5 per pack | 8 | ~120 | ~$0.15 |
| 10 per pack | 8 | ~240 | ~$0.30 |
| 25 per pack | 8 | ~600 | ~$0.75 |
| 50 per pack | 8 | ~1200 | ~$1.50 |
| All (~200 total) | 8 | ~4800 | ~$6.00 |

Each question requires 2 answer calls (Training + Pack) and 2 judge calls, using a mix of Opus (answers) and Haiku (judging).

## A/B Testing Enhancement Modules

Disable individual enhancement modules to measure their contribution:

```bash
# Baseline: all enhancements on
uv run python scripts/run_all_packs_evaluation.py --sample 10

# Test: no graph reranking
uv run python scripts/run_all_packs_evaluation.py --sample 10 --disable-reranker

# Test: no multi-doc synthesis
uv run python scripts/run_all_packs_evaluation.py --sample 10 --disable-multidoc

# Test: no few-shot examples
uv run python scripts/run_all_packs_evaluation.py --sample 10 --disable-fewshot
```

Compare the output JSON files to see which modules contribute the most to each pack's accuracy.

## Troubleshooting

### "No questions found for pack"

Ensure `eval/questions.jsonl` exists in the pack directory:

```bash
ls data/packs/<pack-name>/eval/questions.jsonl
```

If missing, generate questions:

```bash
python scripts/generate_eval_questions.py --pack <pack-name> --count 50
```

### "ANTHROPIC_API_KEY not set"

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### High Variance Between Runs

Small sample sizes produce unreliable results. Increase the sample:

```bash
# Use 25+ questions for stable results
uv run python scripts/eval_single_pack.py go-expert --sample 25
```

### Negative Delta on a Pack

See [Improving Accuracy](../evaluation/improving-accuracy.md) for diagnosis and remediation steps. Common causes:

- Pack content is outdated or incorrect
- Evaluation questions test training knowledge, not pack-specific knowledge
- Source URLs have thin content

## See Also

- [Evaluation Methodology](../evaluation/methodology.md) -- Understanding what we measure and how
- [Evaluation Results](../evaluation/results.md) -- Current results across all packs
- [Improving Accuracy](../evaluation/improving-accuracy.md) -- Strategies for improving pack quality
