#!/usr/bin/env python3
"""Example usage of Wikipedia API Client

Demonstrates:
- Basic article fetching
- Batch fetching
- Error handling
- Caching
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.wikipedia import ArticleNotFoundError, WikipediaAPIClient, WikipediaAPIError


def example_basic_fetch():
    """Basic article fetching example"""
    print("=" * 60)
    print("Example 1: Basic Article Fetching")
    print("=" * 60)

    client = WikipediaAPIClient()
    article = client.fetch_article("Python (programming language)")

    print(f"Title: {article.title}")
    print(f"Page ID: {article.pageid}")
    print(f"Wikitext: {len(article.wikitext):,} chars")
    print(f"Links: {len(article.links):,} links")
    print(f"Categories: {len(article.categories)} categories")
    print(f"\nFirst 5 links: {article.links[:5]}")
    print(f"First 3 categories: {article.categories[:3]}")
    print()


def example_batch_fetch():
    """Batch fetching with error handling"""
    print("=" * 60)
    print("Example 2: Batch Fetching")
    print("=" * 60)

    client = WikipediaAPIClient()

    titles = [
        "Artificial Intelligence",
        "Machine Learning",
        "Deep Learning",
        "This Article Does Not Exist",  # Will fail
        "Neural Network",
    ]

    print(f"Fetching {len(titles)} articles...\n")
    results = client.fetch_batch(titles, continue_on_error=True)

    successful = []
    failed = []

    for title, article, error in results:
        if error:
            failed.append((title, error))
            print(f"✗ {title}: {type(error).__name__}")
        else:
            successful.append((title, article))
            print(f"✓ {title}: {len(article.wikitext):,} chars")

    print(f"\nSuccess rate: {len(successful)}/{len(titles)}")
    print()


def example_error_handling():
    """Error handling demonstration"""
    print("=" * 60)
    print("Example 3: Error Handling")
    print("=" * 60)

    client = WikipediaAPIClient()

    # Try to fetch non-existent article
    try:
        article = client.fetch_article("Zxzxzxzxzx Nonexistent Article 99999")
        print("✗ Should have raised ArticleNotFoundError")
    except ArticleNotFoundError as e:
        print(f"✓ Caught ArticleNotFoundError: {e}")

    # Try valid article
    try:
        article = client.fetch_article("Computer Science")
        print(f"✓ Successfully fetched: {article.title}")
    except WikipediaAPIError as e:
        print(f"✗ Unexpected error: {e}")

    print()


def example_caching():
    """Caching demonstration"""
    print("=" * 60)
    print("Example 4: Caching")
    print("=" * 60)

    import time

    # Without cache
    client = WikipediaAPIClient(cache_enabled=False)
    start = time.time()
    client.fetch_article("Artificial Intelligence")
    time1 = time.time() - start

    start = time.time()
    client.fetch_article("Artificial Intelligence")
    time2 = time.time() - start

    print("Without cache:")
    print(f"  First fetch: {time1:.3f}s")
    print(f"  Second fetch: {time2:.3f}s")

    # With cache
    client = WikipediaAPIClient(cache_enabled=True)
    start = time.time()
    client.fetch_article("Machine Learning")
    time1 = time.time() - start

    start = time.time()
    client.fetch_article("Machine Learning")
    time2 = time.time() - start

    print("\nWith cache:")
    print(f"  First fetch: {time1:.3f}s")
    print(f"  Second fetch (cached): {time2:.3f}s")
    print(f"  Speedup: {time1 / time2:.1f}x faster")
    print()


def example_article_analysis():
    """Analyze article structure"""
    print("=" * 60)
    print("Example 5: Article Analysis")
    print("=" * 60)

    client = WikipediaAPIClient()
    article = client.fetch_article("Neural Network")

    print(f"Analyzing: {article.title}\n")

    # Count sections (rough estimate from wikitext)
    section_count = article.wikitext.count("\n==")
    print(f"Sections (approx): {section_count}")

    # Find internal links
    internal_links = [link for link in article.links if not link.startswith("File:")]
    print(f"Internal article links: {len(internal_links)}")

    # Category analysis
    cs_categories = [
        cat for cat in article.categories if "computer" in cat.lower() or "science" in cat.lower()
    ]
    print(f"Computer Science related categories: {len(cs_categories)}")

    # Link to other AI topics
    ai_links = [
        link
        for link in article.links
        if any(
            term in link.lower() for term in ["artificial", "intelligence", "machine", "learning"]
        )
    ]
    print(f"AI-related links: {len(ai_links)}")
    print(f"Sample AI links: {ai_links[:5]}")

    print()


if __name__ == "__main__":
    print("\nWikipedia API Client Examples\n")

    try:
        example_basic_fetch()
        example_batch_fetch()
        example_error_handling()
        example_caching()
        example_article_analysis()

        print("=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
