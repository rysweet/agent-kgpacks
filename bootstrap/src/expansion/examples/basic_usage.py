"""
Basic usage example for LinkDiscovery

Demonstrates how to use LinkDiscovery to expand a graph from seed articles
by discovering and inserting linked articles.
"""

import kuzu
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from expansion import LinkDiscovery


def main():
    """Demonstrate basic link discovery workflow"""

    print("=" * 60)
    print("Link Discovery Example")
    print("=" * 60)

    # Setup database
    db_path = "data/example_link_discovery.db"
    print(f"\nDatabase: {db_path}")

    # Clean up existing database
    import shutil
    db_path_obj = Path(db_path)
    if db_path_obj.exists():
        if db_path_obj.is_dir():
            shutil.rmtree(db_path)
        else:
            db_path_obj.unlink()

    # Initialize database with schema
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # Create schema
    print("\nCreating schema...")
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

    conn.execute("""
        CREATE REL TABLE LINKS_TO(
            FROM Article TO Article,
            link_type STRING
        )
    """)

    # Create LinkDiscovery instance
    discovery = LinkDiscovery(conn)

    # Insert seed article (simulating a loaded article)
    print("\nInserting seed article...")
    conn.execute("""
        CREATE (a:Article {
            title: 'Machine Learning',
            category: 'Computer Science',
            word_count: 8000,
            expansion_state: 'loaded',
            expansion_depth: 0,
            claimed_at: NULL,
            processed_at: timestamp('2026-02-08T00:00:00'),
            retry_count: 0
        })
    """)

    # Simulate links extracted from Wikipedia article
    # In real usage, these would come from WikipediaArticle.links
    links = [
        # Valid article links
        "Artificial Intelligence",
        "Deep Learning",
        "Neural Networks",
        "Data Science",
        "Statistics",

        # Invalid links (will be filtered)
        "Wikipedia:About",
        "Help:Editing",
        "List of machine learning frameworks",
        "Machine learning (disambiguation)",
        "File:Neural_network.png",
    ]

    print(f"\nDiscovering links from 'Machine Learning'...")
    print(f"Processing {len(links)} candidate links...")

    # Discover links (depth 0 -> depth 1)
    new_count = discovery.discover_links(
        source_title="Machine Learning",
        links=links,
        current_depth=0,
        max_depth=2  # Allow expansion to depth 2
    )

    print(f"✓ Discovered {new_count} new articles")

    # Check discovered articles
    print("\n" + "-" * 60)
    print("Discovered Articles:")
    print("-" * 60)

    result = conn.execute("""
        MATCH (a:Article)
        WHERE a.expansion_state = 'discovered'
        RETURN a.title AS title, a.expansion_depth AS depth
        ORDER BY a.title
    """)

    df = result.get_as_df()
    for idx, row in df.iterrows():
        print(f"  • {row['title']} (depth={row['depth']})")

    # Check link relationships
    print("\n" + "-" * 60)
    print("Link Relationships:")
    print("-" * 60)

    result = conn.execute("""
        MATCH (source:Article)-[r:LINKS_TO]->(target:Article)
        RETURN source.title AS source, target.title AS target
        ORDER BY target.title
    """)

    df = result.get_as_df()
    for idx, row in df.iterrows():
        print(f"  {row['source']} → {row['target']}")

    # Check discovery queue
    discovered_count = discovery.get_discovered_count()
    print(f"\n✓ Total articles waiting to be processed: {discovered_count}")

    # Demonstrate existing article handling
    print("\n" + "=" * 60)
    print("Testing Existing Article Handling")
    print("=" * 60)

    # Mark one article as loaded
    conn.execute("""
        MATCH (a:Article {title: 'Deep Learning'})
        SET a.expansion_state = 'loaded'
    """)

    # Try to discover links that include already-discovered articles
    links_from_ai = [
        "Deep Learning",  # Already exists (loaded)
        "Neural Networks",  # Already exists (discovered)
        "Computer Vision",  # New article
    ]

    print("\nDiscovering links from 'Artificial Intelligence'...")

    # First mark Artificial Intelligence as loaded
    conn.execute("""
        MATCH (a:Article {title: 'Artificial Intelligence'})
        SET a.expansion_state = 'loaded'
    """)

    new_count = discovery.discover_links(
        source_title="Artificial Intelligence",
        links=links_from_ai,
        current_depth=1,
        max_depth=2
    )

    print(f"✓ Discovered {new_count} new article(s)")
    print("  (Existing articles were linked but not re-discovered)")

    # Demonstrate depth limiting
    print("\n" + "=" * 60)
    print("Testing Depth Limiting")
    print("=" * 60)

    # Create article at max depth
    conn.execute("""
        CREATE (a:Article {
            title: 'Max Depth Article',
            category: NULL,
            word_count: 0,
            expansion_state: 'loaded',
            expansion_depth: 2,
            claimed_at: NULL,
            processed_at: timestamp('2026-02-08T00:00:00'),
            retry_count: 0
        })
    """)

    # Try to discover from it (should be blocked)
    new_count = discovery.discover_links(
        source_title="Max Depth Article",
        links=["Should Not Be Discovered"],
        current_depth=2,
        max_depth=2
    )

    print(f"✓ Articles discovered at max depth: {new_count} (expected: 0)")

    # Final statistics
    print("\n" + "=" * 60)
    print("Final Statistics")
    print("=" * 60)

    result = conn.execute("""
        MATCH (a:Article)
        RETURN a.expansion_state AS state, COUNT(a) AS count
        ORDER BY state
    """)

    df = result.get_as_df()
    print("\nArticles by state:")
    for idx, row in df.iterrows():
        print(f"  {row['state']:12s}: {row['count']}")

    result = conn.execute("""
        MATCH (a:Article)-[r:LINKS_TO]->(target:Article)
        RETURN COUNT(r) AS count
    """)

    total_links = result.get_as_df().iloc[0]['count']
    print(f"\nTotal relationships: {total_links}")

    print("\n✓ Example complete!")


if __name__ == "__main__":
    main()
