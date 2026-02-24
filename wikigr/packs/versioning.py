"""Pack version management and compatibility checking.

This module provides functions for comparing semantic versions and checking
compatibility between pack versions.
"""

import re


def _parse_version(version: str) -> tuple[int, int, int, str, str]:
    """Parse semantic version string into components.

    Args:
        version: Semantic version string (e.g., "1.2.3", "1.0.0-alpha+build")

    Returns:
        Tuple of (major, minor, patch, prerelease, build_metadata)

    Raises:
        ValueError: If version doesn't match semantic versioning format
    """
    # Semantic versioning pattern
    pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$"
    match = re.match(pattern, version)

    if not match:
        raise ValueError(f"Invalid semantic version: {version}")

    major, minor, patch, prerelease, build = match.groups()
    return (
        int(major),
        int(minor),
        int(patch),
        prerelease or "",
        build or "",
    )


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic version strings.

    Args:
        v1: First version string
        v2: Second version string

    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2

    Raises:
        ValueError: If either version string is invalid

    Examples:
        >>> compare_versions("1.0.0", "1.0.0")
        0
        >>> compare_versions("2.0.0", "1.0.0")
        1
        >>> compare_versions("1.0.0", "2.0.0")
        -1
        >>> compare_versions("1.0.0", "1.0.0-alpha")
        1
    """
    major1, minor1, patch1, pre1, build1 = _parse_version(v1)
    major2, minor2, patch2, pre2, build2 = _parse_version(v2)

    # Compare major.minor.patch
    if major1 != major2:
        return 1 if major1 > major2 else -1
    if minor1 != minor2:
        return 1 if minor1 > minor2 else -1
    if patch1 != patch2:
        return 1 if patch1 > patch2 else -1

    # Compare pre-release versions
    # When major.minor.patch are equal:
    # - Version without pre-release > version with pre-release
    # - Compare pre-release strings lexically
    if pre1 == pre2:
        return 0
    if not pre1:  # v1 is stable, v2 is pre-release
        return 1
    if not pre2:  # v1 is pre-release, v2 is stable
        return -1

    # Both have pre-release, compare lexically
    if pre1 < pre2:
        return -1
    if pre1 > pre2:
        return 1

    return 0


def is_compatible(required: str, installed: str) -> bool:
    """Check if installed version is compatible with required version.

    Compatibility rules (following semantic versioning):
    - Major version must match exactly
    - Minor/patch versions can differ
    - Pre-release versions must match exactly
    - Build metadata is ignored

    Args:
        required: Required version string
        installed: Installed version string

    Returns:
        True if versions are compatible, False otherwise

    Examples:
        >>> is_compatible("1.0.0", "1.5.0")
        True
        >>> is_compatible("1.0.0", "2.0.0")
        False
        >>> is_compatible("1.0.0", "1.0.0-alpha")
        False
    """
    try:
        major_req, minor_req, patch_req, pre_req, _ = _parse_version(required)
        major_inst, minor_inst, patch_inst, pre_inst, _ = _parse_version(installed)
    except ValueError:
        # Invalid version strings are not compatible
        return False

    # Major version must match
    if major_req != major_inst:
        return False

    # Pre-release handling:
    # - If either version has pre-release, both must match exactly
    # - If both are stable (no pre-release), minor/patch can differ
    if pre_req or pre_inst:
        # If pre-release exists, entire version must match
        return (
            major_req == major_inst
            and minor_req == minor_inst
            and patch_req == patch_inst
            and pre_req == pre_inst
        )

    # Both are stable releases with same major version
    return True
