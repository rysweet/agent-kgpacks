#!/usr/bin/env python3
"""Generate and install Claude Code skills for all knowledge packs.

Creates a SKILL.md file for each pack in .claude/skills/{pack-name}/SKILL.md.
Each skill auto-activates when its domain is mentioned in conversation.

Usage:
    python scripts/install_pack_skills.py
    python scripts/install_pack_skills.py --dry-run    # preview without writing
    python scripts/install_pack_skills.py --user-level # install to ~/.claude/skills/
"""

import argparse
import json
import sys
from pathlib import Path

PACKS_DIR = Path("data/packs")
PROJECT_SKILLS_DIR = Path(".claude/skills")
USER_SKILLS_DIR = Path.home() / ".claude" / "skills"


def load_manifest(pack_dir: Path) -> dict | None:
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    with open(manifest_path) as f:
        return json.load(f)


def generate_skill_md(pack_name: str, manifest: dict, pack_dir: Path) -> str:
    """Generate SKILL.md content for a knowledge pack.

    Creates actionable skill content with:
    - Concise description for auto-activation
    - Domain-specific retrieval instructions
    - Code example for KG Agent usage
    """
    description = manifest.get("description", f"Expert knowledge about {pack_name}")
    # Truncate description for frontmatter — must be very concise for context budget
    # Target: ~80 chars per skill to fit 49 skills in ~4000 char budget
    base_name = pack_name.replace("-expert", "").replace("-", " ")
    short_desc = f"Expert knowledge about {base_name}. Use when coding with or asking about {base_name}."
    if len(short_desc) > 120:
        short_desc = f"Expert {base_name} knowledge. Use for {base_name} questions and coding."

    stats = manifest.get("graph_stats", {})
    articles = stats.get("articles", 0)
    entities = stats.get("entities", 0)
    relationships = stats.get("relationships", 0)

    source_urls = manifest.get("source_urls", [])
    tags = manifest.get("tags", [])

    # Generate trigger keywords from pack name and tags
    base = pack_name.replace("-expert", "").replace("-", " ")
    triggers = [base] + tags[:4]
    # Deduplicate
    seen = set()
    triggers = [t for t in triggers if t not in seen and not seen.add(t)]

    db_path = (pack_dir / "pack.db").resolve()

    return f"""---
name: {pack_name}
description: "{short_desc}"
user-invocable: false
---

# {pack_name.replace('-', ' ').title()}

Knowledge graph with {articles} articles, {entities} entities, {relationships} relationships.

## When This Skill Activates

This skill provides expert knowledge about **{base}**. It activates when the user asks
about {base}, related APIs, libraries, or concepts covered by this pack.

## How to Use

When this skill is relevant, query the knowledge graph to get grounded, sourced answers:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

with KnowledgeGraphAgent(db_path="{db_path}", read_only=True) as agent:
    result = agent.query(user_question, max_results=5)
    # result["answer"] - synthesized answer with citations
    # result["sources"] - article titles used
    # result["entities"] - key entities found
    # result["facts"] - extracted facts
```

## What This Pack Covers

{description}

**Source documentation:**
{chr(10).join(f'- {url}' for url in source_urls[:5])}

## Key Guidance

1. **Always query the pack** before answering domain-specific questions — the KG has
   documentation that may be more current than training data.
2. **Cite sources** from the query results to ground your answers.
3. **Use vector search** (the default) for conceptual questions, and graph traversal
   for relationship questions ("how does X relate to Y?").
"""


def find_all_packs() -> list[dict]:
    """Find all packs with pack.db and manifest.json."""
    packs = []
    for pack_dir in sorted(PACKS_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue
        if not (pack_dir / "pack.db").exists():
            continue
        manifest = load_manifest(pack_dir)
        if manifest is None:
            continue
        packs.append({
            "name": pack_dir.name,
            "dir": pack_dir,
            "manifest": manifest,
        })
    return packs


def main():
    parser = argparse.ArgumentParser(description="Install pack skills for Claude Code")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--user-level", action="store_true", help="Install to ~/.claude/skills/")
    args = parser.parse_args()

    skills_dir = USER_SKILLS_DIR if args.user_level else PROJECT_SKILLS_DIR
    packs = find_all_packs()

    print(f"Found {len(packs)} packs with databases")
    print(f"Installing to: {skills_dir}")
    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    installed = 0
    total_desc_chars = 0

    for pack in packs:
        name = pack["name"]
        manifest = pack["manifest"]
        pack_dir = pack["dir"]

        skill_content = generate_skill_md(name, manifest, pack_dir)
        skill_dir = skills_dir / name
        skill_path = skill_dir / "SKILL.md"

        # Count description length for budget tracking (uses short_desc from generate_skill_md)
        base = name.replace("-expert", "").replace("-", " ")
        short_desc = f"Expert knowledge about {base}. Use when coding with or asking about {base}."
        total_desc_chars += len(short_desc)

        if args.dry_run:
            print(f"  Would create: {skill_path}")
            continue

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(skill_content)
        installed += 1

    print(f"\n{'Would install' if args.dry_run else 'Installed'}: {installed if not args.dry_run else len(packs)} skills")
    print(f"Total description chars: {total_desc_chars}")
    budget = 4000  # ~2% of 200K context
    if total_desc_chars > budget:
        print(f"WARNING: Descriptions exceed estimated context budget ({total_desc_chars} > {budget})")
        print(f"  Consider: export SLASH_COMMAND_TOOL_CHAR_BUDGET=8000")
    else:
        print(f"Within context budget ({total_desc_chars}/{budget} chars)")


if __name__ == "__main__":
    main()
