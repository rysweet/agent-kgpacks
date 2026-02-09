#!/usr/bin/env python3
"""
Test suite for monitor_expansion.py

Validates all monitoring features work correctly.
"""

import sys
sys.path.insert(0, '/home/azureuser/src/wikigr/bootstrap/scripts')

from monitor_expansion import ExpansionMonitor
import kuzu
from pathlib import Path


def test_basic_metrics():
    """Test basic metric collection from database"""
    print("=" * 70)
    print("Test: Basic Metrics Collection")
    print("=" * 70)

    # Use existing test database
    db_path = "data/test_10_articles.db"

    if not Path(db_path).exists():
        print(f"❌ Test database not found: {db_path}")
        return False

    monitor = ExpansionMonitor(db_path, target_count=50)

    # Test state distribution
    print("\n1. Testing state distribution...")
    state_dist = monitor.get_state_distribution()
    assert isinstance(state_dist, dict), "State distribution should be a dict"
    assert sum(state_dist.values()) > 0, "Should have articles in database"
    print(f"   ✓ State distribution: {state_dist}")

    # Test depth distribution
    print("\n2. Testing depth distribution...")
    depth_dist = monitor.get_depth_distribution()
    assert isinstance(depth_dist, dict), "Depth distribution should be a dict"
    print(f"   ✓ Depth distribution: {depth_dist}")

    # Test category distribution
    print("\n3. Testing category distribution...")
    category_dist = monitor.get_category_distribution(limit=5)
    assert isinstance(category_dist, dict), "Category distribution should be a dict"
    print(f"   ✓ Category distribution: {category_dist}")

    # Test loaded count
    print("\n4. Testing loaded count...")
    loaded = monitor.get_loaded_count()
    assert isinstance(loaded, int), "Loaded count should be an int"
    assert loaded >= 0, "Loaded count should be non-negative"
    print(f"   ✓ Loaded count: {loaded}")

    print("\n✅ All basic metrics tests passed!")
    return True


def test_display_functions():
    """Test display formatting functions"""
    print("\n" + "=" * 70)
    print("Test: Display Formatting Functions")
    print("=" * 70)

    monitor = ExpansionMonitor("data/test_10_articles.db", target_count=50)

    # Test progress bar formatting
    print("\n1. Testing progress bar formatting...")
    bar_0 = monitor.format_bar(0, width=20)
    bar_50 = monitor.format_bar(50, width=20)
    bar_100 = monitor.format_bar(100, width=20)

    assert len(bar_0) == 20, "Progress bar should be correct width"
    assert len(bar_50) == 20, "Progress bar should be correct width"
    assert len(bar_100) == 20, "Progress bar should be correct width"
    assert bar_0.count("█") == 0, "0% should have no filled blocks"
    assert bar_50.count("█") == 10, "50% should be half filled"
    assert bar_100.count("█") == 20, "100% should be fully filled"
    print(f"   ✓ Progress bars render correctly")
    print(f"      0%:   [{bar_0}]")
    print(f"     50%:   [{bar_50}]")
    print(f"    100%:   [{bar_100}]")

    # Test duration formatting
    print("\n2. Testing duration formatting...")
    assert monitor.format_duration(30) == "30s"
    assert monitor.format_duration(90) == "1.5m"
    assert monitor.format_duration(3600) == "1h 0m"
    assert monitor.format_duration(3750) == "1h 2m"
    print(f"   ✓ Duration formatting works")
    print(f"      30s:    {monitor.format_duration(30)}")
    print(f"      90s:    {monitor.format_duration(90)}")
    print(f"      3600s:  {monitor.format_duration(3600)}")
    print(f"      3750s:  {monitor.format_duration(3750)}")

    print("\n✅ All display formatting tests passed!")
    return True


def test_full_display():
    """Test full display rendering"""
    print("\n" + "=" * 70)
    print("Test: Full Display Rendering")
    print("=" * 70)

    monitor = ExpansionMonitor("data/test_10_articles.db", target_count=50)

    print("\n1. Rendering full display...")
    try:
        monitor.display()
        print("\n   ✓ Display rendered without errors")
    except Exception as e:
        print(f"   ❌ Display rendering failed: {e}")
        return False

    print("\n✅ Full display test passed!")
    return True


def test_with_different_databases():
    """Test monitor with different database sizes"""
    print("\n" + "=" * 70)
    print("Test: Different Database Sizes")
    print("=" * 70)

    test_dbs = [
        ("data/test_10_articles.db", 10),
        ("data/test_100_articles.db", 100)
    ]

    for db_path, expected_min in test_dbs:
        if not Path(db_path).exists():
            print(f"⚠️  Skipping {db_path} (not found)")
            continue

        print(f"\n1. Testing with {db_path}...")
        monitor = ExpansionMonitor(db_path, target_count=expected_min)

        state_dist = monitor.get_state_distribution()
        total = sum(state_dist.values())

        print(f"   Total articles: {total}")
        assert total > 0, f"Database should have articles"
        print(f"   ✓ {db_path} works correctly")

    print("\n✅ All database size tests passed!")
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("MONITOR EXPANSION TEST SUITE")
    print("=" * 70)

    tests = [
        ("Basic Metrics", test_basic_metrics),
        ("Display Functions", test_display_functions),
        ("Full Display", test_full_display),
        ("Different Databases", test_with_different_databases)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
