"""Tests for pack version management."""

import pytest

from wikigr.packs.versioning import compare_versions, is_compatible


class TestCompareVersions:
    """Test version comparison function."""

    def test_compare_equal_versions(self):
        """Test comparing equal versions returns 0."""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.3.4", "2.3.4") == 0

    def test_compare_major_version_difference(self):
        """Test major version comparison."""
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("10.0.0", "2.0.0") == 1

    def test_compare_minor_version_difference(self):
        """Test minor version comparison."""
        assert compare_versions("1.2.0", "1.1.0") == 1
        assert compare_versions("1.1.0", "1.2.0") == -1
        assert compare_versions("1.10.0", "1.2.0") == 1

    def test_compare_patch_version_difference(self):
        """Test patch version comparison."""
        assert compare_versions("1.0.2", "1.0.1") == 1
        assert compare_versions("1.0.1", "1.0.2") == -1
        assert compare_versions("1.0.10", "1.0.2") == 1

    def test_compare_mixed_differences(self):
        """Test comparison with multiple version parts different."""
        assert compare_versions("2.1.0", "1.9.9") == 1
        assert compare_versions("1.9.9", "2.0.0") == -1
        assert compare_versions("1.2.3", "1.2.2") == 1

    def test_compare_with_prerelease(self):
        """Test comparison with pre-release versions."""
        assert compare_versions("1.0.0", "1.0.0-alpha") == 1
        assert compare_versions("1.0.0-alpha", "1.0.0") == -1
        assert compare_versions("1.0.0-alpha", "1.0.0-alpha") == 0
        assert compare_versions("1.0.0-beta", "1.0.0-alpha") == 1

    def test_compare_with_build_metadata(self):
        """Test comparison ignores build metadata."""
        assert compare_versions("1.0.0+build1", "1.0.0+build2") == 0
        assert compare_versions("1.0.0", "1.0.0+build1") == 0

    def test_invalid_version_format(self):
        """Test invalid version formats raise ValueError."""
        with pytest.raises(ValueError):
            compare_versions("1.0", "1.0.0")
        with pytest.raises(ValueError):
            compare_versions("1.0.0", "invalid")
        with pytest.raises(ValueError):
            compare_versions("v1.0.0", "1.0.0")


class TestIsCompatible:
    """Test version compatibility checking."""

    def test_exact_version_compatible(self):
        """Test exact version match is compatible."""
        assert is_compatible("1.0.0", "1.0.0") is True
        assert is_compatible("2.3.4", "2.3.4") is True

    def test_patch_version_compatible(self):
        """Test patch version differences are compatible."""
        assert is_compatible("1.0.0", "1.0.5") is True
        assert is_compatible("1.0.5", "1.0.0") is True
        assert is_compatible("2.3.4", "2.3.10") is True

    def test_minor_version_compatible(self):
        """Test minor version differences are compatible (same major)."""
        assert is_compatible("1.0.0", "1.5.0") is True
        assert is_compatible("1.5.0", "1.0.0") is True
        assert is_compatible("2.1.0", "2.9.9") is True

    def test_major_version_incompatible(self):
        """Test major version differences are incompatible."""
        assert is_compatible("1.0.0", "2.0.0") is False
        assert is_compatible("2.0.0", "1.0.0") is False
        assert is_compatible("1.9.9", "2.0.0") is False

    def test_prerelease_incompatible_with_stable(self):
        """Test pre-release versions incompatible with stable."""
        assert is_compatible("1.0.0", "1.0.0-alpha") is False
        assert is_compatible("1.0.0-alpha", "1.0.0") is False

    def test_prerelease_compatible_with_same_prerelease(self):
        """Test pre-release versions compatible with same tag."""
        assert is_compatible("1.0.0-alpha", "1.0.0-alpha") is True
        assert is_compatible("1.0.0-beta.1", "1.0.0-beta.1") is True

    def test_build_metadata_ignored(self):
        """Test build metadata doesn't affect compatibility."""
        assert is_compatible("1.0.0+build1", "1.0.0+build2") is True
        assert is_compatible("1.0.0", "1.0.0+build1") is True
