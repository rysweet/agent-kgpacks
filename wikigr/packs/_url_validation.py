"""URL validation for pack downloads -- SSRF prevention.

Validates that download URLs use HTTPS and do not target private/reserved IPs.
"""

import ipaddress
import socket
from urllib.parse import urlparse


def validate_download_url(url: str) -> None:
    """Validate URL before download -- SSRF prevention.

    Ensures the URL uses HTTPS and does not resolve to a private, reserved,
    or loopback IP address.

    Args:
        url: The URL to validate.

    Raises:
        ValueError: If the URL scheme is not HTTPS, has no hostname,
                    or resolves to a private/reserved/loopback IP.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("https",):
        raise ValueError(f"Only HTTPS URLs allowed for downloads, got: {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("URL must have a hostname")

    # Block private/reserved IPs
    try:
        resolved_ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        if resolved_ip.is_private or resolved_ip.is_reserved or resolved_ip.is_loopback:
            raise ValueError(f"Downloads from private/reserved IPs not allowed: {resolved_ip}")
    except socket.gaierror:
        pass  # DNS resolution failure -- will fail at download time
