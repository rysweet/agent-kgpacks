#!/usr/bin/env python3
"""Test the expansion orchestrator"""

import sys

sys.path.insert(0, "bootstrap")

import logging
import shutil
from pathlib import Path

from schema.ryugraph_schema import create_schema
from src.expansion import RyuGraphOrchestrator

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

print("=" * 70)
print("Expansion Orchestrator Test")
print("=" * 70)

# Create fresh database
db_path = "data/test_orchestrator.db"
print(f"\nDatabase: {db_path}")

if Path(db_path).exists():
    if Path(db_path).is_dir():
        shutil.rmtree(db_path)
    else:
        Path(db_path).unlink()

# Create schema
print("\nCreating schema...")
create_schema(db_path)
print("✓ Schema ready")

# Initialize orchestrator
print("\nInitializing orchestrator...")
orch = RyuGraphOrchestrator(db_path=db_path, max_depth=2, batch_size=5)
print("✓ Orchestrator initialized")

# Test 1: Initialize seeds
print("\n" + "=" * 70)
print("TEST 1: Initialize Seeds")
print("=" * 70)

seeds = ["Python (programming language)", "Artificial intelligence", "Machine learning"]

session_id = orch.initialize_seeds(seeds, category="Computer Science")
print(f"✓ Initialized {len(seeds)} seeds (session: {session_id})")

# Test 2: Expand to 15 articles
print("\n" + "=" * 70)
print("TEST 2: Expand to 15 Articles")
print("=" * 70)

stats = orch.expand_to_target(target_count=15, max_iterations=30)

print("\n" + "=" * 70)
print("EXPANSION RESULTS")
print("=" * 70)
print(f"Iterations: {stats['iterations']}")
print(f"Duration: {stats['duration_seconds']:.1f}s")
print(f"Loaded: {stats.get('loaded', 0)}")
print(f"Processed: {stats.get('processed', 0)}")
print(f"Failed: {stats.get('failed', 0)}")
print(f"Discovered (queued): {stats.get('discovered', 0)}")
print(f"Claimed (active): {stats.get('claimed', 0)}")

total_loaded = stats.get("loaded", 0) + stats.get("processed", 0)
print(f"\nTotal loaded: {total_loaded}")

if total_loaded >= 15:
    print("✓ Target reached!")
else:
    print(f"⚠ Target not reached: {total_loaded}/15")

# Check database
print("\n" + "=" * 70)
print("DATABASE STATISTICS")
print("=" * 70)

result = orch.conn.execute("""
    MATCH (a:Article)
    RETURN COUNT(a) AS total_articles
""")
total = result.get_as_df().iloc[0]["total_articles"]

result = orch.conn.execute("""
    MATCH (s:Section)
    RETURN COUNT(s) AS total_sections
""")
sections = result.get_as_df().iloc[0]["total_sections"]

print(f"Total articles: {total}")
print(f"Total sections: {sections}")
print(f"Avg sections/article: {sections/total if total > 0 else 0:.1f}")

# Show articles by state
result = orch.conn.execute("""
    MATCH (a:Article)
    RETURN a.expansion_state AS state,
           a.expansion_depth AS depth,
           COUNT(a) AS count
    ORDER BY depth ASC, state ASC
""")

print("\nArticles by state and depth:")
for idx, row in result.get_as_df().iterrows():
    print(f"  Depth {row['depth']}, {row['state']}: {row['count']} articles")

# Cleanup
print("\n" + "=" * 70)
if Path(db_path).exists():
    if Path(db_path).is_dir():
        shutil.rmtree(db_path)
    else:
        Path(db_path).unlink()
    print("✓ Test database cleaned up")

print("\n✓ Orchestrator test complete!")
