"""Shared utility functions for WikiGR."""

import re

# Pre-compiled patterns for sanitize_error (avoids re-compiling on every call)
_RE_API_KEY_SEP = re.compile(
    r"\b(api[_-]?key|token|secret[_-]?key|bearer|authorization)[=:\s]+['\"]?([a-zA-Z0-9_-]{20,128})['\"]?",
    re.IGNORECASE,
)
_RE_STANDALONE_KEY = re.compile(
    r"(['\"])(sk-[a-zA-Z0-9_-]{20,128}|[a-zA-Z0-9_-]{30,128})(['\"])",
)
_RE_AUTH_HEADER = re.compile(
    r"(Authorization:\s*)(Bearer\s+)?[a-zA-Z0-9_-]+",
    re.IGNORECASE,
)
_RE_DICT_API_KEY = re.compile(
    r'(["\']api[_-]?key["\']\s*:\s*["\'])([a-zA-Z0-9_-]{20,128})(["\'])',
    re.IGNORECASE,
)
_RE_JWT = re.compile(
    r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]*",
)
_RE_URL_CRED = re.compile(
    r"([?&](api[_-]?key|token|secret|access[_-]?token|auth)=)[a-zA-Z0-9_%-]{8,128}",
    re.IGNORECASE,
)
_RE_FILE_PATH = re.compile(
    r"(/(?:home|Users|tmp|var|etc|usr|opt|root)/[^\s:\"']+)",
)


def sanitize_error(error_msg: str) -> str:
    """Sanitize error messages to remove API keys, file paths, and sensitive tokens.

    Redacts common patterns:
    - API keys (alphanumeric strings 20-128 chars)
    - Bearer tokens
    - Authorization headers
    - Secret keys
    - JWT tokens
    - URL-embedded credentials
    - Absolute file paths

    Args:
        error_msg: Original error message

    Returns:
        Sanitized error message with sensitive data redacted
    """
    # Redact API keys with = or : separators
    sanitized = _RE_API_KEY_SEP.sub(r"\1=***REDACTED***", error_msg)

    # Redact standalone API keys (sk-..., long alphanumeric strings in quotes)
    sanitized = _RE_STANDALONE_KEY.sub(r"\1***REDACTED***\3", sanitized)

    # Redact Authorization headers
    sanitized = _RE_AUTH_HEADER.sub(r"\1***REDACTED***", sanitized)

    # Redact dict-style API keys {"api_key": "value"}
    sanitized = _RE_DICT_API_KEY.sub(r"\1***REDACTED***\3", sanitized)

    # Redact JWT tokens
    sanitized = _RE_JWT.sub("***REDACTED_JWT***", sanitized)

    # Redact URL-embedded credentials
    sanitized = _RE_URL_CRED.sub(r"\1***REDACTED***", sanitized)

    # Redact absolute file paths
    sanitized = _RE_FILE_PATH.sub("***REDACTED_PATH***", sanitized)

    return sanitized
