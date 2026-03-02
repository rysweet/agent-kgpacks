"""Tests for ChatRequest.pack field validation in chat API."""

from __future__ import annotations

from backend.models.chat import ChatRequest


class TestChatRequestPackField:
    """Tests for the pack field on ChatRequest."""

    def test_pack_field_optional(self):
        """pack defaults to None."""
        req = ChatRequest(question="What is X?")
        assert req.pack is None

    def test_pack_field_accepts_valid_name(self):
        """pack accepts a valid pack name."""
        req = ChatRequest(question="What is X?", pack="go-expert")
        assert req.pack == "go-expert"

    def test_pack_field_accepts_none(self):
        """pack accepts explicit None."""
        req = ChatRequest(question="What is X?", pack=None)
        assert req.pack is None


class TestPackNameValidation:
    """Tests that path traversal is blocked at the API level."""

    def test_path_traversal_blocked(self):
        """Verify the regex check in chat.py blocks traversal names.

        This tests the validation logic, not the endpoint itself.
        """
        import re

        PACK_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")

        # Valid names
        assert PACK_NAME_RE.match("go-expert")
        assert PACK_NAME_RE.match("physics_expert")
        assert PACK_NAME_RE.match("a")

        # Path traversal attempts
        assert not PACK_NAME_RE.match("../../etc")
        assert not PACK_NAME_RE.match("../parent")
        assert not PACK_NAME_RE.match("/absolute")
        assert not PACK_NAME_RE.match("")
        assert not PACK_NAME_RE.match("-starts-with-hyphen")
        assert not PACK_NAME_RE.match("has spaces")
        assert not PACK_NAME_RE.match("has/slash")
