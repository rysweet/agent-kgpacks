"""
Rate limiting configuration for WikiGR API.

Provides a shared Limiter instance used by all API endpoints.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
