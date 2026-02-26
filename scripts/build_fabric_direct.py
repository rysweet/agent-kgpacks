#!/usr/bin/env python3
"""Build Fabric Graph GQL pack directly from URLs."""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import kuzu

from bootstrap.schema.ryugraph_schema import create_schema
from bootstrap.src.embeddings.generator import EmbeddingGenerator
from bootstrap.src.extraction.llm_extractor import get_extractor
from bootstrap.src.sources.web import WebContentSource
from bootstrap.src.wikipedia.parser import parse_sections

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PACK_DIR = Path("data/packs/fabric-graph-gql-expert")
URLS_FILE = PACK_DIR / "urls.txt"
DB_PATH = PACK_DIR / "pack.db"

# Load URLs (filter comments)
urls = []
with open(URLS_FILE) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)

print("Building Fabric Graph GQL Pack")
print(f"URLs: {len(urls)}")
print(f"Estimated time: {len(urls) * 2} minutes")
print()

# Create database
if DB_PATH.exists():
    import shutil

    shutil.rmtree(DB_PATH) if DB_PATH.is_dir() else DB_PATH.unlink()

create_schema(str(DB_PATH), drop_existing=True)
db = kuzu.Database(str(DB_PATH))
conn = kuzu.Connection(db)

# Initialize components
web_source = WebContentSource()
embedder = EmbeddingGenerator()
extractor = get_extractor()

# Process each URL
successful = 0
for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] {url[:80]}...")
    try:
        # Fetch content
        article = web_source.fetch_article(url)
        if not article or not article.content:
            print("  No content")
            continue

        sections = parse_sections(article.content)
        if not sections:
            print("  No sections")
            continue

        # Create article
        word_count = sum(len(s["content"].split()) for s in sections)
        conn.execute(
            "CREATE (a:Article {title: $title, category: $cat, word_count: $wc})",
            {"title": article.title, "cat": "Fabric", "wc": word_count},
        )

        # Extract knowledge with LLM
        extraction = extractor.extract_from_article(
            article.title, sections, max_sections=5, domain="science"
        )

        # Add entities
        for entity in extraction.entities:
            conn.execute(
                "MERGE (e:Entity {entity_id: $eid}) ON CREATE SET e.name = $name, e.type = $type",
                {"eid": entity.name, "name": entity.name, "type": entity.type},
            )
            conn.execute(
                "MATCH (a:Article {title: $title}), (e:Entity {entity_id: $eid}) MERGE (a)-[:HAS_ENTITY]->(e)",
                {"title": article.title, "eid": entity.name},
            )

        # Add relationships
        for rel in extraction.relationships:
            conn.execute(
                "MERGE (e:Entity {entity_id: $id}) ON CREATE SET e.name = $id, e.type = 'concept'",
                {"id": rel.source},
            )
            conn.execute(
                "MERGE (e:Entity {entity_id: $id}) ON CREATE SET e.name = $id, e.type = 'concept'",
                {"id": rel.target},
            )
            conn.execute(
                "MATCH (s:Entity {entity_id: $src}), (t:Entity {entity_id: $tgt}) MERGE (s)-[:ENTITY_RELATION {relation: $rel, context: $ctx}]->(t)",
                {"src": rel.source, "tgt": rel.target, "rel": rel.relation, "ctx": rel.context},
            )

        # Add sections with embeddings
        for idx, section in enumerate(sections[:3]):
            embedding = embedder.generate([section["content"]])[0].tolist()
            conn.execute(
                "MATCH (a:Article {title: $title}) CREATE (a)-[:HAS_SECTION]->(s:Section {section_id: $sid, content: $content, embedding: $emb})",
                {
                    "title": article.title,
                    "sid": f"{article.title}#{idx}",
                    "content": section["content"],
                    "emb": embedding,
                },
            )

        successful += 1
        print(
            f"  OK: {len(extraction.entities)} entities, {len(extraction.relationships)} relationships"
        )

    except Exception as e:
        print(f"  ERROR: {str(e)[:100]}")

# Get final stats
article_count = int(
    conn.execute("MATCH (a:Article) RETURN count(a) AS count").get_as_df().iloc[0]["count"]
)
entity_count = int(
    conn.execute("MATCH (e:Entity) RETURN count(e) AS count").get_as_df().iloc[0]["count"]
)
rel_count = int(
    conn.execute("MATCH ()-[r:ENTITY_RELATION]->() RETURN count(r) AS count")
    .get_as_df()
    .iloc[0]["count"]
)

print("\nBUILD COMPLETE")
print(f"Successful: {successful}/{len(urls)}")
print(f"Articles: {article_count}, Entities: {entity_count}, Relationships: {rel_count}")

# Create manifest
db_size = (
    sum(f.stat().st_size for f in DB_PATH.rglob("*") if f.is_file())
    if DB_PATH.is_dir()
    else DB_PATH.stat().st_size
)
manifest = {
    "name": "fabric-graph-gql-expert",
    "version": "1.0.0",
    "description": "Microsoft Fabric Graph GQL API expertise from Microsoft Learn",
    "graph_stats": {
        "articles": article_count,
        "entities": entity_count,
        "relationships": rel_count,
        "size_mb": round(db_size / 1024 / 1024, 2),
    },
    "source_urls": urls[:5],
    "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "license": "CC-BY-SA-4.0",
}

with open(PACK_DIR / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

print(f'\nManifest saved to {PACK_DIR / "manifest.json"}')
print("Fabric Graph GQL pack ready!")
