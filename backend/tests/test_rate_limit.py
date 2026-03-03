"""
Unit tests for backend/rate_limit.py — R-DOS-2 regression guard.

Covers:
  - _parse_trusted_proxies(): CIDR parsing, invalid entry warning, edge cases
  - _get_client_ip(): trusted proxy header honouring and spoofing prevention
"""

import ipaddress
import logging
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(client_host: str | None, forwarded_for: str | None = None) -> MagicMock:
    """Build a minimal mock Starlette Request."""
    request = MagicMock()
    if client_host is None:
        request.client = None
    else:
        request.client = MagicMock()
        request.client.host = client_host

    def _headers_get(name, default=""):
        if name == "X-Forwarded-For" and forwarded_for is not None:
            return forwarded_for
        return default

    request.headers.get = _headers_get
    return request


# ---------------------------------------------------------------------------
# Group 1 — _parse_trusted_proxies()
# ---------------------------------------------------------------------------


class TestParseTrustedProxies:
    """_parse_trusted_proxies() parses comma-separated IPs/CIDRs."""

    def _parse(self, raw: str):
        from backend.rate_limit import _parse_trusted_proxies

        return _parse_trusted_proxies(raw)

    def test_single_ipv4_address(self):
        result = self._parse("1.2.3.4")
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("1.2.3.4")

    def test_cidr_block(self):
        result = self._parse("10.0.0.0/8")
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("10.0.0.0/8")

    def test_comma_separated_mix(self):
        result = self._parse("1.2.3.4,10.0.0.0/8")
        assert len(result) == 2
        assert ipaddress.ip_network("1.2.3.4") in result
        assert ipaddress.ip_network("10.0.0.0/8") in result

    def test_invalid_entry_skipped_with_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="backend.rate_limit"):
            result = self._parse("1.2.3.4,not-an-ip")
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("1.2.3.4")
        assert any("not-an-ip" in record.message for record in caplog.records)

    def test_empty_string_returns_empty_list(self):
        result = self._parse("")
        assert result == []

    def test_whitespace_padded_entries(self):
        result = self._parse(" 1.2.3.4 ")
        assert len(result) == 1
        assert result[0] == ipaddress.ip_network("1.2.3.4")


# ---------------------------------------------------------------------------
# Group 2 — _get_client_ip()
# ---------------------------------------------------------------------------


class TestGetClientIp:
    """_get_client_ip() returns the correct IP given trusted proxy configuration."""

    def _call(self, request, trusted_networks):
        from backend.rate_limit import _get_client_ip

        with patch("backend.rate_limit._trusted_networks", trusted_networks):
            return _get_client_ip(request)

    def test_no_trusted_networks_returns_direct_ip(self):
        request = _make_request("203.0.113.5", forwarded_for="10.0.0.1")
        ip = self._call(request, [])
        assert ip == "203.0.113.5"

    def test_trusted_proxy_matching_honours_forwarded_for(self):
        request = _make_request("10.0.0.1", forwarded_for="203.0.113.5")
        trusted = [ipaddress.ip_network("10.0.0.0/8")]
        ip = self._call(request, trusted)
        assert ip == "203.0.113.5"

    def test_non_matching_source_ignores_forwarded_for(self):
        request = _make_request("198.51.100.7", forwarded_for="1.2.3.4")
        trusted = [ipaddress.ip_network("10.0.0.0/8")]
        ip = self._call(request, trusted)
        assert ip == "198.51.100.7"

    def test_multiple_hops_returns_leftmost(self):
        request = _make_request("10.0.0.1", forwarded_for="5.5.5.5, 10.0.0.1")
        trusted = [ipaddress.ip_network("10.0.0.0/8")]
        ip = self._call(request, trusted)
        assert ip == "5.5.5.5"

    def test_no_forwarded_for_header_returns_direct_ip(self):
        request = _make_request("10.0.0.1", forwarded_for=None)
        trusted = [ipaddress.ip_network("10.0.0.0/8")]
        ip = self._call(request, trusted)
        assert ip == "10.0.0.1"

    def test_client_none_returns_loopback(self):
        request = _make_request(None)
        ip = self._call(request, [ipaddress.ip_network("10.0.0.0/8")])
        assert ip == "127.0.0.1"
