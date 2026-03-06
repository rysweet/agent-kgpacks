#!/usr/bin/env python3
"""Generate docs/catalog.md from pack manifest.json files and evaluation data.

Usage:
    python scripts/generate_catalog.py            # writes docs/catalog.md
    python scripts/generate_catalog.py --stdout    # prints to stdout instead
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = REPO_ROOT / "data" / "packs"
EVAL_FILE = PACKS_DIR / "all_packs_evaluation.json"
OUTPUT_FILE = REPO_ROOT / "docs" / "catalog.md"

# Category -> list of pack directory names (order preserved)
CATEGORIES: dict[str, list[str]] = {
    "Languages": [
        "rust-expert",
        "python-expert",
        "go-expert",
        "java-expert",
        "kotlin-expert",
        "csharp-expert",
        "cpp-expert",
        "ruby-expert",
        "swift-expert",
        "typescript-expert",
        "zig-expert",
    ],
    "AI/ML Frameworks": [
        "anthropic-api-expert",
        "openai-api-expert",
        "claude-agent-sdk",
        "langchain-expert",
        "llamaindex-expert",
        "huggingface-transformers",
        "dspy-expert",
        "crew-ai-expert",
        "autogen-expert",
        "microsoft-agent-framework",
        "semantic-kernel",
    ],
    "Web": [
        "react-expert",
        "nextjs-expert",
        "vercel-ai-sdk",
        "vscode-extensions",
    ],
    "Infrastructure": [
        "docker-expert",
        "kubernetes-networking",
        "terraform-expert",
        "bicep-infrastructure",
        "github-actions-advanced",
    ],
    "Databases": [
        "ladybugdb-expert",
        "postgresql-internals",
        "opencypher-expert",
    ],
    "Azure / Microsoft": [
        "azure-ai-foundry",
        "azure-lighthouse",
        "fabric-graph-gql-expert",
        "fabric-graphql-expert",
        "security-copilot",
        "sentinel-graph",
        "workiq-mcp",
    ],
    "Other": [
        "mcp-protocol",
        "github-copilot-sdk",
        "opentelemetry-expert",
        "prompt-engineering",
        "wasm-components",
        "physics-expert",
        "rust-async-expert",
        "dotnet-expert",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_manifests() -> dict[str, dict[str, Any]]:
    """Return {pack_name: manifest_dict} for every pack with a manifest.json."""
    manifests: dict[str, dict[str, Any]] = {}
    for entry in sorted(PACKS_DIR.iterdir()):
        mf = entry / "manifest.json"
        if entry.is_dir() and mf.is_file():
            with open(mf) as f:
                manifests[entry.name] = json.load(f)
    return manifests


def load_eval() -> dict[str, dict[str, Any]]:
    """Return per-pack evaluation data (or empty dict if file missing)."""
    if not EVAL_FILE.is_file():
        return {}
    with open(EVAL_FILE) as f:
        data = json.load(f)
    return data.get("per_pack", {})


def eval_delta(scores: dict[str, list[int]]) -> str:
    """Compute enhanced accuracy minus training accuracy as a '+Xpp' string."""
    training = scores.get("training", [])
    enhanced = scores.get("enhanced", [])
    if not training or not enhanced:
        return "--"
    train_acc = sum(1 for s in training if s >= 8) / len(training) * 100
    enh_acc = sum(1 for s in enhanced if s >= 8) / len(enhanced) * 100
    delta = enh_acc - train_acc
    if delta > 0:
        return f"+{delta:.0f}pp"
    if delta == 0:
        return "0pp"
    return f"{delta:.0f}pp"


def eval_enhanced_accuracy(scores: dict[str, list[int]]) -> str:
    """Return enhanced accuracy as a percentage string."""
    enhanced = scores.get("enhanced", [])
    if not enhanced:
        return "--"
    acc = sum(1 for s in enhanced if s >= 8) / len(enhanced) * 100
    return f"{acc:.0f}%"


def fmt_sources(urls: list[str], limit: int = 2) -> str:
    """Format source URLs for table display (first N, as markdown links)."""
    if not urls:
        return "--"
    parts = []
    for url in urls[:limit]:
        # Shorten the display text
        display = url.replace("https://", "").replace("http://", "")
        if len(display) > 50:
            display = display[:47] + "..."
        parts.append(f"[{display}]({url})")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------


def generate_summary_table(manifests: dict[str, dict], eval_data: dict[str, dict]) -> str:
    """Generate the top-level summary statistics."""
    total_articles = sum(m.get("graph_stats", {}).get("articles", 0) for m in manifests.values())
    total_entities = sum(m.get("graph_stats", {}).get("entities", 0) for m in manifests.values())
    total_rels = sum(m.get("graph_stats", {}).get("relationships", 0) for m in manifests.values())

    # Compute aggregate eval
    all_training: list[int] = []
    all_enhanced: list[int] = []
    pack_wins = 0
    pack_ties = 0
    packs_evaluated = 0
    for _pack_name, entry in eval_data.items():
        scores = entry.get("scores", {})
        training = scores.get("training", [])
        enhanced = scores.get("enhanced", [])
        if training and enhanced:
            packs_evaluated += 1
            all_training.extend(training)
            all_enhanced.extend(enhanced)
            t_acc = sum(1 for s in training if s >= 8) / len(training) * 100
            e_acc = sum(1 for s in enhanced if s >= 8) / len(enhanced) * 100
            if e_acc > t_acc:
                pack_wins += 1
            elif e_acc == t_acc:
                pack_ties += 1

    train_acc = (
        sum(1 for s in all_training if s >= 8) / len(all_training) * 100 if all_training else 0
    )
    enh_acc = (
        sum(1 for s in all_enhanced if s >= 8) / len(all_enhanced) * 100 if all_enhanced else 0
    )

    lines = [
        "| Metric | Value |",
        "|--------|------:|",
        f"| Total packs | **{len(manifests)}** |",
        f"| Total articles | **{total_articles:,}** |",
        f"| Total entities | **{total_entities:,}** |",
        f"| Total relationships | **{total_rels:,}** |",
        f"| Packs evaluated | **{packs_evaluated}** |",
        f"| Baseline accuracy (Claude alone) | **{train_acc:.0f}%** |",
        f"| Enhanced accuracy (with pack) | **{enh_acc:.0f}%** |",
        f"| Packs where pack wins | **{pack_wins} of {packs_evaluated}** |",
    ]
    return "\n".join(lines)


def generate_category_table(
    pack_names: list[str],
    manifests: dict[str, dict],
    eval_data: dict[str, dict],
) -> str:
    """Generate a markdown table for one category of packs."""
    header = (
        "| Pack | Description | Articles | Entities | Rels "
        "| Eval (enhanced) | Delta vs baseline | Sources |"
    )
    sep = (
        "|------|-------------|:--------:|:--------:|:----:"
        "|:---------------:|:-----------------:|---------|"
    )
    rows = [header, sep]

    for name in pack_names:
        m = manifests.get(name)
        if m is None:
            continue
        gs = m.get("graph_stats", {})
        articles = gs.get("articles", 0)
        entities = gs.get("entities", 0)
        rels = gs.get("relationships", 0)
        desc = m.get("description", "")
        # Truncate long descriptions for table readability
        if len(desc) > 100:
            desc = desc[:97] + "..."
        urls = m.get("source_urls", [])
        sources = fmt_sources(urls, limit=2)

        edata = eval_data.get(name, {})
        scores = edata.get("scores", {})
        acc_str = eval_enhanced_accuracy(scores) if scores else "--"
        delta_str = eval_delta(scores) if scores else "--"

        row = (
            f"| **{name}** | {desc} | {articles} | {entities} | {rels} "
            f"| {acc_str} | {delta_str} | {sources} |"
        )
        rows.append(row)

    return "\n".join(rows)


def generate_install_reference(manifests: dict[str, dict]) -> str:
    """Generate a compact install-command reference list."""
    lines = ["```bash"]
    for name in sorted(manifests.keys()):
        lines.append(f"/kg-pack install {name}")
    lines.append("```")
    return "\n".join(lines)


def generate_catalog() -> str:
    """Generate the full catalog markdown document."""
    manifests = load_manifests()
    eval_data = load_eval()

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    sections: list[str] = []

    # Title and introduction
    sections.append("# Knowledge Pack Catalog")
    sections.append("")
    sections.append(
        f"**{len(manifests)} packs** covering programming languages, "
        "AI/ML frameworks, cloud infrastructure, databases, and more."
    )
    sections.append("")
    sections.append(f"*Auto-generated on {now} from pack manifest data.*")
    sections.append("")

    # Summary
    sections.append("## Summary")
    sections.append("")
    sections.append(generate_summary_table(manifests, eval_data))
    sections.append("")

    # Quick install
    sections.append("## Quick Install")
    sections.append("")
    sections.append("Install any pack as a Claude Code skill:")
    sections.append("")
    sections.append("```bash")
    sections.append("/kg-pack install <pack-name>")
    sections.append("```")
    sections.append("")

    # Category sections
    for category, pack_names in CATEGORIES.items():
        sections.append(f"## {category}")
        sections.append("")
        sections.append(generate_category_table(pack_names, manifests, eval_data))
        sections.append("")

    # Uncategorized packs (safety net)
    all_categorized = set()
    for names in CATEGORIES.values():
        all_categorized.update(names)
    uncategorized = sorted(set(manifests.keys()) - all_categorized)
    if uncategorized:
        sections.append("## Uncategorized")
        sections.append("")
        sections.append(generate_category_table(uncategorized, manifests, eval_data))
        sections.append("")

    # Install reference
    sections.append("## All Install Commands")
    sections.append("")
    sections.append(generate_install_reference(manifests))
    sections.append("")

    # Evaluation methodology note
    sections.append("## Evaluation Methodology")
    sections.append("")
    sections.append(
        "Each pack is evaluated on 5 domain-specific questions scored 1-10 by Claude Opus. "
        "**Accuracy** counts scores >= 8 as correct. "
        "**Delta** is the difference between enhanced (with pack) accuracy and training "
        "(Claude alone) accuracy in percentage points."
    )
    sections.append("")

    # Regeneration instructions
    sections.append("---")
    sections.append("")
    sections.append("*To regenerate this page:*")
    sections.append("")
    sections.append("```bash")
    sections.append("python scripts/generate_catalog.py")
    sections.append("```")
    sections.append("")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Knowledge Pack catalog page.")
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing docs/catalog.md",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write to a custom output path (overrides default docs/catalog.md)",
    )
    args = parser.parse_args()

    content = generate_catalog()

    if args.stdout:
        print(content)
    else:
        out_path = Path(args.output) if args.output else OUTPUT_FILE
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content)
        print(f"Wrote {out_path} ({len(content):,} bytes, {content.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
