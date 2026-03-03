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
        "task_description": "CRITICAL: backend/api/v1/chat.py chat_stream endpoint at lines 177-180 calls _plan_query and _execute_query which were deleted in the dead code cleanup. Every SSE stream request raises AttributeError at runtime.\n\nFix: Replace the decomposed private-method calls in the generate function with a single agent.query call. Emit the answer as a token event and sources as a sources event.\n\nAlso fix: wikigr/packs/distribution.py line 142 - add filter='data' to tar.extractall call to prevent Python 3.14 deprecation warning.\n\nRun tests after to verify 0 failures.",
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
