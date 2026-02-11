"""
Rate limiting configuration for WikiGR API.

Provides a shared Limiter instance used by all API endpoints.
Set WIKIGR_RATE_LIMIT_ENABLED=false to disable (e.g., in tests or CI).
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_enabled = os.environ.get("WIKIGR_RATE_LIMIT_ENABLED", "true").lower() != "false"

limiter = Limiter(key_func=get_remote_address, enabled=_enabled)
