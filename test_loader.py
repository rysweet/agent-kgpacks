#!/usr/bin/env python3
"""Test the database loader"""

import sys
sys.path.insert(0, 'bootstrap')

from src.database import ArticleLoader

print("=" * 60)
print("Article Loader Test")
print("=" * 60)

# Create test database
db_path = "data/test_loader.db"
print(f"\nDatabase: {db_path}")

# Initialize loader
loader = ArticleLoader(db_path)

# Test articles
test_articles = [
    ("Python (programming language)", "Computer Science"),
    ("Machine Learning", "Computer Science"),
    ("Quantum Computing", "Physics")
]

print(f"\nLoading {len(test_articles)} test articles...")

for title, category in test_articles:
    success, error = loader.load_article(title, category=category)

    if success:
        print(f"  ✓ {title}")
    else:
        print(f"  ✗ {title}: {error}")

# Check results
print(f"\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Articles in database: {loader.get_article_count()}")
print(f"Sections in database: {loader.get_section_count()}")

# Verify data
result = loader.conn.execute("""
    MATCH (a:Article)-[:HAS_SECTION]->(s:Section)
    RETURN a.title AS article, COUNT(s) AS sections
    ORDER BY sections DESC
""")

print("\nArticles with section counts:")
df = result.get_as_df()
for idx, row in df.iterrows():
    print(f"  {row['article']}: {row['sections']} sections")

print("\n✓ Test complete!")
