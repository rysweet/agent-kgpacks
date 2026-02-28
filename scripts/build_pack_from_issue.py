#!/usr/bin/env python3
"""Build a knowledge pack from a GitHub issue JSON payload.

Orchestrates the full pack-build pipeline: scaffold, URL discovery,
build script generation, database build, and eval question generation.

Usage:
    python scripts/build_pack_from_issue.py --issue-json '{"pack_name":"aws-lambda","description":"..."}'

Input JSON fields:
    pack_name (str, required): Pack identifier (lowercase, hyphens)
    description (str, required): Domain description for eval question generation
    urls (list[str], optional): Seed URLs to crawl
    search_terms (str, optional): Comma-separated terms for URL discovery
    article_count_target (int, optional): Target article count (default 20)

Output:
    Prints JSON result on the last line with build statistics.
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


def validate_pack_name(name: str) -> str:
    """Validate pack name: lowercase alphanumeric and hyphens only."""
    if not name:
        raise ValueError("Pack name is required")
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", name) and not re.match(r"^[a-z0-9]+$", name):
        raise ValueError(
            f"Invalid pack name '{name}': use lowercase alphanumeric and hyphens only, "
            "no leading/trailing hyphens"
        )
    if len(name) > 60:
        raise ValueError(f"Pack name too long ({len(name)} chars, max 60)")
    return name


def discover_urls_from_search(search_terms: str, target_count: int) -> list[str]:
    """Use the Anthropic API to suggest documentation URLs from search terms.

    This is a lightweight approach: ask Claude to suggest authoritative URLs
    for the given topic rather than running a web search.
    """
    try:
        from anthropic import Anthropic

        client = Anthropic()
        prompt = (
            f"List {target_count} authoritative documentation URLs for learning about: {search_terms}\n\n"
            "Requirements:\n"
            "- Only include real, currently-accessible URLs\n"
            "- Prefer official documentation sites\n"
            "- Include a mix of getting-started, reference, and advanced topics\n"
            "- One URL per line, no numbering or descriptions\n"
            "- Only output URLs, nothing else"
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        urls = [line.strip() for line in text.splitlines() if line.strip().startswith("http")]
        logger.info(f"Discovered {len(urls)} URLs from search terms")
        return urls
    except Exception as e:
        logger.warning(f"URL discovery failed: {e}")
        return []


def create_urls_file(pack_dir: Path, urls: list[str], pack_name: str) -> Path:
    """Write urls.txt for the pack."""
    urls_path = pack_dir / "urls.txt"
    with open(urls_path, "w") as f:
        f.write(f"# {pack_name} - Source URLs\n")
        f.write(f"# Generated {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n\n")
        for url in urls:
            f.write(f"{url}\n")
    logger.info(f"Created {urls_path} with {len(urls)} URLs")
    return urls_path


def generate_build_script(pack_name: str, description: str) -> Path:
    """Generate a build script from the standard template."""
    # Derive identifiers from pack name
    pack_var = pack_name.replace("-", "_")
    # Category: title-case the pack name without trailing -expert
    category_base = pack_name.replace("-expert", "").replace("-", " ")
    category = category_base.title()
    domain = pack_var.replace("_expert", "")

    script_path = PROJECT_ROOT / "scripts" / f"build_{pack_var}_pack.py"

    content = f'''#!/usr/bin/env python3
"""
Build {category} Knowledge Pack from URLs.

Reads documentation URLs from urls.txt and builds a complete
knowledge graph with LLM-based extraction using the web content pipeline.

Usage:
    python scripts/build_{pack_var}_pack.py [--test-mode]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import kuzu  # noqa: E402

from bootstrap.schema.ryugraph_schema import create_schema  # noqa: E402
from bootstrap.src.embeddings.generator import EmbeddingGenerator  # noqa: E402
from bootstrap.src.extraction.llm_extractor import get_extractor  # noqa: E402
from bootstrap.src.sources.web import WebContentSource  # noqa: E402

PACK_NAME = {json.dumps(pack_name)}
PACK_DIR = Path(f"data/packs/{{PACK_NAME}}")
URLS_FILE = PACK_DIR / "urls.txt"
DB_PATH = PACK_DIR / "pack.db"
MANIFEST_PATH = PACK_DIR / "manifest.json"
CATEGORY = {json.dumps(category)}
DOMAIN = {json.dumps(domain)}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/build_{{PACK_NAME.replace('-', '_')}}_pack.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_urls(urls_file: Path, limit: int | None = None) -> list[str]:
    with open(urls_file) as f:
        urls = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#") and line.strip().startswith("http")
        ]
    if limit:
        urls = urls[:limit]
        logger.info(f"Limited to {{limit}} URLs for testing")
    logger.info(f"Loaded {{len(urls)}} URLs from {{urls_file}}")
    return urls


