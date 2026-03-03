"""
Rate limiting configuration for WikiGR API.

Provides a shared Limiter instance used by all API endpoints.
Set WIKIGR_RATE_LIMIT_ENABLED=false to disable (e.g., in tests or CI).

Set WIKIGR_TRUSTED_PROXIES=<IP1>,<CIDR1>,... (comma-separated IPs or CIDR
networks) to safely honour X-Forwarded-For from known reverse-proxy addresses
(R-DOS-2).  Without this variable the direct connection IP is always used,
preventing attackers from spoofing their source address via the header.
"""

import ipaddress
import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_enabled = os.environ.get("WIKIGR_RATE_LIMIT_ENABLED", "true").lower() != "false"

if not _enabled:
    logging.getLogger(__name__).warning(
        "Rate limiting is DISABLED (WIKIGR_RATE_LIMIT_ENABLED=false)"
    )


def _parse_trusted_proxies(raw: str) -> list:
    """Parse comma-separated IP addresses or CIDR networks into ip_network objects."""
    networks = []
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logging.getLogger(__name__).warning(
                "Invalid WIKIGR_TRUSTED_PROXIES entry ignored: %r", entry
            )
    return networks


_trusted_networks = _parse_trusted_proxies(os.environ.get("WIKIGR_TRUSTED_PROXIES", ""))


def _get_client_ip(request) -> str:
    """Return the real client IP.

    Honours X-Forwarded-For only when the direct connection comes from a
    configured trusted proxy network (WIKIGR_TRUSTED_PROXIES).  Falls back
    to the direct connection IP when no trusted proxies are configured or
    when the connection does not originate from a trusted proxy — preventing
    IP spoofing via header injection.
    """
    direct_host = request.client.host if request.client else "127.0.0.1"
    if _trusted_networks:
        try:
            direct_addr = ipaddress.ip_address(direct_host)
        except ValueError:
            return direct_host
        if any(direct_addr in net for net in _trusted_networks):
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            if forwarded_for:
                # Take the leftmost (original client) IP from the chain
                return forwarded_for.split(",")[0].strip()
    return direct_host


limiter = Limiter(
    key_func=_get_client_ip if _trusted_networks else get_remote_address,
    enabled=_enabled,
)
