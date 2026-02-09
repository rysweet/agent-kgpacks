#!/usr/bin/env python3
"""
Demo: Real-time monitor with simulated expansion

Shows monitor behavior during a simulated expansion process.
This demonstrates how the monitor tracks changing metrics over time.
"""

import sys
import time

sys.path.insert(0, "/home/azureuser/src/wikigr/bootstrap/scripts")

from monitor_expansion import ExpansionMonitor


def demo_monitor_with_static_data():
    """Demo monitor with existing test database"""
    print("=" * 80)
    print("DEMO: Monitor with Existing Test Data")
    print("=" * 80)
    print()
    print("This demo shows the monitor displaying stats from a completed expansion.")
    print("Database: data/test_100_articles.db")
    print()
    print("Press Ctrl+C to exit the demo")
    print()
    input("Press Enter to start...")

    # Create monitor instance
    monitor = ExpansionMonitor("data/test_100_articles.db", target_count=1000)

    # Show 3 refresh cycles
    for i in range(3):
        print(f"\n--- Refresh cycle {i + 1}/3 ---")
        monitor.display()
        if i < 2:
            time.sleep(5)

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80)


def show_monitor_features():
    """Show different monitor features"""
    print("=" * 80)
    print("MONITOR FEATURES DEMONSTRATION")
    print("=" * 80)

    monitor = ExpansionMonitor("data/test_10_articles.db", target_count=50)

    print("\n1. State Distribution")
    print("-" * 40)
    state_dist = monitor.get_state_distribution()
    for state, count in state_dist.items():
        print(f"   {state:12}: {count:6}")

    print("\n2. Depth Distribution")
    print("-" * 40)
    depth_dist = monitor.get_depth_distribution()
    for depth, count in depth_dist.items():
        print(f"   Depth {depth}: {count}")

    print("\n3. Category Distribution")
    print("-" * 40)
    cat_dist = monitor.get_category_distribution(limit=5)
    for category, count in cat_dist.items():
        print(f"   {category:30}: {count:4}")

    print("\n4. Progress Metrics")
    print("-" * 40)
    loaded = monitor.get_loaded_count()
    if monitor.target_count:
        progress = 100 * loaded / monitor.target_count
        print(f"   Loaded: {loaded}/{monitor.target_count}")
        print(f"   Progress: {progress:.1f}%")
        bar = monitor.format_bar(progress, width=40)
        print(f"   [{bar}]")

    print("\n5. Performance Stats")
    print("-" * 40)
    elapsed = time.time() - monitor.start_time
    rate = loaded / elapsed if elapsed > 0 else 0
    print(f"   Elapsed: {monitor.format_duration(elapsed)}")
    print(f"   Rate: {rate * 60:.1f} articles/minute")

    print("\n" + "=" * 80)


def main():
    """Run demos"""
    print("\nWikiGR Monitor Demonstration")
    print("=" * 80)
    print()
    print("Choose a demo:")
    print("  1. Monitor with static test data (recommended)")
    print("  2. Show individual monitor features")
    print("  3. Exit")
    print()

    choice = input("Enter choice (1-3): ").strip()

    if choice == "1":
        demo_monitor_with_static_data()
    elif choice == "2":
        show_monitor_features()
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
