# Generating Evaluation Questions for Knowledge Packs

How to generate evaluation Q&A pairs for knowledge packs and run evaluations across all packs.

> **Note**: `generate_eval_questions.py` and `build_fabric_pack.py` are added in [PR #167](https://github.com/rysweet/wikigr/pull/167). The `--disable-reranker/multidoc/fewshot` flags are added in [PR #168](https://github.com/rysweet/wikigr/pull/168).

## Overview

Each pack needs evaluation questions to measure accuracy. The `generate_eval_questions.py` script uses Claude Haiku to generate 50 diverse Q&A pairs per pack, sampling article content from the pack database.

## Quick Start

### Generate Questions for a Pack

```bash
# Generate 50 questions for azure-lighthouse
python scripts/generate_eval_questions.py \
    --pack azure-lighthouse \
    --count 50

# Output: data/packs/azure-lighthouse/eval/questions.json
#         data/packs/azure-lighthouse/eval/questions.jsonl
```

### Generate for All Pre-existing Packs

```bash
python scripts/generate_eval_questions.py --pack azure-lighthouse
python scripts/generate_eval_questions.py --pack security-copilot
python scripts/generate_eval_questions.py --pack sentinel-graph
```

### Custom Options

```bash
python scripts/generate_eval_questions.py \
    --pack physics-expert \
    --db data/packs/physics-expert/pack.db \  # auto-detected by default
    --count 100 \                              # more questions = better stats
    --output data/packs/physics-expert/eval/questions_extended.json
```

## Running All-Packs Evaluation

The `run_all_packs_evaluation.py` script runs evaluation across every pack that has both `pack.db` and `eval/questions.jsonl`:

```bash
# Quick sample (5 questions per pack, ~$0.15)
python scripts/run_all_packs_evaluation.py --sample 5

# Full evaluation (all questions, ~$15 for 477 questions)
python scripts/run_all_packs_evaluation.py

# With enhancement comparison
python scripts/run_all_packs_evaluation.py --sample 10

# A/B test without reranker
python scripts/run_all_packs_evaluation.py --sample 10 --disable-reranker
```

Output is saved to `data/packs/all_packs_evaluation.json`.

## Question Format

Generated questions follow this format:

```json
[
  {
    "id": 1,
    "question": "What is the primary purpose of Azure Lighthouse?",
    "answer": "Azure Lighthouse enables service providers to manage customer Azure resources at scale through delegated resource management...",
    "difficulty": "easy",
    "topic": "azure-lighthouse"
  }
]
```

Questions span easy/medium/hard difficulty levels and cover diverse topics from the pack.

## Building the Fabric GraphQL Pack

The `build_fabric_pack.py` script builds a knowledge pack from Microsoft Fabric GraphQL documentation:

```bash
# Test build (5 URLs)
python scripts/build_fabric_pack.py --test-mode

# Full build
python scripts/build_fabric_pack.py

# Validate URLs first
python scripts/validate_pack_urls.py --pack fabric-graphql-expert --fix
python scripts/build_fabric_pack.py
```

Output: `data/packs/fabric-graphql-expert/pack.db`

## Statistical Significance

5 questions per pack is insufficient for reliable results (±2 points variance). Recommendations:

| Questions | Confidence | Cost (all packs) |
|-----------|------------|-----------------|
| 5 | Low (±2 pts) | ~$0.15 |
| 25 | Medium (±1 pt) | ~$0.75 |
| 50 | High (±0.5 pts) | ~$1.50 |
| All (~200) | Very high | ~$6 per pack |

## See Also

- [Pack Content Quality](dotnet-content-quality.md) — fixing thin content before evaluation
- [Vector Search Retrieval](vector-search-primary-retrieval.md) — retrieval pipeline improvements
- [Phase 1 Enhancements](phase1-enhancements.md) — enhancement components

> **Reference**: For a complete list of evaluation scripts and their arguments, see
> `scripts/run_all_packs_evaluation.py --help` and `scripts/run_enhancement_evaluation.py --help`.
