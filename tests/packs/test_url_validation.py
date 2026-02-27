"""Tests for SSRF protection in pack download URL validation."""

from unittest.mock import patch

import pytest

from wikigr.packs._url_validation import validate_download_url


class TestValidateDownloadUrl:
    """Tests for validate_download_url()."""

    def test_allows_https(self) -> None:
        """HTTPS URLs with public hostnames should pass validation."""
        # Mock DNS to return a public IP so we don't make real DNS queries
        with patch(
            "wikigr.packs._url_validation.socket.gethostbyname", return_value="93.184.216.34"
        ):
            validate_download_url("https://registry.wikigr.com/packs/test-1.0.tar.gz")

    def test_rejects_http_scheme(self) -> None:
        """HTTP (non-TLS) URLs must be rejected."""
        with pytest.raises(ValueError, match="Only HTTPS URLs allowed"):
            validate_download_url("http://example.com/pack.tar.gz")

    def test_rejects_file_scheme(self) -> None:
        """file:// URLs must be rejected to prevent local file exfiltration."""
        with pytest.raises(ValueError, match="Only HTTPS URLs allowed"):
            validate_download_url("file:///etc/passwd")

    def test_rejects_ftp_scheme(self) -> None:
        """ftp:// URLs must be rejected."""
        with pytest.raises(ValueError, match="Only HTTPS URLs allowed"):
            validate_download_url("ftp://files.example.com/pack.tar.gz")

    def test_rejects_no_scheme(self) -> None:
        """URLs without a scheme must be rejected."""
        with pytest.raises(ValueError, match="Only HTTPS URLs allowed"):
            validate_download_url("example.com/pack.tar.gz")

    def test_rejects_empty_hostname(self) -> None:
        """URLs without a hostname must be rejected."""
        with pytest.raises(ValueError, match="URL must have a hostname"):
            validate_download_url("https:///path/only")

    def test_rejects_private_ip(self) -> None:
        """URLs resolving to private IPs (e.g. 192.168.x.x) must be rejected."""
        with (
            patch("wikigr.packs._url_validation.socket.gethostbyname", return_value="192.168.1.1"),
            pytest.raises(ValueError, match="private/reserved IPs not allowed"),
        ):
            validate_download_url("https://internal.corp/pack.tar.gz")

    def test_rejects_loopback(self) -> None:
        """URLs resolving to loopback (127.0.0.1) must be rejected."""
        with (
            patch("wikigr.packs._url_validation.socket.gethostbyname", return_value="127.0.0.1"),
            pytest.raises(ValueError, match="private/reserved IPs not allowed"),
        ):
            validate_download_url("https://localhost/pack.tar.gz")

    def test_rejects_link_local(self) -> None:
        """URLs resolving to link-local IPs (169.254.x.x) must be rejected."""
        with (
            patch(
                "wikigr.packs._url_validation.socket.gethostbyname", return_value="169.254.169.254"
            ),
            pytest.raises(ValueError, match="private/reserved IPs not allowed"),
        ):
            validate_download_url("https://metadata.internal/pack.tar.gz")

    def test_dns_failure_allows_through(self) -> None:
        """DNS resolution failure should not block — download will fail later."""
        import socket

        with patch(
            "wikigr.packs._url_validation.socket.gethostbyname",
            side_effect=socket.gaierror("Name resolution failed"),
        ):
            # Should not raise — DNS failure is handled gracefully
            validate_download_url("https://nonexistent.example.com/pack.tar.gz")
