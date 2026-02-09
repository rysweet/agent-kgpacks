#!/usr/bin/env python3
"""
WikiGR Quickstart Script

Validates the complete pipeline with 3 sample articles:
1. Fetch from Wikipedia
2. Parse sections
3. Generate embeddings
4. Load into Kuzu
5. Create vector index
6. Run semantic search query

Usage:
    python quickstart.py
"""

import os
import shutil
import sys

print("=" * 60)
print("WikiGR Quickstart Validation")
print("=" * 60)

# Step 1: Check dependencies
print("\n1. Checking dependencies...")

missing_deps = []
required_packages = {
    "kuzu": "kuzu",
    "sentence_transformers": "sentence-transformers",
    "requests": "requests",
    "pandas": "pandas",
    "numpy": "numpy",
}

for module, package in required_packages.items():
    try:
        __import__(module)
        print(f"   ✅ {package}")
    except ImportError:
        print(f"   ❌ {package} - NOT INSTALLED")
        missing_deps.append(package)

if missing_deps:
    print(f"\n❌ Missing dependencies: {', '.join(missing_deps)}")
    print("\nInstall with:")
    print(f"   pip install {' '.join(missing_deps)}")
    sys.exit(1)

print("   ✅ All dependencies installed")

# Import after validation
import re

import kuzu
import requests
from sentence_transformers import SentenceTransformer

# Step 2: Create test database
print("\n2. Creating test database...")

db_path = "/tmp/wikigr_quickstart"
if os.path.exists(db_path):
    shutil.rmtree(db_path)

try:
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    print(f"   ✅ Database created: {db_path}")
except Exception as e:
    print(f"   ❌ Database creation failed: {e}")
    sys.exit(1)

# Step 3: Create schema
print("\n3. Creating schema...")

try:
    # Article node
    conn.execute("""
        CREATE NODE TABLE Article(
            title STRING,
            category STRING,
            word_count INT32,
            PRIMARY KEY(title)
        )
    """)
    print("   ✅ Article table created")

    # Section node
    conn.execute("""
        CREATE NODE TABLE Section(
            section_id STRING,
            title STRING,
            content STRING,
            embedding DOUBLE[384],
            level INT32,
            PRIMARY KEY(section_id)
        )
    """)
    print("   ✅ Section table created")

    # HAS_SECTION relationship
    conn.execute("""
        CREATE REL TABLE HAS_SECTION(
            FROM Article TO Section,
            section_index INT32
        )
    """)
    print("   ✅ HAS_SECTION relationship created")

except Exception as e:
    print(f"   ❌ Schema creation failed: {e}")
    sys.exit(1)

# Step 4: Fetch sample articles from Wikipedia
print("\n4. Fetching sample articles from Wikipedia...")

USER_AGENT = "WikiGR-Quickstart/1.0 (Educational Project)"
SAMPLE_ARTICLES = ["Machine_Learning", "Quantum_Computing", "Deep_Learning"]


def fetch_article(title: str) -> dict:
    """Fetch article from Wikipedia Action API"""
    params = {"action": "parse", "page": title, "prop": "wikitext|links", "format": "json"}

    response = requests.get(
        "https://en.wikipedia.org/w/api.php", params=params, headers={"User-Agent": USER_AGENT}
    )

    data = response.json()

    if "parse" not in data:
        raise ValueError(f"Article not found: {title}")

    return {
        "title": data["parse"]["title"],
        "wikitext": data["parse"]["wikitext"]["*"],
        "links": [link["*"] for link in data["parse"].get("links", [])],
    }


articles_data = []
for title in SAMPLE_ARTICLES:
    try:
        article = fetch_article(title)
        articles_data.append(article)
        print(f"   ✅ Fetched: {article['title']} ({len(article['wikitext'])} chars)")
    except Exception as e:
        print(f"   ❌ Failed to fetch {title}: {e}")
        sys.exit(1)

# Step 5: Parse sections
print("\n5. Parsing sections...")


def parse_sections(wikitext: str) -> list[dict]:
    """Extract H2 and H3 sections from wikitext"""
    sections = []

    # Match == Heading 2 == and === Heading 3 ===
    pattern = r"^(={2,3})\s*(.+?)\s*\1$"

    matches = list(re.finditer(pattern, wikitext, re.MULTILINE))

    for i, match in enumerate(matches):
        level = len(match.group(1))  # 2 or 3
        title = match.group(2).strip()

        # Extract content (text between this heading and next)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
        content = wikitext[start:end].strip()

        # Filter out short sections
        if len(content) > 100:
            sections.append(
                {
                    "level": level,
                    "title": title,
                    "content": content[:1000],  # Limit to 1000 chars for demo
                }
            )

    return sections


parsed_articles = []
for article in articles_data:
    sections = parse_sections(article["wikitext"])
    parsed_articles.append(
        {
            "title": article["title"],
            "sections": sections,
            "word_count": len(article["wikitext"].split()),
        }
    )
    print(f"   ✅ Parsed: {article['title']} ({len(sections)} sections)")

