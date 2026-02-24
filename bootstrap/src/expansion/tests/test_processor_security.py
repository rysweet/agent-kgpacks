"""Security tests for processor.py - API key sanitization."""

from ..processor import _sanitize_error


class TestAPIKeySanitization:
    """Test that API keys and tokens are redacted from error messages."""

    def test_sanitizes_api_key_equals(self):
        """api_key=<value> should be redacted."""
        error = "Request failed: api_key=sk-abc123def456ghi789"
        sanitized = _sanitize_error(error)
        assert "sk-abc123def456ghi789" not in sanitized
        assert "api_key=***REDACTED***" in sanitized

    def test_sanitizes_api_key_colon(self):
        """api_key: <value> should be redacted."""
        error = "Configuration error: api_key: abc123def456ghi789jkl"
        sanitized = _sanitize_error(error)
        assert "abc123def456ghi789jkl" not in sanitized
        assert "api_key=***REDACTED***" in sanitized

    def test_sanitizes_bearer_token(self):
        """Bearer tokens should be redacted."""
        error = "Auth failed: bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        sanitized = _sanitize_error(error)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
        assert "bearer=***REDACTED***" in sanitized

    def test_sanitizes_authorization_header(self):
        """Authorization: Bearer <token> should be redacted."""
        error = "HTTP 401: Authorization: Bearer sk-1234567890abcdefghij"
        sanitized = _sanitize_error(error)
        assert "sk-1234567890abcdefghij" not in sanitized
        assert "Authorization: ***REDACTED***" in sanitized

    def test_sanitizes_secret_key(self):
        """secret_key=<value> should be redacted."""
        error = "Database error: secret_key=my_secret_12345678901234567890"
        sanitized = _sanitize_error(error)
        assert "my_secret_12345678901234567890" not in sanitized
        assert "secret_key=***REDACTED***" in sanitized

    def test_sanitizes_token_with_quotes(self):
        """Tokens in quotes should be redacted."""
        error = 'Failed: token="abc123def456ghi789jkl012"'
        sanitized = _sanitize_error(error)
        assert "abc123def456ghi789jkl012" not in sanitized
        assert "token=***REDACTED***" in sanitized

    def test_sanitizes_case_insensitive(self):
        """Sanitization should be case-insensitive."""
        error = "Error: API_KEY=abc123def456ghi789jkl012"
        sanitized = _sanitize_error(error)
        assert "abc123def456ghi789jkl012" not in sanitized
        assert "API_KEY=***REDACTED***" in sanitized

    def test_preserves_non_sensitive_content(self):
        """Non-sensitive parts of error messages should be preserved."""
        error = "Connection timeout after 30s"
        sanitized = _sanitize_error(error)
        assert sanitized == error

    def test_sanitizes_multiple_keys(self):
        """Multiple keys in same message should all be redacted."""
        error = "Config: api_key=key123456789012345678901, token=tok123456789012345678901"
        sanitized = _sanitize_error(error)
        assert "key123456789012345678901" not in sanitized
        assert "tok123456789012345678901" not in sanitized
        assert sanitized.count("***REDACTED***") == 2

    def test_sanitizes_minimum_length_key(self):
        """Keys must be at least 20 chars to avoid false positives."""
        # 20 chars - should be redacted
        error = "api_key=12345678901234567890"
        sanitized = _sanitize_error(error)
        assert "12345678901234567890" not in sanitized

        # 19 chars - should NOT be redacted (too short)
        error = "api_key=1234567890123456789"
        sanitized = _sanitize_error(error)
        assert "1234567890123456789" in sanitized

    def test_sanitizes_maximum_length_key(self):
        """Keys up to 128 chars should be redacted."""
        long_key = "a" * 128
        error = f"api_key={long_key}"
        sanitized = _sanitize_error(error)
        assert long_key not in sanitized
        assert "***REDACTED***" in sanitized

    def test_handles_special_characters(self):
        """Keys with hyphens and underscores should be redacted."""
        error = "token=sk-proj_abc123-def456_ghi789"
        sanitized = _sanitize_error(error)
        assert "sk-proj_abc123-def456_ghi789" not in sanitized


class TestSanitizationEdgeCases:
    """Test edge cases and corner cases."""

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert _sanitize_error("") == ""

    def test_only_whitespace(self):
        """Whitespace-only string should be preserved."""
        assert _sanitize_error("   \n\t  ") == "   \n\t  "

    def test_no_keys_present(self):
        """Messages without keys should pass through unchanged."""
        error = "Generic error message with no sensitive data"
        assert _sanitize_error(error) == error

    def test_malformed_key_patterns(self):
        """Malformed patterns should not crash."""
        error = "api_key="  # No value
        sanitized = _sanitize_error(error)
        # Should not crash, just return as-is
        assert "api_key" in sanitized


class TestRealWorldScenarios:
    """Test realistic error messages from actual API failures."""

    def test_openai_api_error(self):
        """OpenAI API error with API key should be sanitized."""
        error = (
            "OpenAI API Error: Authentication failed. "
            "API key 'sk-proj-abc123def456ghi789jkl012mno345' is invalid"
        )
        sanitized = _sanitize_error(error)
        assert "sk-proj-abc123def456ghi789jkl012mno345" not in sanitized
        assert "Authentication failed" in sanitized

    def test_http_request_exception(self):
        """HTTP request with Authorization header should be sanitized."""
        error = (
            "HTTPError 401: Unauthorized. "
            "Request headers: {'Authorization': 'Bearer eyJhbGc1234567890abcdefghijk'}"
        )
        sanitized = _sanitize_error(error)
        assert "eyJhbGc1234567890abcdefghijk" not in sanitized
        assert "401: Unauthorized" in sanitized

    def test_configuration_dump(self):
        """Config dumps with API keys should be sanitized."""
        error = (
            "Config validation failed: "
            '{"api_key": "sk-test1234567890abcdefghij", "endpoint": "https://api.example.com"}'
        )
        sanitized = _sanitize_error(error)
        assert "sk-test1234567890abcdefghij" not in sanitized
        assert "https://api.example.com" in sanitized

    def test_traceback_with_api_key(self):
        """Stack traces containing API keys should be sanitized."""
        error = (
            "Traceback (most recent call last):\n"
            '  File "client.py", line 42, in request\n'
            "    response = requests.get(url, headers={'api_key': 'sk-live-abc123def456ghi789jkl012'})\n"
            "RequestException: Connection refused"
        )
        sanitized = _sanitize_error(error)
        assert "sk-live-abc123def456ghi789jkl012" not in sanitized
        assert "Connection refused" in sanitized
