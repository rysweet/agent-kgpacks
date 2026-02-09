#!/usr/bin/env python3
"""
1,000-Article Expansion Test

Full-scale test of WikiGR system:
1. Initialize 100 diverse seeds
2. Expand to 1,000 articles automatically
3. Monitor progress
4. Test semantic search quality
5. Measure performance
"""

import sys

sys.path.insert(0, "bootstrap")

import json
import logging
import shutil
import time
from pathlib import Path

import numpy as np
from schema.ryugraph_schema import create_schema
from src.expansion import RyuGraphOrchestrator
from src.query import semantic_search

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/1k_expansion.log"), logging.StreamHandler()],
)

print("=" * 70)
print("WikiGR 1,000-Article Expansion Test")
print("=" * 70)

# Configuration
DB_PATH = "data/wikigr_1k.db"
SEEDS_FILE = "bootstrap/data/seeds_1k.json"
TARGET_COUNT = 1000

# Load seeds
print("\n1. Loading seeds...")
with open(SEEDS_FILE) as f:
    seed_data = json.load(f)

seeds = seed_data["seeds"]
print(f"   ✓ Loaded {len(seeds)} seeds from {len(set(s['category'] for s in seeds))} categories")

# Create fresh database
print("\n2. Creating database...")
Path("logs").mkdir(exist_ok=True)

if Path(DB_PATH).exists():
    if Path(DB_PATH).is_dir():
        shutil.rmtree(DB_PATH)
    else:
        Path(DB_PATH).unlink()

create_schema(DB_PATH)
print("   ✓ Database ready")

# Initialize orchestrator
print("\n3. Initializing orchestrator...")
orch = RyuGraphOrchestrator(
    db_path=DB_PATH,
    max_depth=2,
    batch_size=20,  # Larger batch for efficiency
)
print("   ✓ Orchestrator initialized")

# Initialize seeds
print(f"\n4. Initializing {len(seeds)} seeds...")
for seed in seeds:
    result = orch.conn.execute(
        """
        MATCH (a:Article {title: $title})
        RETURN COUNT(a) AS count
    """,
        {"title": seed["title"]},
    )

    if result.get_as_df().iloc[0]["count"] == 0:
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
            {"title": seed["title"], "category": seed["category"]},
        )

print(f"   ✓ {len(seeds)} seeds initialized")

# Expand to 1,000 articles
print(f"\n5. Expanding to {TARGET_COUNT} articles...")
print("   (This will take ~60-90 minutes)")
print("   Monitor progress: tail -f logs/1k_expansion.log")
print("-" * 70)

start_time = time.time()
stats = orch.expand_to_target(target_count=TARGET_COUNT, max_iterations=200)
duration = time.time() - start_time

# Results
print("\n" + "=" * 70)
print("EXPANSION COMPLETE")
print("=" * 70)
print(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)")
print(f"Iterations: {stats['iterations']}")

# Database statistics
result = orch.conn.execute("MATCH (a:Article) WHERE a.word_count > 0 RETURN COUNT(a) AS count")
loaded = result.get_as_df().iloc[0]["count"]

result = orch.conn.execute("MATCH (s:Section) RETURN COUNT(s) AS count")
sections = result.get_as_df().iloc[0]["count"]

result = orch.conn.execute("MATCH (a:Article) RETURN COUNT(a) AS count")
total = result.get_as_df().iloc[0]["count"]

print("\nDatabase Statistics:")
print(f"  Articles loaded: {loaded}")
print(f"  Total sections: {sections}")
print(f"  Avg sections/article: {sections/loaded if loaded > 0 else 0:.1f}")
print(f"  Total articles (all states): {total}")

# State distribution
result = orch.conn.execute("""
    MATCH (a:Article)
    RETURN a.expansion_state AS state, COUNT(a) AS count
    ORDER BY count DESC
""")

print("\n  State distribution:")
for _, row in result.get_as_df().iterrows():
    print(f"    {row['state']}: {row['count']}")

# Database size
if Path(DB_PATH).is_dir():
    db_size_mb = sum(f.stat().st_size for f in Path(DB_PATH).rglob("*") if f.is_file()) / (
        1024 * 1024
    )
else:
    db_size_mb = 0

print(f"\n  Database size: {db_size_mb:.1f} MB")

# Test semantic search
print("\n" + "=" * 70)
print("SEMANTIC SEARCH QUALITY TEST")
print("=" * 70)

test_queries = [
    ("Artificial intelligence", "Computer Science & AI"),
    ("Quantum mechanics", "Physics"),
    ("DNA", "Biology & Medicine"),
    ("Calculus", "Mathematics"),
    ("World War II", "History"),
]

query_latencies = []
precision_scores = []

for query_title, category in test_queries:
    if loaded < 100:
        print("\n⚠ Skipping queries (not enough articles loaded)")
        break

    print(f"\nQuery: '{query_title}'")

    start = time.time()
    results = semantic_search(orch.conn, query_title, top_k=10)
    latency = (time.time() - start) * 1000

    query_latencies.append(latency)

    print(f"  Latency: {latency:.1f} ms")
    print(f"  Results: {len(results)}")

    if results:
        print("  Top 3:")
        for r in results[:3]:
            print(f"    {r['rank']}. {r['article_title']}: {r['similarity']:.3f}")

# Performance summary
if query_latencies:
    print("\n" + "=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)
    print("\nQuery Latency:")
    print(f"  Average: {np.mean(query_latencies):.1f} ms")
    print(f"  P50: {np.percentile(query_latencies, 50):.1f} ms")
    print(f"  P95: {np.percentile(query_latencies, 95):.1f} ms")
    print(f"  Max: {np.max(query_latencies):.1f} ms")

    p95 = np.percentile(query_latencies, 95)
    if p95 < 500:
        print(f"\n  ✓ P95 latency {p95:.1f}ms < 500ms target")

# Success criteria
print("\n" + "=" * 70)
print("SUCCESS CRITERIA")
print("=" * 70)

criteria = {
    "Articles loaded": (loaded >= 800, f"{loaded}/1000 (target: ≥800)"),
    "Database size": (db_size_mb < 1000, f"{db_size_mb:.1f} MB (target: <1000 MB)"),
    "P95 latency": (
        np.percentile(query_latencies, 95) < 500 if query_latencies else False,
        f"{np.percentile(query_latencies, 95) if query_latencies else 0:.1f} ms (target: <500ms)",
    ),
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
    print("\n🚀 Ready for Phase 4: Scale to 30K articles")
else:
    print("⚠ Some criteria not met - review results")
print("=" * 70)

print("\nDetailed logs: logs/1k_expansion.log")
print(f"Database: {DB_PATH}")
