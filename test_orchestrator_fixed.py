#!/usr/bin/env python3
"""Quick test of orchestrator with fix"""

import sys
sys.path.insert(0, 'bootstrap')

import logging
from pathlib import Path
import shutil

from src.expansion import RyuGraphOrchestrator
from src.query import semantic_search
from schema.ryugraph_schema import create_schema

logging.basicConfig(level=logging.WARNING)

print("=" * 70)
print("Orchestrator Fix Validation (20 Articles)")
print("=" * 70)

# Create fresh database
db_path = "data/test_orch_fix.db"
if Path(db_path).exists():
    if Path(db_path).is_dir():
        shutil.rmtree(db_path)
    else:
        Path(db_path).unlink()

create_schema(db_path)
print("✓ Schema created")

# Initialize orchestrator
orch = RyuGraphOrchestrator(db_path, max_depth=1, batch_size=5)

# Initialize seeds
seeds = [
    "Python (programming language)",
    "Artificial intelligence",
]

for title in seeds:
    orch.conn.execute("""
        CREATE (a:Article {
            title: $title,
            category: 'Computer Science',
            word_count: 0,
            expansion_state: 'discovered',
            expansion_depth: 0,
            claimed_at: NULL,
            processed_at: NULL,
            retry_count: 0
        })
    """, {"title": title})

print(f"✓ Initialized {len(seeds)} seeds")

# Expand to 20 articles
print("\nExpanding to 20 articles (max_depth=1)...")
stats = orch.expand_to_target(target_count=20, max_iterations=30)

print("\n" + "=" * 70)
print("RESULTS")
print("=" * 70)

# Check sections
result = orch.conn.execute("MATCH (s:Section) RETURN COUNT(s) AS count")
sections = result.get_as_df().iloc[0]['count']

# Check articles with content
result = orch.conn.execute("""
    MATCH (a:Article)
    WHERE a.word_count > 0
    RETURN COUNT(a) AS count
""")
articles_with_content = result.get_as_df().iloc[0]['count']

print(f"Duration: {stats['duration_seconds']:.1f}s")
print(f"Iterations: {stats['iterations']}")
print(f"Total sections: {sections}")
print(f"Articles with content: {articles_with_content}")
print(f"State: {stats}")

if sections > 0 and articles_with_content >= 15:
    print("\n✓ FIX VALIDATED - Sections are being inserted!")
else:
    print("\n✗ Issue persists")

# Cleanup
if Path(db_path).exists():
    if Path(db_path).is_dir():
        shutil.rmtree(db_path)
    else:
        Path(db_path).unlink()
