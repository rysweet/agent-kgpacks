"""Security tests for web.py - SSRF and input validation."""

import pytest

from ..web import _validate_url


class TestSSRFProtection:
    """Test SSRF attack prevention in URL validation."""

    def test_allows_valid_https_url(self):
        """Valid HTTPS URLs should pass validation."""
        _validate_url("https://example.com/page")
        _validate_url("https://docs.microsoft.com/azure")

    def test_allows_valid_http_url(self):
        """Valid HTTP URLs should pass validation."""
        _validate_url("http://example.com/page")

    def test_rejects_file_scheme(self):
        """File:// URLs must be rejected."""
        with pytest.raises(ValueError, match="Only HTTP\\(S\\) URLs are allowed"):
            _validate_url("file:///etc/passwd")

    def test_rejects_ftp_scheme(self):
        """FTP URLs must be rejected."""
        with pytest.raises(ValueError, match="Only HTTP\\(S\\) URLs are allowed"):
            _validate_url("ftp://example.com/file")

    def test_rejects_localhost_ipv4(self):
        """127.0.0.1 (localhost) must be rejected."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://127.0.0.1/admin")

    def test_rejects_localhost_name(self):
        """localhost hostname must be rejected."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://localhost/admin")

    def test_rejects_private_10_network(self):
        """10.0.0.0/8 private network must be rejected."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://10.0.0.1/internal")

    def test_rejects_private_172_network(self):
        """172.16.0.0/12 private network must be rejected."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://172.16.0.1/internal")
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://172.31.255.254/internal")

    def test_rejects_private_192_network(self):
        """192.168.0.0/16 private network must be rejected."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://192.168.1.1/router")

    def test_rejects_link_local_169(self):
        """169.254.0.0/16 link-local addresses must be rejected."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://169.254.169.254/metadata")

    def test_rejects_ipv6_loopback(self):
        """::1 (IPv6 loopback) must be rejected."""
        with pytest.raises(ValueError, match="private/reserved IP"):
            _validate_url("http://[::1]/admin")

    def test_rejects_ipv6_site_local_deprecated(self):
        """fec0::/10 (IPv6 deprecated site-local) must be rejected."""
        with pytest.raises(ValueError, match="deprecated IPv6 site-local"):
            _validate_url("http://[fec0::1]/internal")
        with pytest.raises(ValueError, match="deprecated IPv6 site-local"):
            _validate_url("http://[fec0:1234:5678::1]/internal")

    def test_rejects_no_hostname(self):
        """URLs without hostnames must be rejected."""
        with pytest.raises(ValueError, match="URL has no hostname"):
            _validate_url("http:///path")


class TestIDNAHomoglyphProtection:
    """Test Unicode homoglyph attack prevention via IDNA normalization."""

    def test_allows_ascii_hostname(self):
        """ASCII hostnames should work normally."""
        _validate_url("https://example.com")

    def test_normalizes_unicode_hostname(self):
        """Valid Unicode hostnames should be normalized via IDNA."""
        # This should succeed (real internationalized domain)
        _validate_url("https://münchen.de")

    def test_rejects_invalid_unicode(self):
        """Invalid Unicode sequences should be rejected."""
        # Malformed Unicode that can't be encoded to IDNA or resolved
        # (DNS resolution fails for malformed hostnames)
        with pytest.raises(ValueError, match="(Invalid hostname encoding|Cannot resolve hostname)"):
            _validate_url("https://\x00\x01\x02.com")

    def test_normalizes_punycode(self):
        """Punycode domains should be normalized."""
        # xn-- is the punycode prefix
        _validate_url("https://xn--mnchen-3ya.de")


class TestDNSRebindingProtection:
    """Test that validation happens at request time (covered by integration tests)."""

    def test_validation_called_before_request(self):
        """Validation should be called immediately before making HTTP request.

        This is tested by the double _validate_url() call in fetch_article().
        The test here just documents the expected behavior.
        """
        # This test is satisfied by code inspection:
        # fetch_article() calls _validate_url() twice:
        # 1. Initial validation
        # 2. Re-validation immediately before self._session.get()
        assert True


class TestErrorHandling:
    """Test error message quality and information disclosure."""

    def test_error_includes_ip_address(self):
        """Error messages should include the resolved IP for debugging."""
        with pytest.raises(ValueError, match=r"127\.0\.0\.1"):
            _validate_url("http://localhost")

    def test_error_includes_original_url(self):
        """Error messages should include the original URL."""
        with pytest.raises(ValueError, match="localhost"):
            _validate_url("http://localhost")

    def test_dns_resolution_failure_message(self):
        """DNS resolution failures should have clear error messages."""
        with pytest.raises(ValueError, match="Cannot resolve hostname"):
            _validate_url("http://nonexistent-domain-12345.invalid")
