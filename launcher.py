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
        "task_description": "Fix broken and incomplete URL lists for the losing packs - Issue 211 Improvement 6.\n\nFor each pack, update data/packs/PACK/urls.txt:\n\n1. langchain-expert: Verify URLs use python.langchain.com not old docs.langchain.com. Add comprehensive coverage of concepts, how-to guides, tutorials, and integrations sections.\n\n2. openai-api-expert: Keep working platform.openai.com URLs. Add GitHub alternatives that bypass 403 blocks: openai-cookbook examples, openai-python SDK README, cookbook.openai.com pages, OpenAI Agents SDK.\n\n3. vercel-ai-sdk: Keep working sdk.vercel.ai URLs. Add GitHub source URLs - vercel/ai repo README, core packages, content/docs MDX files for reliable text extraction.\n\n4. llamaindex-expert: Expand from ~30 to ~70+ URLs. Add getting_started, understanding, optimizing subsections. Add module guides, agent/workflow docs, examples, API reference categories.\n\n5. zig-expert: Add zig.guide as comprehensive third-party guide, language-basics and standard-library sections, ziglang.org/learn, community resources, GitHub repo.\n\nDo NOT remove any working existing URLs. Keep same format with one URL per line and # comments.",
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
