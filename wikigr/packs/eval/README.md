# Knowledge Pack Evaluation Framework

A three-baseline evaluation system for measuring whether knowledge packs surpass training data and web search.

## Overview

This framework enables objective comparison of knowledge packs against two baselines:

1. **Training Baseline**: Claude without any tools (training data only)
2. **Web Search Baseline**: Claude with web search capabilities
3. **Knowledge Pack**: Claude with knowledge pack retrieval

## Key Metrics

- **Accuracy**: Semantic similarity to ground truth (0.0 to 1.0)
- **Hallucination Rate**: Detection of unsupported claims (0.0 to 1.0)
- **Citation Quality**: Validation of citations (0.0 to 1.0)
- **Latency**: Average response time in milliseconds
- **Cost**: Total cost in USD

## Quick Start

### 1. Prepare Questions

Create a JSONL file with evaluation questions:

```json
{"id": "q1", "question": "What is E=mc²?", "ground_truth": "Einstein's mass-energy equivalence", "domain": "physics", "difficulty": "easy"}
{"id": "q2", "question": "Explain quantum entanglement", "ground_truth": "Particles remain connected regardless of distance", "domain": "physics", "difficulty": "hard"}
```

### 2. Run Evaluation

```python
from pathlib import Path
from wikigr.packs.eval import EvalRunner, load_questions_jsonl

# Load questions
questions = load_questions_jsonl(Path("questions.jsonl"))

# Run evaluation
runner = EvalRunner(pack_path=Path("./packs/physics-expert"))
result = runner.run_evaluation(questions)

# Check results
if result.surpasses_training and result.surpasses_web:
    print("✓ Pack meets quality bar!")
else:
    print("✗ Pack needs improvement")

# Save results
runner.save_results(result, Path("./eval_results.json"))
```

### 3. Use the Example Script

```bash
python wikigr/packs/examples/run_physics_evaluation.py \
    ./packs/physics-expert \
    ./questions.jsonl
```

## Architecture

### Data Models (`models.py`)

- `Question`: Evaluation question with ground truth
- `Answer`: Generated answer with metadata
- `EvalMetrics`: Aggregated metrics for one baseline
- `EvalResult`: Complete three-baseline comparison

### Baselines (`baselines.py`)

- `TrainingBaselineEvaluator`: Claude without tools
- `WebSearchBaselineEvaluator`: Claude with web search
- `KnowledgePackEvaluator`: Claude with pack retrieval

### Metrics (`metrics.py`)

- `calculate_accuracy()`: Compare to ground truth
- `calculate_hallucination_rate()`: Detect unsupported claims
- `calculate_citation_quality()`: Validate citations
- `aggregate_metrics()`: Combine all metrics

### Runner (`runner.py`)

- `EvalRunner`: Orchestrates complete evaluation
- Runs all three baselines
- Compares results
- Saves evaluation report

## Metric Details

### Accuracy

Uses semantic similarity:
- **1.0**: Exact match with ground truth
- **0.8**: Contains ground truth
- **0.5**: Partial word overlap
- **0.0**: No overlap

### Hallucination Rate

Detects hedging language without citations:
- Hedging phrases: "I think", "probably", "might be"
- Citation markers: `[1]`, `(Smith 2020)`, "according to"
- Flagged if hedging present without citations

### Citation Quality

Binary classification:
- **1.0**: Has citation markers
- **0.0**: No citation markers

Recognized formats:
- `[1]`, `[2]` (numbered references)
- `(Smith 2020)` (author-year)
- "Source:", "Citation:", "Reference:"
- "According to..."

## Surpassing Criteria

A knowledge pack **surpasses** a baseline if it has:
1. Higher accuracy
2. Lower hallucination rate
3. Higher citation quality

All three conditions must be met.

## Example Output

```json
{
  "pack_name": "physics-expert",
  "timestamp": "2024-01-01T00:00:00Z",
  "training_baseline": {
    "accuracy": 0.70,
    "hallucination_rate": 0.20,
    "citation_quality": 0.50,
    "avg_latency_ms": 300.0,
    "total_cost_usd": 0.05
  },
  "web_search_baseline": {
    "accuracy": 0.80,
    "hallucination_rate": 0.15,
    "citation_quality": 0.70,
    "avg_latency_ms": 400.0,
    "total_cost_usd": 0.08
  },
  "knowledge_pack": {
    "accuracy": 0.90,
    "hallucination_rate": 0.05,
    "citation_quality": 0.95,
    "avg_latency_ms": 250.0,
    "total_cost_usd": 0.03
  },
  "surpasses_training": true,
  "surpasses_web": true,
  "questions_tested": 10
}
```

## Testing

Run the test suite:

```bash
pytest tests/packs/eval/ -v
```

All tests use mocking for the Anthropic API to avoid actual API calls.

## Future Enhancements

### Short-term
- Improve accuracy metric (use sentence embeddings)
- Enhanced hallucination detection (claim verification)
- Citation validation (check sources exist)

### Long-term
- Multi-hop reasoning evaluation
- Factuality benchmarks
- Domain-specific test suites
- Automated question generation from packs

## API Reference

See module docstrings for complete API documentation:

```python
from wikigr.packs import eval
help(eval)
```
