#!/usr/bin/env python3
"""Final validation test with 20 articles"""

import sys

sys.path.insert(0, "bootstrap")

import logging
import shutil
import time
from pathlib import Path

from schema.ryugraph_schema import create_schema
from src.expansion import RyuGraphOrchestrator
from src.query import semantic_search

logging.basicConfig(level=logging.WARNING)

print("=" * 70)
print("20-Article Orchestrator Validation")
print("=" * 70)

# Create fresh database
db_path = "data/test_20_final.db"
if Path(db_path).exists():
    if Path(db_path).is_dir():
        shutil.rmtree(db_path)
    else:
        Path(db_path).unlink()

print("\n1. Creating database...")
create_schema(db_path)
print("   ✓ Schema ready")

# Initialize orchestrator
print("\n2. Initializing orchestrator...")
orch = RyuGraphOrchestrator(db_path, max_depth=1, batch_size=5)
print("   ✓ Orchestrator ready")

# Initialize 3 seeds
print("\n3. Initializing 3 seeds...")
seeds = [
    ("Python (programming language)", "Computer Science"),
    ("Artificial intelligence", "Computer Science"),
    ("DNA", "Biology"),
]

for title, category in seeds:
    orch.conn.execute(
        """
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
    """,
        {"title": title, "category": category},
    )

print(f"   ✓ {len(seeds)} seeds initialized")

# Expand to 20 articles
print("\n4. Expanding to 20 articles...")
start = time.time()
stats = orch.expand_to_target(target_count=20, max_iterations=50)
duration = time.time() - start

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)
print(f"Duration: {duration:.1f}s ({duration/60:.1f} min)")
print(f"Iterations: {stats['iterations']}")

# Check actual content
result = orch.conn.execute("MATCH (a:Article) WHERE a.word_count > 0 RETURN COUNT(a) AS count")
loaded = result.get_as_df().iloc[0]["count"]

result = orch.conn.execute("MATCH (s:Section) RETURN COUNT(s) AS count")
sections = result.get_as_df().iloc[0]["count"]

result = orch.conn.execute("MATCH (a:Article) RETURN COUNT(a) AS count")
total = result.get_as_df().iloc[0]["count"]

print(f"\nArticles with content: {loaded}")
print(f"Total sections: {sections}")
print(f"Total articles (all states): {total}")
print(f"Avg sections/article: {sections/loaded if loaded > 0 else 0:.1f}")

# Test semantic search
print("\n" + "=" * 70)
print("SEMANTIC SEARCH")
print("=" * 70)

query_start = time.time()
results = semantic_search(orch.conn, "Artificial intelligence", top_k=5)
query_time = (time.time() - query_start) * 1000

print(f"\nQuery time: {query_time:.1f} ms")
print(f"Results: {len(results)}")

if results:
    print("\nTop 3:")
    for r in results[:3]:
        print(f"  {r['rank']}. {r['article_title']}: {r['similarity']:.3f}")

# Success
print("\n" + "=" * 70)
if loaded >= 18 and sections > 300:
    print("✓ TEST PASSED!")
    print(f"  Loaded: {loaded}/20")
    print(f"  Sections: {sections}")
    print(f"  Query: {query_time:.1f}ms")
else:
    print("⚠ Incomplete")
print("=" * 70)

# Cleanup
if Path(db_path).exists():
    if Path(db_path).is_dir():
        shutil.rmtree(db_path)
    else:
        Path(db_path).unlink()
