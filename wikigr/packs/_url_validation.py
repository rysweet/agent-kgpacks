# File: wikigr/packs/_url_validation.py
"""URL validation for pack downloads -- SSRF prevention.

Validates that download URLs use HTTPS and do not target private/reserved IPs.
"""

import ipaddress
import socket
from urllib.parse import urlparse


def validate_download_url(
    url: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Validate URL before download -- SSRF prevention.

    Ensures the URL uses HTTPS and does not resolve to a private, reserved,
    or loopback IP address.  Returns the resolved IP so the caller can connect
    directly to it, eliminating the TOCTOU window between validation and download
    (DNS rebinding prevention).

    Args:
        url: The URL to validate.

    Returns:
        The resolved IP address on success, or None if DNS resolution failed.
        Callers should treat None as an error and raise ValueError before
        attempting any download.

    Raises:
        ValueError: If the URL scheme is not HTTPS, has no hostname,
                    or resolves to a private/reserved/loopback IP.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Only HTTPS URLs allowed for downloads, got: {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("URL must have a hostname")

    # Block private/reserved IPs; return the resolved IP for DNS-bind
    try:
        resolved_ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        if resolved_ip.is_private or resolved_ip.is_reserved or resolved_ip.is_loopback:
            raise ValueError(f"Downloads from private/reserved IPs not allowed: {resolved_ip}")
        return resolved_ip
    except socket.gaierror:
        return None  # DNS resolution failure -- caller converts to ValueError
