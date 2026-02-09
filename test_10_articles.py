#!/usr/bin/env python3
"""
End-to-end test with 10 diverse Wikipedia articles

Validates complete pipeline:
1. Schema creation
2. Article loading (fetch, parse, embed)
3. Semantic search queries
4. Performance measurement
"""

import sys

sys.path.insert(0, "bootstrap")

import shutil
import time
from pathlib import Path

import numpy as np
from schema.ryugraph_schema import create_schema
from src.database import ArticleLoader
from src.query import semantic_search

print("=" * 70)
print("WikiGR 10-Article End-to-End Validation")
print("=" * 70)

# Configuration
DB_PATH = "data/test_10_articles.db"

# 10 diverse, high-quality articles (full article names for Wikipedia API)
TEST_ARTICLES = [
    ("Artificial intelligence", "Computer Science"),
    ("Python (programming language)", "Computer Science"),
    ("Neural network (machine learning)", "Computer Science"),
    ("Quantum mechanics", "Physics"),
    ("General relativity", "Physics"),
    ("DNA", "Biology"),
    ("Evolution", "Biology"),
    ("World War II", "History"),
    ("Democracy", "Political Science"),
    ("Philosophy", "Philosophy"),
]

# Step 1: Create fresh database
print("\n1. Creating fresh database...")
if Path(DB_PATH).exists():
    if Path(DB_PATH).is_dir():
        shutil.rmtree(DB_PATH)
    else:
        Path(DB_PATH).unlink()

create_schema(DB_PATH, drop_existing=False)
print("✓ Database ready")

# Step 2: Initialize loader
print("\n2. Initializing article loader...")
loader = ArticleLoader(DB_PATH)
print("✓ Loader initialized")

# Step 3: Load 10 articles
print(f"\n3. Loading {len(TEST_ARTICLES)} articles...")
print("-" * 70)

load_times = []
successful_articles = []
failed_articles = []

for i, (title, category) in enumerate(TEST_ARTICLES, 1):
    print(f"\n[{i}/{len(TEST_ARTICLES)}] {title}")

    start_time = time.time()
    success, error = loader.load_article(title, category=category)
    elapsed = time.time() - start_time

    if success:
        load_times.append(elapsed)
        successful_articles.append(title)
        print(f"    ✓ Loaded in {elapsed:.2f}s")
    else:
        failed_articles.append((title, error))
        print(f"    ✗ Failed: {error}")

# Step 4: Check database stats
print("\n" + "=" * 70)
print("DATABASE STATISTICS")
print("=" * 70)

total_articles = loader.get_article_count()
total_sections = loader.get_section_count()

print(f"\nTotal articles: {total_articles}")
print(f"Total sections: {total_sections}")
print(
    f"Average sections per article: {total_sections / total_articles if total_articles > 0 else 0:.1f}"
)

# Article details
result = loader.conn.execute("""
    MATCH (a:Article)-[:HAS_SECTION]->(s:Section)
    RETURN a.title AS article, a.category AS category, COUNT(s) AS sections, a.word_count AS words
    ORDER BY sections DESC
""")

articles_df = result.get_as_df()

print("\nArticle details:")
print("-" * 70)
for idx, row in articles_df.iterrows():
    print(
        f"  {row['article']:<45} {row['sections']:>3} sections  {row['words']:>6} words  {row['category']}"
    )

# Database size
if Path(DB_PATH).is_dir():
    db_size_mb = sum(f.stat().st_size for f in Path(DB_PATH).rglob("*") if f.is_file()) / (
        1024 * 1024
    )
else:
    db_size_mb = 0

print(f"\nDatabase size: {db_size_mb:.1f} MB")

# Step 5: Test semantic search
print("\n" + "=" * 70)
print("SEMANTIC SEARCH TESTS")
print("=" * 70)

test_queries = [
    (
        "Artificial intelligence",
        "Computer Science",
        ["Python (programming language)", "Neural network (machine learning)"],
    ),
    ("DNA", "Biology", ["Evolution"]),
    ("Quantum mechanics", "Physics", ["General relativity"]),
]

