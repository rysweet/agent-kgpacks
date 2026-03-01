#!/usr/bin/env python3
"""Workstream launcher - recipe runner execution."""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

try:
    from amplihack.recipes import run_recipe_by_name
    from amplihack.recipes.adapters.cli_subprocess import CLISubprocessAdapter
except ImportError:
    print("ERROR: amplihack package not importable. Falling back to classic mode.")
    sys.exit(2)

adapter = CLISubprocessAdapter(cli="claude", working_dir=".")
result = run_recipe_by_name(
    "default-workflow",
    adapter=adapter,
    user_context={
        "task_description": "Implement cross-encoder reranking for improved retrieval precision - Issue 211 Improvement 3.\n\nProblem: The bi-encoder BGE bge-base-en-v1.5 embeds queries and documents independently. Cross-encoders see BOTH together for much more accurate relevance.\n\nChanges needed:\n1. Create new file wikigr/agent/cross_encoder.py with CrossEncoderReranker class using cross-encoder/ms-marco-MiniLM-L-12-v2 at 33MB on CPU. Method: rerank with query, results, top_k=5 returns top-k results sorted by cross-encoder score with ce_score added to each dict.\n2. In wikigr/agent/kg_agent.py __init__: add enable_cross_encoder=False parameter. When True and use_enhancements=True, instantiate CrossEncoderReranker.\n3. In _vector_primary_retrieve: if cross_encoder is active, fetch 2x candidates from semantic_search, then rerank down to max_results.\n4. sentence-transformers already includes CrossEncoder - no new dependencies needed.\n5. Create tests/agent/test_cross_encoder.py: test reranking with mocked model, empty results, top_k filtering, ce_score added, graceful init failure.\n\nExpected impact: +10-15 pct retrieval precision. Cost: ~50ms per rerank which is negligible vs 10-15s Opus synthesis.",
        "repo_path": ".",
    },
)

print()
print("=" * 60)
print("RECIPE EXECUTION RESULTS")
print("=" * 60)
for sr in result.step_results:
    print(f"  [{sr.status.value:>9}] {sr.step_id}")
print(f"\nOverall: {'SUCCESS' if result.success else 'FAILED'}")
sys.exit(0 if result.success else 1)
