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
        "task_description": "Refactor: Extract the duplicated load_urls function from 45+ build scripts into a shared utility. Create wikigr/packs/utils.py with a load_urls function that reads urls.txt with blank/comment filtering. Then update all build scripts to import from the shared module. Run tests after.",
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
