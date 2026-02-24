#!/usr/bin/env python3
"""Example: Check version compatibility between packs.

This script demonstrates how to use the version comparison and compatibility
checking functions to manage pack dependencies and updates.
"""

from wikigr.packs import compare_versions, is_compatible


def main():
    """Demonstrate version comparison and compatibility checking."""
    print("=== Version Comparison Examples ===\n")

    # Example 1: Comparing versions
    print("1. Comparing versions:")
    versions = [
        ("1.0.0", "1.0.0", "equal"),
        ("2.0.0", "1.9.9", "newer"),
        ("1.5.0", "2.0.0", "older"),
        ("1.0.0-alpha", "1.0.0", "pre-release vs stable"),
    ]

    for v1, v2, description in versions:
        result = compare_versions(v1, v2)
        if result == 0:
            symbol = "=="
        elif result > 0:
            symbol = ">"
        else:
            symbol = "<"
        print(f"  {v1} {symbol} {v2}  ({description})")

    # Example 2: Checking compatibility
    print("\n2. Checking compatibility:")
    compatibility_checks = [
        ("1.0.0", "1.5.0", "Same major version"),
        ("1.0.0", "2.0.0", "Different major version"),
        ("2.3.0", "2.3.5", "Patch version difference"),
        ("1.0.0", "1.0.0-alpha", "Stable vs pre-release"),
    ]

    for required, installed, description in compatibility_checks:
        compatible = is_compatible(required, installed)
        status = "✓ Compatible" if compatible else "✗ Incompatible"
        print(f"  Required: {required}, Installed: {installed}")
        print(f"  {status} ({description})")
        print()

    # Example 3: Real-world scenario - checking if update is safe
    print("3. Safe update checking:")

    current_version = "1.2.3"
    available_updates = ["1.2.4", "1.3.0", "2.0.0"]

    print(f"Current version: {current_version}")
    print("Available updates:")

    for update_version in available_updates:
        compatible = is_compatible(current_version, update_version)
        comparison = compare_versions(update_version, current_version)

        if comparison > 0 and compatible:
            update_type = "Safe update (backwards compatible)"
        elif comparison > 0 and not compatible:
            update_type = "Breaking change (major version bump)"
        else:
            update_type = "Downgrade (not recommended)"

        print(f"  {update_version}: {update_type}")

    # Example 4: Dependency resolution
    print("\n4. Dependency resolution:")

    # Dependencies with their pack-core version requirements
    # pack-a requires ^1.2.0, pack-b requires ^1.5.0
    pack_core_versions = ["1.2.0", "1.5.0", "1.9.9", "2.0.0"]

    print("Checking which pack-core versions satisfy both dependencies:")
    for core_version in pack_core_versions:
        compat_a = is_compatible("1.2.0", core_version)
        compat_b = is_compatible("1.5.0", core_version)

        if compat_a and compat_b:
            print(f"  ✓ {core_version} - Compatible with both")
        else:
            reasons = []
            if not compat_a:
                reasons.append("pack-a")
            if not compat_b:
                reasons.append("pack-b")
            print(f"  ✗ {core_version} - Incompatible with: {', '.join(reasons)}")

    print("\nVersion management best practices:")
    print("1. Use semantic versioning (major.minor.patch)")
    print("2. Increment major version for breaking changes")
    print("3. Increment minor version for new features (backwards compatible)")
    print("4. Increment patch version for bug fixes")
    print("5. Use pre-release versions for testing (e.g., 1.0.0-alpha)")


if __name__ == "__main__":
    main()
