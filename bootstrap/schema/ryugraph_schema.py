#!/usr/bin/env python3
"""
WikiGR Database Schema

Creates the complete Kuzu schema for Wikipedia knowledge graph:
- Article nodes
- Section nodes
- Category nodes
- Relationships (HAS_SECTION, LINKS_TO, IN_CATEGORY)
- Vector index on Section embeddings

Usage:
    python bootstrap/schema/ryugraph_schema.py --db data/wikigr.db
"""

import argparse
import sys
from pathlib import Path

import kuzu


def create_schema(db_path: str, drop_existing: bool = False):
    """
    Create complete Kuzu schema for WikiGR

    Args:
        db_path: Path to Kuzu database
        drop_existing: If True, drop existing tables first
    """
    print("=" * 60)
    print("WikiGR Schema Creation")
    print("=" * 60)

    # Create database
    print(f"\nDatabase path: {db_path}")

    if drop_existing and Path(db_path).exists():
        print("⚠️  Dropping existing database...")
        import shutil

        db_path_obj = Path(db_path)
        if db_path_obj.is_dir():
            shutil.rmtree(db_path)
        else:
            db_path_obj.unlink()

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    print("✅ Database connection established")

    # Drop existing tables if they exist (for re-creation)
    if not drop_existing:
        try:
            print("\nDropping existing tables (if any)...")
            conn.execute("DROP TABLE IF EXISTS HAS_CHUNK")
            conn.execute("DROP TABLE IF EXISTS HAS_SECTION")
            conn.execute("DROP TABLE IF EXISTS LINKS_TO")
            conn.execute("DROP TABLE IF EXISTS IN_CATEGORY")
            conn.execute("DROP TABLE IF EXISTS Chunk")
            conn.execute("DROP TABLE IF EXISTS Section")
            conn.execute("DROP TABLE IF EXISTS Article")
            conn.execute("DROP TABLE IF EXISTS Category")
            print("✅ Existing tables dropped")
        except Exception as e:
            print(f"⚠️  No existing tables to drop: {e}")

    # Create Article node table
    print("\n1. Creating Article node table...")
    try:
        conn.execute("""
            CREATE NODE TABLE Article(
                title STRING,
                category STRING,
                word_count INT32,
                expansion_state STRING,
                expansion_depth INT32,
                claimed_at TIMESTAMP,
                processed_at TIMESTAMP,
                retry_count INT32,
                PRIMARY KEY(title)
            )
        """)
        print("   ✅ Article table created")
    except Exception as e:
        print(f"   ❌ Failed to create Article table: {e}")
        sys.exit(1)

    # Create Section node table
    print("\n2. Creating Section node table...")
    try:
        conn.execute("""
            CREATE NODE TABLE Section(
                section_id STRING,
                title STRING,
                content STRING,
                embedding DOUBLE[384],
                level INT32,
                word_count INT32,
                PRIMARY KEY(section_id)
            )
        """)
        print("   ✅ Section table created")
    except Exception as e:
        print(f"   ❌ Failed to create Section table: {e}")
        sys.exit(1)

    # Create Category node table
    print("\n3. Creating Category node table...")
    try:
        conn.execute("""
            CREATE NODE TABLE Category(
                name STRING,
                article_count INT32,
                PRIMARY KEY(name)
            )
        """)
        print("   ✅ Category table created")
    except Exception as e:
        print(f"   ❌ Failed to create Category table: {e}")
        sys.exit(1)

    # Create HAS_SECTION relationship
    print("\n4. Creating HAS_SECTION relationship...")
    try:
        conn.execute("""
            CREATE REL TABLE HAS_SECTION(
                FROM Article TO Section,
                section_index INT32
            )
        """)
        print("   ✅ HAS_SECTION relationship created")
    except Exception as e:
        print(f"   ❌ Failed to create HAS_SECTION relationship: {e}")
        sys.exit(1)

    # Create LINKS_TO relationship
    print("\n5. Creating LINKS_TO relationship...")
    try:
        conn.execute("""
            CREATE REL TABLE LINKS_TO(
                FROM Article TO Article,
                link_type STRING
            )
        """)
        print("   ✅ LINKS_TO relationship created")
    except Exception as e:
        print(f"   ❌ Failed to create LINKS_TO relationship: {e}")
        sys.exit(1)

    # Create IN_CATEGORY relationship
    print("\n6. Creating IN_CATEGORY relationship...")
    try:
        conn.execute("""
            CREATE REL TABLE IN_CATEGORY(
                FROM Article TO Category
            )
        """)
        print("   ✅ IN_CATEGORY relationship created")
    except Exception as e:
        print(f"   ❌ Failed to create IN_CATEGORY relationship: {e}")
        sys.exit(1)

    # Create Chunk node table (for fine-grained text retrieval)
    print("\n6b. Creating Chunk node table...")
    try:
        conn.execute("""
            CREATE NODE TABLE Chunk(
                chunk_id STRING,
                content STRING,
                embedding DOUBLE[384],
                article_title STRING,
                section_index INT32,
                chunk_index INT32,
                PRIMARY KEY(chunk_id)
            )
        """)
        print("   ✅ Chunk table created")
    except Exception as e:
        print(f"   ❌ Failed to create Chunk table: {e}")
        sys.exit(1)

    # Create HAS_CHUNK relationship
    print("\n6c. Creating HAS_CHUNK relationship...")
    try:
        conn.execute("""
            CREATE REL TABLE HAS_CHUNK(
                FROM Article TO Chunk,
                section_index INT32,
                chunk_index INT32
            )
        """)
        print("   ✅ HAS_CHUNK relationship created")
    except Exception as e:
        print(f"   ❌ Failed to create HAS_CHUNK relationship: {e}")
        sys.exit(1)

    # Create vector index
    print("\n7. Creating HNSW vector index on Section.embedding...")
    try:
        conn.execute("""
            CALL CREATE_VECTOR_INDEX(
                'Section',
                'embedding_idx',
                'embedding',
                metric := 'cosine'
            )
        """)
        print("   ✅ Vector index created (HNSW, cosine metric)")
    except Exception as e:
        print(f"   ❌ Failed to create vector index: {e}")
        sys.exit(1)

    # Create chunk vector index
    print("\n7b. Creating HNSW vector index on Chunk.embedding...")
    try:
        conn.execute("""
            CALL CREATE_VECTOR_INDEX(
                'Chunk',
                'chunk_embedding_idx',
                'embedding',
                metric := 'cosine'
            )
        """)
        print("   ✅ Chunk vector index created (HNSW, cosine metric)")
    except Exception as e:
        print(f"   ❌ Failed to create chunk vector index: {e}")
        sys.exit(1)

    # Verify schema
    print("\n8. Verifying schema...")
    try:
        result = conn.execute("CALL SHOW_TABLES() RETURN *")
        tables = result.get_as_df()
        print("\n   Tables created:")
        for _idx, row in tables.iterrows():
            print(f"      - {row['name']}")

        expected_tables = {
            "Article",
            "Section",
            "Category",
            "Chunk",
            "HAS_SECTION",
            "LINKS_TO",
            "IN_CATEGORY",
            "HAS_CHUNK",
        }
        actual_tables = set(tables["name"].tolist())

        if expected_tables.issubset(actual_tables):
            print("\n   ✅ All tables created successfully")
        else:
            missing = expected_tables - actual_tables
            print(f"\n   ❌ Missing tables: {missing}")
            sys.exit(1)

    except Exception as e:
        print(f"   ❌ Schema verification failed: {e}")
        sys.exit(1)

    # Test basic operations
    print("\n9. Testing basic operations...")
    try:
        # Insert test article
        conn.execute("""
            CREATE (a:Article {
                title: 'Test Article',
                category: 'Test',
                word_count: 1000,
                expansion_state: 'loaded',
                expansion_depth: 0,
                claimed_at: NULL,
                processed_at: NULL,
                retry_count: 0
            })
        """)

        # Insert test section
        test_embedding = [0.1] * 384
        conn.execute(
            """
            CREATE (s:Section {
                section_id: 'Test Article#0',
                title: 'Introduction',
                content: 'Test content',
                embedding: $embedding,
                level: 2,
                word_count: 10
            })
        """,
            {"embedding": test_embedding},
        )

        # Create relationship
        conn.execute("""
            MATCH (a:Article {title: 'Test Article'}),
                  (s:Section {section_id: 'Test Article#0'})
            CREATE (a)-[:HAS_SECTION {section_index: 0}]->(s)
        """)

        # Query test
        result = conn.execute("""
            MATCH (a:Article {title: 'Test Article'})-[:HAS_SECTION]->(s:Section)
            RETURN a.title AS article_title, s.title AS section_title, s.level AS level
        """)

        df = result.get_as_df()
        assert len(df) == 1
        assert df.iloc[0]["article_title"] == "Test Article"
        assert df.iloc[0]["section_title"] == "Introduction"
        assert df.iloc[0]["level"] == 2

        # Clean up test data
        conn.execute("MATCH (a:Article {title: 'Test Article'}) DETACH DELETE a")
        conn.execute("MATCH (s:Section {section_id: 'Test Article#0'}) DELETE s")

        print("   ✅ Basic operations working")

    except Exception as e:
        print(f"   ❌ Basic operations failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("SCHEMA CREATION COMPLETE ✅")
    print("=" * 60)
    print("\nCreated:")
    print("  ✅ 4 node tables (Article, Section, Category, Chunk)")
    print("  ✅ 4 relationship tables (HAS_SECTION, LINKS_TO, IN_CATEGORY, HAS_CHUNK)")
    print("  ✅ 2 vector indices (Section.embedding, Chunk.embedding)")
    print("\nDatabase ready for data loading!")
    print(f"Location: {db_path}")


def main():
    parser = argparse.ArgumentParser(description="Create WikiGR database schema")
    parser.add_argument(
        "--db", default="data/wikigr.db", help="Path to Kuzu database (default: data/wikigr.db)"
    )
    parser.add_argument(
        "--drop", action="store_true", help="Drop existing database before creating schema"
    )

    args = parser.parse_args()

    # Create schema
    create_schema(args.db, drop_existing=args.drop)


if __name__ == "__main__":
    main()
