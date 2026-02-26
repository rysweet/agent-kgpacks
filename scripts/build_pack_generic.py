#!/usr/bin/env python3
"""Generic pack builder from URLs."""

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

logging.basicConfig(level=logging.WARNING)

pack_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/packs/test")
urls_file = pack_dir / "urls.txt"
db_path = pack_dir / "pack.db"

with open(urls_file) as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
print(f"Building {pack_dir.name}: {len(urls)} URLs")

if db_path.exists():
    import shutil

    (shutil.rmtree if db_path.is_dir() else lambda p: p.unlink())(db_path)

create_schema(str(db_path), drop_existing=True)
db, conn = kuzu.Database(str(db_path)), kuzu.Connection(kuzu.Database(str(db_path)))
web_source, embedder, extractor = WebContentSource(), EmbeddingGenerator(), get_extractor()

successful = 0
for i, url in enumerate(urls, 1):
    try:
        article = web_source.fetch_article(url)
        if not article or not article.content:
            continue
        sections = parse_sections(article.content)
        if not sections:
            continue

        conn.execute(
            "CREATE (a:Article {title: $t, category: $c, word_count: $w})",
            {
                "t": article.title,
                "c": pack_dir.name,
                "w": sum(len(s["content"].split()) for s in sections),
            },
        )

        extraction = extractor.extract_from_article(article.title, sections, 5, "science")

        for e in extraction.entities:
            conn.execute(
                "MERGE (e:Entity {entity_id: $id}) ON CREATE SET e.name=$n, e.type=$t",
                {"id": e.name, "n": e.name, "t": e.type},
            )
            conn.execute(
                "MATCH (a:Article {title:$t}), (e:Entity {entity_id:$id}) MERGE (a)-[:HAS_ENTITY]->(e)",
                {"t": article.title, "id": e.name},
            )

        for r in extraction.relationships:
            for eid in [r.source, r.target]:
                conn.execute(
                    "MERGE (e:Entity {entity_id: $id}) ON CREATE SET e.name=$id, e.type='concept'",
                    {"id": eid},
                )
            conn.execute(
                "MATCH (s:Entity {entity_id:$s}), (t:Entity {entity_id:$t}) "
                "MERGE (s)-[:ENTITY_RELATION {relation:$r, context:$c}]->(t)",
                {"s": r.source, "t": r.target, "r": r.relation, "c": r.context},
            )

        for idx, sec in enumerate(sections[:3]):
            emb = embedder.generate([sec["content"]])[0].tolist()
            conn.execute(
                "MATCH (a:Article {title:$t}) CREATE (a)-[:HAS_SECTION]->(s:Section {section_id:$id, content:$c, embedding:$e})",
                {"t": article.title, "id": f"{article.title}#{idx}", "c": sec["content"], "e": emb},
            )

        successful += 1
        print(
            f"  [{i}/{len(urls)}] {article.title[:60]} - {len(extraction.entities)}E {len(extraction.relationships)}R"
        )
    except Exception as e:
        print(f"  [{i}/{len(urls)}] ERROR: {str(e)[:80]}")

stats = {
    t: int(conn.execute(f"MATCH (n:{t}) RETURN count(n) AS c").get_as_df().iloc[0]["c"])
    for t in ["Article", "Entity", "Section"]
}
stats["Relationships"] = int(
    conn.execute("MATCH ()-[r:ENTITY_RELATION]->() RETURN count(r) AS c").get_as_df().iloc[0]["c"]
)

print(f"\n=== {pack_dir.name.upper()} COMPLETE ===")
print(
    f'Success: {successful}/{len(urls)} | Articles: {stats["Article"]} | Entities: {stats["Entity"]} | Relationships: {stats["Relationships"]}'
)

# Fail if no articles were successfully processed
if stats["Article"] == 0:
    print("\n❌ ERROR: Pack build completed with 0 articles. Check URLs and network connectivity.")
    sys.exit(1)

db_size = (
    (
        sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())
        if db_path.is_dir()
        else db_path.stat().st_size
    )
    / 1024
    / 1024
)
manifest = {
    "name": pack_dir.name,
    "version": "1.0.0",
    "description": f'{pack_dir.name.replace("-"," ").title()} knowledge from Microsoft Learn',
    "graph_stats": {
        "articles": stats["Article"],
        "entities": stats["Entity"],
        "relationships": stats["Relationships"],
        "size_mb": round(db_size, 2),
    },
    "source_urls": urls[:5],
    "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "license": "CC-BY-SA-4.0",
}
with open(pack_dir / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"✓ Pack ready: {db_path}")
