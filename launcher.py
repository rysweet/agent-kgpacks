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
        "task_description": "Implement confidence-gated context injection for the KG agent - Issue 211 Improvement 1. HIGHEST IMPACT fix.\n\nProblem: The synthesis prompt ALWAYS injects retrieved content, regardless of relevance. When vector similarity is low, retrieved sections are irrelevant noise that misleads Claude.\n\nChanges needed:\n1. Add CONTEXT_CONFIDENCE_THRESHOLD = 0.5 class constant to KnowledgeGraphAgent in wikigr/agent/kg_agent.py\n2. In the query method, after _vector_primary_retrieve returns the tuple of kg_results and max_similarity, check if max_similarity is below CONTEXT_CONFIDENCE_THRESHOLD\n3. If below threshold: skip all pack context injection - hybrid retrieval, enhancements, full synthesis. Instead call a minimal synthesis that tells Claude to answer from its own expertise. Return query_type as confidence_gated_fallback.\n4. Add _synthesize_answer_minimal method that calls Claude with just the question and a note that the pack had no relevant content.\n5. Add tests in tests/agent/test_kg_agent_core.py for: low similarity triggers fallback, high similarity runs normal pipeline, minimal synthesis is used correctly.\n6. Update test_query_never_calls_llm_cypher in tests/agent/test_kg_agent_semantic.py - it uses distance=0.9 which means similarity=0.1 which now triggers confidence gating.\n\nExpected impact: Eliminates ALL negative deltas on packs where training is already strong - go-expert at 100 pct, react-expert at 100 pct.",
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
