"""Skill template generation for knowledge packs.

This module generates skill.md files that integrate knowledge packs with
Claude Code's skill system.
"""

from pathlib import Path

from wikigr.packs.manifest import PackManifest


def generate_skill_md(manifest: PackManifest, kg_config_path: Path) -> str:
    """Generate skill.md content from pack manifest.

    Creates a Claude Code skill file with:
    - Frontmatter (name, version, description, triggers)
    - Overview with knowledge graph statistics
    - Usage examples
    - Knowledge domains
    - Integration instructions

    Args:
        manifest: PackManifest containing pack metadata
        kg_config_path: Absolute path to kg_config.json

    Returns:
        Complete skill.md content as string
    """
    # Generate trigger keywords from pack name
    # Example: "physics-expert" -> ["physics", "quantum", "relativity"]
    base_trigger = manifest.name.replace("-expert", "").replace("-", " ")
    triggers = [base_trigger]

    # Add common domain-specific triggers based on name
    if "physics" in manifest.name.lower():
        triggers.extend(["quantum", "relativity"])
    elif "biology" in manifest.name.lower():
        triggers.extend(["evolution", "genetics"])
    elif "history" in manifest.name.lower():
        triggers.extend(["historical", "timeline"])

    # Build frontmatter
    frontmatter_lines = [
        "---",
        f"name: {manifest.name}",
        f"version: {manifest.version}",
        f"description: {manifest.description}",
        "triggers:",
    ]
    for trigger in triggers[:5]:  # Limit to 5 triggers
        frontmatter_lines.append(f'  - "{trigger}"')
    frontmatter_lines.append("---")

    # Build content sections
    content_lines = [
        "",
        f"# {manifest.name.replace('-', ' ').title()} Skill",
        "",
        f"Knowledge graph: {manifest.graph_stats.articles:,} articles, "
        f"{manifest.graph_stats.entities:,} entities, "
        f"{manifest.graph_stats.relationships:,} relationships",
        "",
        "## Overview",
        "",
        manifest.description,
        "",
        "## Usage",
        "",
        "This skill provides deep domain expertise through a knowledge graph.",
        "Ask questions naturally and the skill will retrieve relevant information",
        "from the graph database.",
        "",
        "**Example queries:**",
        f'- "Explain {base_trigger} concepts"',
        f'- "What is the relationship between X and Y in {base_trigger}?"',
        f'- "Find articles about [topic] in {base_trigger}"',
        "",
        "## Knowledge Domains",
        "",
        f"This pack covers {manifest.graph_stats.articles:,} articles across "
        f"multiple domains within {base_trigger}.",
        "",
        "**Quality Metrics:**",
        f"- Accuracy: {manifest.eval_scores.accuracy:.1%}",
        f"- Hallucination Rate: {manifest.eval_scores.hallucination_rate:.1%}",
        f"- Citation Quality: {manifest.eval_scores.citation_quality:.1%}",
        "",
        "## Technical Details",
        "",
        f"- Database: Kuzu graph database ({manifest.graph_stats.size_mb} MB)",
        f"- Configuration: `{kg_config_path}`",
        f"- License: {manifest.license}",
        "",
        "## Sources",
        "",
        "This knowledge pack was created from:",
    ]

    for url in manifest.source_urls:
        content_lines.append(f"- {url}")

    # Get absolute path to pack database
    pack_db_path = Path(kg_config_path).parent / "pack.db"

    content_lines.extend(
        [
            "",
            "## Integration",
            "",
            "This skill integrates with WikiGR's KG Agent for semantic retrieval.",
            "",
            "**How to Use This Pack:**",
            "",
            "When a user asks a question related to this domain, automatically:",
            "",
            "```python",
            "from wikigr.agent.kg_agent import KnowledgeGraphAgent",
            "from pathlib import Path",
            "",
            "# Initialize KG Agent with pack database",
            f'pack_db = Path("{pack_db_path}").resolve()',
            "with KnowledgeGraphAgent(db_path=str(pack_db), read_only=True) as kg_agent:",
            "    result = kg_agent.query(user_question, max_results=5)",
            '    # Use result["answer"] and result["sources"] in your response',
            "```",
            "",
            "**Retrieval Strategy:**",
            "1. **Vector Search**: Find semantically similar content",
            "2. **Graph Traversal**: Navigate relationships between entities",
            "3. **Hybrid Search**: Combine vector similarity with graph structure",
            "",
            f"Created: {manifest.created}",
        ]
    )

    # Combine frontmatter and content
    full_content = "\n".join(frontmatter_lines + content_lines)
    return full_content