def process_url(url, conn, web_source, embedder, extractor) -> bool:
    try:
        article = web_source.fetch_article(url)
        if not article or not article.content:
            logger.warning(f"No content for {{url}}")
            return False
        title = article.title
        result = conn.execute(
            "MATCH (a:Article {{title: $title}}) RETURN a.title AS title", {{"title": title}}
        )
        if not result.get_as_df().empty:
            logger.info(f"Skipping {{title!r}} (already exists)")
            return True
        sections = web_source.parse_sections(article.content)
        if not sections:
            sections = [{{"title": "Overview", "content": article.content, "level": 1}}]
        extraction = extractor.extract_from_article(
            title=title, sections=sections, max_sections=5, domain=DOMAIN
        )
        word_count = sum(len(s["content"].split()) for s in sections)
        conn.execute(
            "CREATE (a:Article {{title: $title, category: $category, word_count: $wc}})",
            {{"title": title, "category": CATEGORY, "wc": word_count}},
        )
        for entity in extraction.entities:
            conn.execute(
                "MERGE (e:Entity {{entity_id: $eid}}) ON CREATE SET e.name = $name, e.type = $type",
                {{"eid": entity.name, "name": entity.name, "type": entity.type}},
            )
            conn.execute(
                "MATCH (a:Article {{title: $title}}), (e:Entity {{entity_id: $eid}}) "
                "MERGE (a)-[:HAS_ENTITY]->(e)",
                {{"title": title, "eid": entity.name}},
            )
        for rel in extraction.relationships:
            for eid in (rel.source, rel.target):
                conn.execute(
                    "MERGE (e:Entity {{entity_id: $eid}}) ON CREATE SET e.name = $eid, e.type = 'concept'",
                    {{"eid": eid}},
                )
            conn.execute(
                "MATCH (s:Entity {{entity_id: $source}}), (t:Entity {{entity_id: $target}}) "
                "MERGE (s)-[:ENTITY_RELATION {{relation: $rel, context: $ctx}}]->(t)",
                {{
                    "source": rel.source,
                    "target": rel.target,
                    "rel": rel.relation,
                    "ctx": rel.context,
                }},
            )
        for idx, fact in enumerate(extraction.key_facts):
            conn.execute(
                "MATCH (a:Article {{title: $title}}) "
                "CREATE (a)-[:HAS_FACT]->(f:Fact {{fact_id: $fid, content: $content}})",
                {{"title": title, "fid": f"{{title}}:fact:{{idx}}", "content": fact}},
            )
        for idx, section in enumerate(sections[:3]):
            sid = f"{{title}}#{{idx}}"
            content = section["content"]
            embedding = embedder.generate([content])[0].tolist()
            conn.execute(
                "MATCH (a:Article {{title: $title}}) "
                "CREATE (a)-[:HAS_SECTION {{section_index: $idx}}]->"
                "(s:Section {{section_id: $sid, content: $content, embedding: $emb}})",
                {{"title": title, "idx": idx, "sid": sid, "content": content, "emb": embedding}},
            )
        logger.info(f"Processed {{url!r}} -> {{title!r}}")
        return True
    except Exception as e:
        logger.error(f"Failed to process {{url}}: {{e}}")
        return False


def create_manifest(db_path, manifest_path, articles, entities, relationships):
    size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
    manifest = {{
        "name": PACK_NAME,
        "version": "1.0.0",
        "description": {json.dumps(description)},
        "graph_stats": {{
            "articles": int(articles),
            "entities": int(entities),
            "relationships": int(relationships),
            "size_mb": round(size_mb, 2),
        }},
        "eval_scores": {{"accuracy": 0.0, "hallucination_rate": 0.0, "citation_quality": 0.0}},
        "source_urls": [],
        "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "license": "MIT",
    }}
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\\n")
    logger.info(f"Manifest saved to {{manifest_path}}")