# Step 6: Generate embeddings
print("\n6. Generating embeddings...")

try:
    print("   Loading model: paraphrase-MiniLM-L3-v2...")
    model = SentenceTransformer("paraphrase-MiniLM-L3-v2")
    print("   ✅ Model loaded")

    for article in parsed_articles:
        texts = [s["content"] for s in article["sections"]]

        if not texts:
            print(f"   ⚠️  No sections for {article['title']}, skipping")
            continue

        embeddings = model.encode(texts, show_progress_bar=False)
        article["embeddings"] = embeddings
        print(f"   ✅ Generated embeddings for {article['title']}: {embeddings.shape}")

except Exception as e:
    print(f"   ❌ Embedding generation failed: {e}")
    sys.exit(1)

# Step 7: Load into database
print("\n7. Loading articles into database...")

try:
    for article in parsed_articles:
        # Insert Article node
        conn.execute(
            """
            CREATE (a:Article {
                title: $title,
                category: 'Computer Science',
                word_count: $word_count
            })
        """,
            {"title": article["title"], "word_count": article["word_count"]},
        )

        # Insert Section nodes and relationships
        for i, section in enumerate(article["sections"]):
            if "embeddings" not in article:
                continue

            section_id = f"{article['title']}#{i}"
            embedding = article["embeddings"][i].tolist()

            conn.execute(
                """
                CREATE (s:Section {
                    section_id: $section_id,
                    title: $title,
                    content: $content,
                    embedding: $embedding,
                    level: $level
                })
            """,
                {
                    "section_id": section_id,
                    "title": section["title"],
                    "content": section["content"],
                    "embedding": embedding,
                    "level": section["level"],
                },
            )

            # Create HAS_SECTION relationship
            conn.execute(
                """
                MATCH (a:Article {title: $article_title}),
                      (s:Section {section_id: $section_id})
                CREATE (a)-[:HAS_SECTION {section_index: $index}]->(s)
            """,
                {"article_title": article["title"], "section_id": section_id, "index": i},
            )

        print(f"   ✅ Loaded: {article['title']}")

except Exception as e:
    print(f"   ❌ Database loading failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Step 8: Create vector index
print("\n8. Creating vector index...")

try:
    conn.execute("""
        CALL CREATE_VECTOR_INDEX(
            'Section',
            'embedding_idx',
            'embedding',
            metric := 'cosine'
        )
    """)
    print("   ✅ Vector index created")
except Exception as e:
    print(f"   ❌ Vector index creation failed: {e}")
    sys.exit(1)

# Step 9: Run semantic search query
print("\n9. Running semantic search query...")

try:
    # Get embedding for "Machine Learning"
    result = conn.execute("""
        MATCH (a:Article {title: 'Machine Learning'})-[:HAS_SECTION]->(s:Section)
        RETURN s.embedding AS embedding
        LIMIT 1
    """)

    query_embedding = result.get_next()["embedding"]

    # Search for similar sections
    result = conn.execute(
        """
        CALL QUERY_VECTOR_INDEX(
            'Section',
            'embedding_idx',
            $query,
            10
        ) RETURN *
    """,
        {"query": query_embedding},
    )

    results_df = result.get_as_df()

    print(f"   ✅ Found {len(results_df)} similar sections")
    print("\n   Top 3 results:")

    for i, row in results_df.head(3).iterrows():
        node = row["node"]
        distance = row["distance"]

        # Extract section info
        section_id = node["_properties"]["section_id"]
        section_title = node["_properties"]["title"]
        article_title = section_id.split("#")[0]

        print(f"      {i + 1}. {article_title} > {section_title}")
        print(f"         Distance: {distance:.4f}")

except Exception as e:
    print(f"   ❌ Semantic search failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# Step 10: Cleanup
print("\n10. Cleanup...")

try:
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
    print("   ✅ Test database removed")
except Exception as e:
    print(f"   ⚠️  Cleanup warning: {e}")

# Summary
print("\n" + "=" * 60)
print("QUICKSTART VALIDATION COMPLETE ✅")
print("=" * 60)
print("\nAll systems validated:")
print("  ✅ Dependencies installed")
print("  ✅ Database creation working")
print("  ✅ Schema creation working")
print("  ✅ Wikipedia API access working")
print("  ✅ Section parsing working")
print("  ✅ Embedding generation working")
print("  ✅ Database loading working")
print("  ✅ Vector index creation working")
print("  ✅ Semantic search working")

print("\n🚀 Ready to proceed with Phase 3: Implementation!")

print("\nNext steps:")
print("  1. Review bootstrap/docs/implementation-roadmap.md")
print("  2. Start with Issue #2: Set up project structure")
print("  3. Follow the 6-week implementation plan")
