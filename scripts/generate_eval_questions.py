#!/usr/bin/env python3
"""Generate evaluation Q&A pairs for a knowledge pack using Claude.

Generates 50 diverse evaluation questions per pack. When a pack database
exists, article titles and content snippets are sampled to ground the
questions in actual pack content. When no database exists, questions are
generated from domain knowledge about the pack topic.

Usage:
    python scripts/generate_eval_questions.py --pack azure-lighthouse
    python scripts/generate_eval_questions.py --pack physics-expert --db data/packs/physics-expert/pack.db
    python scripts/generate_eval_questions.py --pack security-copilot --count 50

Output:
    data/packs/{pack-name}/eval/questions.json  (JSON array)
    data/packs/{pack-name}/eval/questions.jsonl (JSONL, one object per line)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import anthropic

# Add project root to path for optional kuzu import
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
DEFAULT_COUNT = 50

# Domain descriptions for well-known packs (used when no DB is available)
DOMAIN_DESCRIPTIONS: dict[str, str] = {
    "azure-lighthouse": (
        "Azure Lighthouse is a service that enables cross-tenant management, "
        "allowing service providers to manage customer Azure resources at scale. "
        "Key topics: delegated resource management, Azure Active Directory, "
        "managed services offers, Azure Marketplace, role assignments, "
        "just-in-time access, Azure Policy, Azure Monitor, ARM templates, "
        "Bicep templates, multi-tenant architectures, and security best practices."
    ),
    "security-copilot": (
        "Microsoft Security Copilot is an AI-powered security analysis tool that "
        "combines large language models with security-specific plugins and skills. "
        "Key topics: threat intelligence, incident response, vulnerability assessment, "
        "KQL queries, Microsoft Sentinel integration, Defender for Endpoint, "
        "Entra ID security, MITRE ATT&CK framework, promptbooks, custom plugins, "
        "natural language queries, and security operations center (SOC) workflows."
    ),
    "sentinel-graph": (
        "Microsoft Sentinel is a cloud-native SIEM (Security Information and Event "
        "Management) and SOAR (Security Orchestration, Automation, and Response) "
        "solution. Key topics: KQL (Kusto Query Language), analytic rules, "
        "workbooks, playbooks (Logic Apps), data connectors, threat hunting, "
        "incidents and alerts, UEBA, entity mapping, watchlists, content hub, "
        "Microsoft Graph Security API, investigation graph, and automation rules."
    ),
    "fabric-graphql-expert": (
        "Microsoft Fabric API for GraphQL provides GraphQL access to Fabric data "
        "sources. Key topics: GraphQL schema generation, authentication with "
        "Microsoft Entra ID, pagination (cursor-based), filtering operators, "
        "mutations, VS Code development, schema export/introspection, security "
        "best practices, performance optimization, monitoring with Azure Monitor, "
        "troubleshooting, OneLake, lakehouses, data warehouses, and SQL databases."
    ),
    "fabric-graph-gql-expert": (
        "Microsoft Fabric API for GraphQL provides GraphQL access to Fabric data "
        "sources. Key topics: GraphQL schema generation, authentication with "
        "Microsoft Entra ID, pagination (cursor-based), filtering operators, "
        "mutations, VS Code development, schema export/introspection, security "
        "best practices, performance optimization, monitoring with Azure Monitor, "
        "troubleshooting, OneLake, lakehouses, data warehouses, and SQL databases."
    ),
    "physics-expert": (
        "Comprehensive physics knowledge spanning classical mechanics, quantum "
        "mechanics, thermodynamics, electromagnetism, relativity, and modern physics."
    ),
    "dotnet-expert": (
        "Expert .NET development knowledge covering C#, ASP.NET Core, Entity "
        "Framework, LINQ, async/await, dependency injection, minimal APIs, and Blazor."
    ),
    "rust-expert": (
        "Expert Rust programming knowledge covering ownership, borrowing, lifetimes, "
        "traits, async/await, unsafe code, macros, Cargo, and systems programming."
    ),
}

# Difficulty distribution: ~40% easy, 40% medium, 20% hard
DIFFICULTY_DISTRIBUTION = [
    ("easy", 20),
    ("medium", 20),
    ("hard", 10),
]


def get_domain_name(pack_name: str) -> str:
    """Convert pack name to a clean domain identifier."""
    return pack_name.replace("-", "_").lower()


def sample_db_context(db_path: Path, max_articles: int = 20) -> str:
    """Sample article titles and content snippets from a pack database.

    Args:
        db_path: Path to the Kuzu pack database
        max_articles: Maximum number of articles to sample

    Returns:
        Formatted context string with article titles and snippets, or empty string on failure
    """
    try:
        import kuzu

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        result = conn.execute(
            f"MATCH (a:Article) RETURN a.title AS title LIMIT {max_articles}"
        )
        df = result.get_as_df()
        if df.empty:
            logger.warning(f"No articles found in {db_path}")
            return ""

        titles = df["title"].tolist()

        result = conn.execute(
            "MATCH (a:Article)-[:HAS_SECTION]->(s:Section) "
            f"RETURN a.title AS title, s.content AS content LIMIT {max_articles}"
        )
        sections_df = result.get_as_df()

        context_parts = [f"Pack contains {len(titles)} articles including:", ""]
        for title in titles[:15]:
            context_parts.append(f"- {title}")

        if not sections_df.empty:
            context_parts.append("\nSample content snippets:")
            seen_titles: set[str] = set()
            for _, row in sections_df.iterrows():
                if row["title"] not in seen_titles and len(seen_titles) < 5:
                    snippet = str(row["content"])[:200].replace("\n", " ")
                    context_parts.append(f'\n[{row["title"]}]: {snippet}...')
                    seen_titles.add(row["title"])

        return "\n".join(context_parts)

    except Exception as e:
        logger.warning(f"Could not query database {db_path}: {e}")
        return ""


def build_generation_prompt(
    pack_name: str,
    domain_description: str,
    db_context: str,
    difficulty: str,
    count: int,
    id_prefix: str,
    id_start: int,
) -> str:
    """Build the Claude prompt for generating evaluation questions."""
    domain_name = get_domain_name(pack_name)

    db_section = f"\n\nPACK DATABASE CONTEXT:\n{db_context}\n" if db_context else ""

    difficulty_guidance = {
        "easy": (
            "Easy questions test basic factual knowledge: definitions, key concepts, "
            "simple procedures. A junior practitioner should answer confidently."
        ),
        "medium": (
            "Medium questions require understanding of how things work, trade-offs, "
            "configuration details, or combining multiple concepts."
        ),
        "hard": (
            "Hard questions test deep expertise: edge cases, performance implications, "
            "security considerations, architecture decisions, or complex troubleshooting."
        ),
    }

    return f"""Generate exactly {count} {difficulty} evaluation questions for a knowledge pack about: {domain_description}
{db_section}
DIFFICULTY: {difficulty} — {difficulty_guidance[difficulty]}