def build_pack(test_mode=False):
    limit = 5 if test_mode else None
    urls = load_urls(URLS_FILE, limit=limit)
    if test_mode:
        logger.info("TEST MODE: Building 5-URL pack")
    if DB_PATH.exists():
        import shutil

        logger.warning(f"Database already exists: {{DB_PATH}} -- removing for rebuild")
        shutil.rmtree(DB_PATH) if DB_PATH.is_dir() else DB_PATH.unlink()
    create_schema(str(DB_PATH), drop_existing=True)
    db = kuzu.Database(str(DB_PATH))
    conn = kuzu.Connection(db)
    web_source = WebContentSource()
    embedder = EmbeddingGenerator()
    extractor = get_extractor()
    successful, failed = 0, 0
    for i, url in enumerate(urls, 1):
        logger.info(f"Processing {{i}}/{{len(urls)}}: {{url}}")
        if process_url(url, conn, web_source, embedder, extractor):
            successful += 1
        else:
            failed += 1
    a = conn.execute("MATCH (a:Article) RETURN count(a) AS c").get_as_df().iloc[0]["c"]
    e = conn.execute("MATCH (e:Entity) RETURN count(e) AS c").get_as_df().iloc[0]["c"]
    r = (
        conn.execute("MATCH ()-[r:ENTITY_RELATION]->() RETURN count(r) AS c")
        .get_as_df()
        .iloc[0]["c"]
    )
    logger.info(f"Build complete: {{successful}} successful, {{failed}} failed")
    logger.info(f"Final stats: {{a}} articles, {{e}} entities, {{r}} relationships")
    create_manifest(DB_PATH, MANIFEST_PATH, a, e, r)


def main():
    parser = argparse.ArgumentParser(description=f"Build {{PACK_NAME}} Knowledge Pack")
    parser.add_argument("--test-mode", action="store_true", help="Build 5-URL pack for testing")
    args = parser.parse_args()
    Path("logs").mkdir(exist_ok=True)
    try:
        build_pack(test_mode=args.test_mode)
    except KeyboardInterrupt:
        logger.info("Build interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Build failed: {{e}}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

    with open(script_path, "w") as f:
        f.write(content)
    script_path.chmod(0o755)
    logger.info(f"Generated build script: {script_path}")
    return script_path


def run_build_script(pack_name: str) -> dict:
    """Run the generated build script in test-mode."""
    pack_var = pack_name.replace("-", "_")
    script = PROJECT_ROOT / "scripts" / f"build_{pack_var}_pack.py"

    if not script.exists():
        raise FileNotFoundError(f"Build script not found: {script}")

    # Ensure logs directory exists
    (PROJECT_ROOT / "logs").mkdir(exist_ok=True)

    logger.info(f"Running build script: {script} --test-mode")
    result = subprocess.run(
        ["uv", "run", "python", str(script), "--test-mode"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=1200,  # 20 minutes max
    )

    if result.returncode != 0:
        logger.error(f"Build script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return {"success": False, "error": result.stderr[-500:] if result.stderr else "unknown"}

    logger.info("Build script completed successfully")
    return {"success": True}


def main():
    parser = argparse.ArgumentParser(
        description="Build a knowledge pack from a GitHub issue JSON payload"
    )
    parser.add_argument(
        "--issue-json",
        required=True,
        help="JSON string with pack_name, description, urls, search_terms, article_count_target",
    )
    args = parser.parse_args()

    try:
        issue = json.loads(args.issue_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    pack_name = issue.get("pack_name", "").strip()
    description = issue.get("description", "").strip()
    urls = issue.get("urls", [])
    search_terms = issue.get("search_terms", "").strip()
    article_count_target = int(issue.get("article_count_target", 20))

    # Validate
    try:
        pack_name = validate_pack_name(pack_name)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    if not description:
        print(json.dumps({"error": "Description is required"}))
        sys.exit(1)

    # Create pack directory
    pack_dir = PROJECT_ROOT / "data" / "packs" / pack_name
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "eval").mkdir(exist_ok=True)

    # Resolve URLs
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.splitlines() if u.strip().startswith("http")]

    if not urls and search_terms:
        logger.info(f"No seed URLs provided. Discovering from search terms: {search_terms}")
        urls = discover_urls_from_search(search_terms, target_count=article_count_target)

    if not urls:
        print(json.dumps({"error": "No URLs provided and URL discovery returned no results"}))
        sys.exit(1)

    # Limit URLs to target count
    urls = urls[:article_count_target]
    logger.info(f"Using {len(urls)} URLs (target: {article_count_target})")

    # Step 1: Create urls.txt
    create_urls_file(pack_dir, urls, pack_name)

    # Step 2: Generate build script
    script_path = generate_build_script(pack_name, description)

    # Step 3: Run build script (test-mode: processes first 5 URLs)
    build_result = run_build_script(pack_name)

    # Step 4: Read manifest for stats
    manifest_path = pack_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

    result = {
        "pack_name": pack_name,
        "urls_count": len(urls),
        "article_count_target": article_count_target,
        "build_success": build_result.get("success", False),
        "build_error": build_result.get("error"),
        "graph_stats": manifest.get("graph_stats", {}),
        "script_path": str(script_path),
        "pack_dir": str(pack_dir),
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
