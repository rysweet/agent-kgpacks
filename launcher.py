#!/usr/bin/env python3
"""Workstream launcher - recipe runner execution."""
import sys
import logging

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
        "task_description": "Tests reference methods removed in the dead code cleanup: _validate_cypher, _execute_query, _execute_fallback_query, _plan_query. Fix: Remove tests/agent/test_validate_cypher.py entirely. Remove TestExecuteQuery and TestExecuteFallbackQuery classes from tests/agent/test_kg_agent_core.py. Remove test_handles_enriched_context from test_kg_agent_core.py. Fix test_query_skips_llm_when_high_confidence and test_query_never_calls_llm_cypher in test_kg_agent_semantic.py to not reference _plan_query. Add pytest.mark.skipif for test_kg_agent_queries.py when data/wikigr_30k.db is missing.",
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
