"""
Work Queue Manager Demo

Demonstrates complete workflow of work queue management:
- Initialize seed articles
- Claim work batches
- Simulate processing with heartbeats
- Handle failures with retries
- Monitor queue statistics
"""

import kuzu
import time
from datetime import datetime


def demo_work_queue():
    """Demonstrate work queue manager workflow"""

    print("=" * 70)
    print("Work Queue Manager Demo")
    print("=" * 70)

    # Create in-memory database
    print("\n1. Setting up test database...")
    db = kuzu.Database()
    conn = kuzu.Connection(db)

    # Create schema
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
    print("   ✓ Schema created")

    # Initialize with seed articles
    print("\n2. Initializing seed articles...")
    seeds = [
        "Machine Learning",
        "Deep Learning",
        "Neural Networks"
    ]

    for title in seeds:
        conn.execute("""
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
    print(f"   ✓ Initialized {len(seeds)} seed articles")

    # Import WorkQueueManager
    from ..work_queue import WorkQueueManager
    manager = WorkQueueManager(conn, max_retries=3)
    print("   ✓ WorkQueueManager initialized")

    # Display initial stats
    print("\n3. Initial queue statistics:")
    stats = manager.get_queue_stats()
    print(f"   Discovered: {stats['discovered']}")
    print(f"   Claimed: {stats['claimed']}")
    print(f"   Loaded: {stats['loaded']}")
    print(f"   Failed: {stats['failed']}")

    # Claim work
    print("\n4. Claiming work batch...")
    articles = manager.claim_work(batch_size=2)
    print(f"   ✓ Claimed {len(articles)} articles:")
    for article in articles:
        print(f"     - {article['title']} (depth={article['expansion_depth']})")

    # Simulate processing with heartbeats
    print("\n5. Simulating article processing with heartbeats...")
    for article in articles:
        title = article['title']
        print(f"\n   Processing: {title}")

        # Simulate work with periodic heartbeats
        for i in range(3):
            print(f"     [Step {i+1}/3] Working...")
            time.sleep(0.5)
            manager.update_heartbeat(title)
            print(f"     [Heartbeat] Updated at {datetime.now().strftime('%H:%M:%S')}")

        # Mark as successfully loaded
        manager.advance_state(title, "loaded")
        print(f"     ✓ Advanced to 'loaded' state")

    # Check stats after processing
    print("\n6. Queue statistics after processing:")
    stats = manager.get_queue_stats()
    print(f"   Discovered: {stats['discovered']}")
    print(f"   Claimed: {stats['claimed']}")
    print(f"   Loaded: {stats['loaded']}")
    print(f"   Failed: {stats['failed']}")

    # Claim remaining work
    print("\n7. Processing remaining article with failure simulation...")
    remaining = manager.claim_work(batch_size=1)
    if remaining:
        title = remaining[0]['title']
        print(f"   Claimed: {title}")

        # Simulate failure
        print(f"   Simulating failure...")
        manager.mark_failed(title, "Simulated network error")
        print(f"   ✓ Marked as failed (will retry)")

        # Check retry state
        result = conn.execute("""
            MATCH (a:Article {title: $title})
            RETURN a.retry_count AS retry_count, a.expansion_state AS state
        """, {"title": title})
        df = result.get_as_df()
        print(f"   Retry count: {df.iloc[0]['retry_count']}")
        print(f"   State: {df.iloc[0]['state']}")

    # Final statistics
    print("\n8. Final queue statistics:")
    stats = manager.get_queue_stats()
    print(f"   Discovered: {stats['discovered']}")
    print(f"   Claimed: {stats['claimed']}")
    print(f"   Loaded: {stats['loaded']}")
    print(f"   Failed: {stats['failed']}")

    # Demonstrate stale reclaim
    print("\n9. Demonstrating stale claim reclamation...")

    # Claim an article
    articles = manager.claim_work(batch_size=1)
    if articles:
        title = articles[0]['title']
        print(f"   Claimed: {title}")

        # Manually set old timestamp to simulate stale claim
        from datetime import timedelta
        old_time = datetime.now() - timedelta(seconds=400)
        conn.execute("""
            MATCH (a:Article {title: $title})
            SET a.claimed_at = $old_time
        """, {"title": title, "old_time": old_time})
        print(f"   Simulated stale claim (no heartbeat for 400 seconds)")

        # Reclaim stale work
        reclaimed = manager.reclaim_stale(timeout_seconds=300)
        print(f"   ✓ Reclaimed {reclaimed} stale claim(s)")

        # Verify state
        result = conn.execute("""
            MATCH (a:Article {title: $title})
            RETURN a.expansion_state AS state
        """, {"title": title})
        state = result.get_as_df().iloc[0]['state']
        print(f"   Article state: {state} (back to queue)")

    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nKey Features Demonstrated:")
    print("  ✓ Claim-based work distribution")
    print("  ✓ Heartbeat updates to prevent reclamation")
    print("  ✓ State transitions (discovered → claimed → loaded)")
    print("  ✓ Failure handling with retry logic")
    print("  ✓ Stale claim reclamation")
    print("  ✓ Queue statistics monitoring")


if __name__ == "__main__":
    demo_work_queue()