query_latencies = []

for query_title, category, expected in test_queries:
    if query_title not in successful_articles:
        print(f"\n✗ Skipping {query_title} (not loaded)")
        continue

    print(f"\nQuery: '{query_title}' (category={category})")

    start = time.time()
    results = semantic_search(loader.conn, query_title, category=category, top_k=5)
    elapsed = (time.time() - start) * 1000  # ms

    query_latencies.append(elapsed)

    print(f"  Latency: {elapsed:.1f} ms")
    print(f"  Results: {len(results)}")

    if results:
        print("\n  Top 3 results:")
        for result in results[:3]:
            print(f"    {result['rank']}. {result['article_title']}")
            print(f"       Similarity: {result['similarity']:.4f}")
            print(f"       Section: {result['section_title']}")

        # Check if expected results are in top results
        result_titles = [r["article_title"] for r in results]
        matches = [e for e in expected if e in result_titles]

        if matches:
            print(f"\n  ✓ Found {len(matches)}/{len(expected)} expected results: {matches}")
        else:
            print(f"\n  ⚠ None of the expected results found in top {len(results)}")

# Step 6: Performance summary
print("\n" + "=" * 70)
print("PERFORMANCE SUMMARY")
print("=" * 70)

if load_times:
    print("\nArticle Loading:")
    print(f"  Total articles attempted: {len(TEST_ARTICLES)}")
    print(f"  Successful: {len(successful_articles)}")
    print(f"  Failed: {len(failed_articles)}")
    print(f"  Success rate: {100 * len(successful_articles) / len(TEST_ARTICLES):.1f}%")
    print(f"\n  Load time (avg): {np.mean(load_times):.2f}s")
    print(f"  Load time (min): {np.min(load_times):.2f}s")
    print(f"  Load time (max): {np.max(load_times):.2f}s")

if query_latencies:
    print("\nQuery Performance:")
    print(f"  Queries run: {len(query_latencies)}")
    print(f"  Latency (avg): {np.mean(query_latencies):.1f} ms")
    print(f"  Latency (p50): {np.percentile(query_latencies, 50):.1f} ms")
    print(f"  Latency (p95): {np.percentile(query_latencies, 95):.1f} ms")
    print(f"  Latency (max): {np.max(query_latencies):.1f} ms")

    p95 = np.percentile(query_latencies, 95)
    if p95 < 500:
        print(f"\n  ✓ P95 latency {p95:.1f}ms < 500ms target")
    else:
        print(f"\n  ✗ P95 latency {p95:.1f}ms > 500ms target")

# Step 7: Success criteria
print("\n" + "=" * 70)
print("SUCCESS CRITERIA")
print("=" * 70)

success_criteria = {
    "Articles loaded": (
        len(successful_articles) >= 8,
        f"{len(successful_articles)}/10 (target: 8+)",
    ),
    "Database size": (db_size_mb < 50, f"{db_size_mb:.1f} MB (target: <50 MB)"),
    "P95 latency": (
        np.percentile(query_latencies, 95) < 500 if query_latencies else False,
        f"{np.percentile(query_latencies, 95) if query_latencies else 0:.1f} ms (target: <500ms)",
    ),
}

all_pass = True
for criterion, (passed, value) in success_criteria.items():
    status = "✓" if passed else "✗"
    print(f"  {status} {criterion}: {value}")
    if not passed:
        all_pass = False

print("\n" + "=" * 70)
if all_pass:
    print("✓ ALL SUCCESS CRITERIA MET!")
    print("\n🚀 Ready to proceed to Issue #10: Orchestrator")
else:
    print("⚠ Some criteria not met - review and fix")
print("=" * 70)

if failed_articles:
    print("\nFailed articles:")
    for title, error in failed_articles:
        print(f"  ✗ {title}")
        print(f"    Error: {error[:100]}")
