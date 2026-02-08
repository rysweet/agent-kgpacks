#!/usr/bin/env python3
"""
100-Article Expansion Test

Validates complete orchestrator with automatic expansion:
1. Initialize 10 seed articles
2. Expand to 100 articles automatically
3. Measure performance
4. Test semantic search
5. Document results
"""

import sys
sys.path.insert(0, 'bootstrap')

import logging
from pathlib import Path
import shutil
import time
import numpy as np

from src.expansion import RyuGraphOrchestrator
from src.query import semantic_search
from schema.ryugraph_schema import create_schema

# Set up logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/100_article_test.log'),
        logging.StreamHandler()
    ]
)

print("=" * 70)
print("WikiGR 100-Article Expansion Test")
print("=" * 70)

# Configuration
DB_PATH = "data/test_100_articles.db"

# 10 diverse seeds across multiple categories
SEED_ARTICLES = [
    ("Artificial intelligence", "Computer Science"),
    ("Python (programming language)", "Computer Science"),
    ("Quantum mechanics", "Physics"),
    ("DNA", "Biology"),
    ("Evolution", "Biology"),
    ("World War II", "History"),
    ("Democracy", "Political Science"),
    ("Philosophy", "Philosophy"),
    ("General relativity", "Physics"),
    ("Neural network (machine learning)", "Computer Science"),
]

# Create fresh database
print("\n1. Creating fresh database...")
Path("logs").mkdir(exist_ok=True)

if Path(DB_PATH).exists():
    if Path(DB_PATH).is_dir():
        shutil.rmtree(DB_PATH)
    else:
        Path(DB_PATH).unlink()

print("   Creating schema...")
create_schema(DB_PATH)
print("   ✓ Database ready")

# Initialize orchestrator
print("\n2. Initializing orchestrator...")
orch = RyuGraphOrchestrator(
    db_path=DB_PATH,
    max_depth=2,
    batch_size=10
)
print("   ✓ Orchestrator initialized")

# Initialize seeds
print(f"\n3. Initializing {len(SEED_ARTICLES)} seeds...")
seed_titles = [title for title, _ in SEED_ARTICLES]

# Insert seeds individually with categories
for title, category in SEED_ARTICLES:
    result = orch.conn.execute("""
        MATCH (a:Article {title: $title})
        RETURN COUNT(a) AS count
    """, {"title": title})

    if result.get_as_df().iloc[0]['count'] == 0:
        orch.conn.execute("""
            CREATE (a:Article {
                title: $title,
                category: $category,
                word_count: 0,
                expansion_state: 'discovered',
                expansion_depth: 0,
                claimed_at: NULL,
                processed_at: NULL,
                retry_count: 0
            })
        """, {"title": title, "category": category})
        print(f"   ✓ {title}")

print(f"   ✓ {len(SEED_ARTICLES)} seeds initialized")

# Expand to 100 articles
print(f"\n4. Expanding to 100 articles...")
print("   (This may take 5-10 minutes)")
print("-" * 70)

start_time = time.time()
stats = orch.expand_to_target(target_count=100, max_iterations=100)
duration = time.time() - start_time

print("\n" + "=" * 70)
print("EXPANSION COMPLETE")
print("=" * 70)
print(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
print(f"Iterations: {stats['iterations']}")
print(f"Articles loaded: {stats.get('loaded', 0) + stats.get('processed', 0)}")
print(f"Articles failed: {stats.get('failed', 0)}")
print(f"Articles queued: {stats.get('discovered', 0)}")

# Database statistics
print("\n" + "=" * 70)
print("DATABASE STATISTICS")
print("=" * 70)

result = orch.conn.execute("""
    MATCH (a:Article)
    RETURN COUNT(a) AS total
""")
total_articles = result.get_as_df().iloc[0]['total']

result = orch.conn.execute("""
    MATCH (s:Section)
    RETURN COUNT(s) AS total
""")
total_sections = result.get_as_df().iloc[0]['total']

print(f"Total articles: {total_articles}")
print(f"Total sections: {total_sections}")
print(f"Avg sections/article: {total_sections / total_articles if total_articles > 0 else 0:.1f}")

# State distribution
result = orch.conn.execute("""
    MATCH (a:Article)
    RETURN a.expansion_state AS state, COUNT(a) AS count
    ORDER BY count DESC
""")

print("\nState distribution:")
for idx, row in result.get_as_df().iterrows():
    print(f"  {row['state']}: {row['count']} articles")

# Depth distribution
result = orch.conn.execute("""
    MATCH (a:Article)
    WHERE a.expansion_state IN ['loaded', 'processed']
    RETURN a.expansion_depth AS depth, COUNT(a) AS count
    ORDER BY depth ASC
""")

print("\nDepth distribution (loaded articles):")
for idx, row in result.get_as_df().iterrows():
    print(f"  Depth {row['depth']}: {row['count']} articles")

# Database size
if Path(DB_PATH).is_dir():
    db_size_mb = sum(f.stat().st_size for f in Path(DB_PATH).rglob('*') if f.is_file()) / (1024 * 1024)
else:
    db_size_mb = 0

print(f"\nDatabase size: {db_size_mb:.1f} MB")

# Test semantic search
print("\n" + "=" * 70)
print("SEMANTIC SEARCH TEST")
print("=" * 70)

test_query = "Artificial intelligence"
print(f"\nQuery: '{test_query}'")

start = time.time()
results = semantic_search(orch.conn, test_query, top_k=10)
query_time = (time.time() - start) * 1000

print(f"Query time: {query_time:.1f} ms")
print(f"Results: {len(results)}")

if results:
    print("\nTop 5 results:")
    for result in results[:5]:
        print(f"  {result['rank']}. {result['article_title']}")
        print(f"     Similarity: {result['similarity']:.4f}")

# Success criteria
print("\n" + "=" * 70)
print("SUCCESS CRITERIA")
print("=" * 70)

loaded_count = stats.get('loaded', 0) + stats.get('processed', 0)
success_rate = loaded_count / total_articles * 100 if total_articles > 0 else 0

criteria = {
    "Articles loaded": (loaded_count >= 80, f"{loaded_count} (target: ≥80)"),
    "Success rate": (success_rate >= 80, f"{success_rate:.1f}% (target: ≥80%)"),
    "Database size": (db_size_mb < 500, f"{db_size_mb:.1f} MB (target: <500 MB)"),
    "Query latency": (query_time < 500, f"{query_time:.1f} ms (target: <500ms)"),
}

all_pass = True
for criterion, (passed, value) in criteria.items():
    status = "✓" if passed else "✗"
    print(f"  {status} {criterion}: {value}")
    if not passed:
        all_pass = False

print("\n" + "=" * 70)
if all_pass:
    print("✓ ALL SUCCESS CRITERIA MET!")
    print("\n🚀 Ready for Phase 4: Scale to 1K articles")
else:
    print("⚠ Some criteria not met - review and adjust")
print("=" * 70)

print(f"\nTest results logged to: logs/100_article_test.log")
print(f"Database saved at: {DB_PATH}")