OUTPUT FORMAT: Return a JSON array. Each element must have these exact fields:
- "id": string like "{id_prefix}_{id_start:03d}", "{id_prefix}_{id_start+1:03d}", etc.
- "domain": "{domain_name}"
- "difficulty": "{difficulty}"
- "question": the question text (specific, testable, domain-relevant)
- "ground_truth": concise factual answer (1-3 sentences, technically accurate)
- "source": a short identifier for the relevant concept/feature (e.g., "authentication")

REQUIREMENTS:
- Questions must test REAL knowledge about {pack_name}, not generic concepts
- Questions must be diverse: cover different features, use cases, configurations
- ground_truth answers must be technically accurate and complete
- No duplicate or trivially similar questions
- Return ONLY the JSON array, no explanation

JSON array:"""


def parse_questions_from_response(
    response_text: str,
    expected_count: int,
    pack_name: str,
) -> list[dict]:
    """Parse and validate questions from Claude's response.

    Extracts the JSON array from the response text and validates each question
    has the required fields with valid values.
    """
    text = response_text.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array found in response: {text[:200]}")

    questions = json.loads(text[start:end])
    if not isinstance(questions, list):
        raise ValueError(f"Expected list, got {type(questions)}")

    domain_name = get_domain_name(pack_name)
    required_fields = {"id", "domain", "difficulty", "question", "ground_truth", "source"}
    valid_difficulties = {"easy", "medium", "hard"}

    validated = []
    for i, q in enumerate(questions):
        missing = required_fields - set(q.keys())
        if missing:
            logger.warning(f"Question {i} missing fields {missing}, skipping")
            continue
        if q["difficulty"] not in valid_difficulties:
            logger.warning(f"Question {i} invalid difficulty {q['difficulty']!r}, fixing to medium")
            q["difficulty"] = "medium"
        q["domain"] = domain_name
        validated.append(q)

    if len(validated) < expected_count * 0.8:
        logger.warning(f"Only {len(validated)}/{expected_count} valid questions parsed")

    return validated


def generate_questions_for_difficulty(
    client: anthropic.Anthropic,
    pack_name: str,
    domain_description: str,
    db_context: str,
    difficulty: str,
    count: int,
    id_prefix: str,
    id_start: int,
) -> list[dict]:
    """Call Claude to generate questions for one difficulty level."""
    prompt = build_generation_prompt(
        pack_name=pack_name,
        domain_description=domain_description,
        db_context=db_context,
        difficulty=difficulty,
        count=count,
        id_prefix=id_prefix,
        id_start=id_start,
    )

    logger.info(f"Generating {count} {difficulty} questions for {pack_name}...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text if response.content else ""
    questions = parse_questions_from_response(text, count, pack_name)
    logger.info(f"Generated {len(questions)} {difficulty} questions")
    return questions


def generate_eval_questions(
    pack_name: str,
    db_path: Path | None,
    output_dir: Path,
    total_count: int = DEFAULT_COUNT,
) -> list[dict]:
    """Generate all evaluation questions for a pack and save to output_dir.

    Args:
        pack_name: Pack name (e.g., 'azure-lighthouse')
        db_path: Optional Kuzu database path for context sampling
        output_dir: Directory to write questions.json and questions.jsonl
        total_count: Total questions to generate (default 50)

    Returns:
        List of generated question dicts
    """
    client = anthropic.Anthropic()

    domain_description = DOMAIN_DESCRIPTIONS.get(
        pack_name,
        f"Expert knowledge about {pack_name.replace('-', ' ').title()}",
    )

    db_context = ""
    if db_path and db_path.exists():
        logger.info(f"Sampling context from database: {db_path}")
        db_context = sample_db_context(db_path)
        if db_context:
            logger.info(f"Got DB context ({len(db_context)} chars)")
    else:
        logger.info(f"No database available, using domain knowledge for {pack_name}")

    # Scale difficulty counts to total_count
    base_total = sum(n for _, n in DIFFICULTY_DISTRIBUTION)
    difficulty_counts: dict[str, int] = {
        d: max(1, round(n * total_count / base_total))
        for d, n in DIFFICULTY_DISTRIBUTION
    }
    # Fix rounding to hit exact total
    diff = total_count - sum(difficulty_counts.values())
    if diff != 0:
        difficulty_counts["medium"] += diff

    # Build 2-char ID prefix from pack name
    words = [w for w in pack_name.split("-") if w]
    id_prefix = "".join(w[0] for w in words)[:2].lower()
    if len(id_prefix) < 2:
        id_prefix = (id_prefix + pack_name[:2])[:2]

    all_questions: list[dict] = []
    id_counter = 1

    for difficulty, count in difficulty_counts.items():
        batch = generate_questions_for_difficulty(
            client=client,
            pack_name=pack_name,
            domain_description=domain_description,
            db_context=db_context,
            difficulty=difficulty,
            count=count,
            id_prefix=id_prefix,
            id_start=id_counter,
        )
        for q in batch:
            q["id"] = f"{id_prefix}_{id_counter:03d}"
            id_counter += 1
        all_questions.extend(batch)

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for q in all_questions:
        key = q["question"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(q)

    logger.info(f"Total unique questions: {len(unique)}")

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "questions.json"
    with open(json_path, "w") as f:
        json.dump(unique, f, indent=2)
        f.write("\n")
    logger.info(f"Saved JSON array: {json_path}")

    jsonl_path = output_dir / "questions.jsonl"
    with open(jsonl_path, "w") as f:
        for q in unique:
            f.write(json.dumps(q) + "\n")
    logger.info(f"Saved JSONL: {jsonl_path}")

    return unique


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate evaluation Q&A pairs for a knowledge pack using Claude"
    )
    parser.add_argument("--pack", required=True, help="Pack name (e.g., azure-lighthouse)")
    parser.add_argument("--db", help="Path to pack database (auto-detected if omitted)")
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Total questions to generate (default: {DEFAULT_COUNT})",
    )
    parser.add_argument("--output", help="Output directory (default: data/packs/{pack}/eval/)")
    args = parser.parse_args()

    pack_name = args.pack

    db_path: Path | None = None
    if args.db:
        db_path = Path(args.db)
    else:
        auto_db = Path(f"data/packs/{pack_name}/pack.db")
        if auto_db.exists():
            db_path = auto_db
            logger.info(f"Auto-detected database: {db_path}")

    output_dir = Path(args.output) if args.output else Path(f"data/packs/{pack_name}/eval")

    try:
        questions = generate_eval_questions(
            pack_name=pack_name,
            db_path=db_path,
            output_dir=output_dir,
            total_count=args.count,
        )
        print(f"\nGenerated {len(questions)} evaluation questions for '{pack_name}'")
        print(f"  JSON:  {output_dir / 'questions.json'}")
        print(f"  JSONL: {output_dir / 'questions.jsonl'}")
    except anthropic.AuthenticationError:
        logger.error("ANTHROPIC_API_KEY is not set or invalid")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
