"""Tests for pack registry API client."""

import ipaddress
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from wikigr.packs.registry_api import PackListing, PackRegistryClient


class TestPackListing:
    """Test PackListing data model."""

    def test_pack_listing_creation(self):
        """Test creating PackListing instance."""
        listing = PackListing(
            name="physics-expert",
            version="1.0.0",
            description="Physics knowledge pack",
            author="WikiGR Team",
            download_url="https://registry.wikigr.com/packs/physics-expert-1.0.0.tar.gz",
            size_mb=50,
            downloads=1234,
        )

        assert listing.name == "physics-expert"
        assert listing.version == "1.0.0"
        assert listing.description == "Physics knowledge pack"
        assert listing.author == "WikiGR Team"
        assert listing.size_mb == 50
        assert listing.downloads == 1234


class TestPackRegistryClient:
    """Test PackRegistryClient (mocked for MVP)."""

    def test_client_initialization_default(self):
        """Test client initializes with default registry URL."""
        client = PackRegistryClient()
        assert client.registry_url == "https://registry.wikigr.com/api/v1"

    def test_client_initialization_custom(self):
        """Test client initializes with custom registry URL."""
        custom_url = "https://custom.registry.com/api"
        client = PackRegistryClient(registry_url=custom_url)
        assert client.registry_url == custom_url

    @patch("urllib.request.urlopen")
    def test_search_returns_listings(self, mock_urlopen):
        """Test search returns pack listings."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.read.return_value = b"""[
            {
                "name": "physics-expert",
                "version": "1.0.0",
                "description": "Physics knowledge",
                "author": "WikiGR",
                "download_url": "https://example.com/physics.tar.gz",
                "size_mb": 50,
                "downloads": 100
            },
            {
                "name": "biology-expert",
                "version": "2.0.0",
                "description": "Biology knowledge",
                "author": "WikiGR",
                "download_url": "https://example.com/biology.tar.gz",
                "size_mb": 75,
                "downloads": 200
            }
        ]"""
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = PackRegistryClient()
        results = client.search("physics")

        assert len(results) == 2
        assert results[0].name == "physics-expert"
        assert results[0].version == "1.0.0"
        assert results[1].name == "biology-expert"

    @patch("urllib.request.urlopen")
    def test_search_empty_results(self, mock_urlopen):
        """Test search with no results returns empty list."""
        mock_response = Mock()
        mock_response.read.return_value = b"[]"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = PackRegistryClient()
        results = client.search("nonexistent")

        assert results == []

    @patch("urllib.request.urlopen")
    def test_search_network_error(self, mock_urlopen):
        """Test search handles network errors."""
        mock_urlopen.side_effect = Exception("Network error")

        client = PackRegistryClient()
        with pytest.raises(Exception, match="Network error"):
            client.search("physics")

    @patch("urllib.request.urlopen")
    def test_get_pack_info(self, mock_urlopen):
        """Test get_pack_info returns pack details."""
        mock_response = Mock()
        mock_response.read.return_value = b"""{
            "name": "physics-expert",
            "version": "1.0.0",
            "description": "Physics knowledge pack",
            "author": "WikiGR Team",
            "download_url": "https://example.com/physics.tar.gz",
            "size_mb": 50,
            "downloads": 500
        }"""
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = PackRegistryClient()
        listing = client.get_pack_info("physics-expert")

        assert listing.name == "physics-expert"
        assert listing.version == "1.0.0"
        assert listing.downloads == 500

    @patch("urllib.request.urlopen")
    def test_get_pack_info_not_found(self, mock_urlopen):
        """Test get_pack_info raises error for nonexistent pack."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, None
        )

        client = PackRegistryClient()
        with pytest.raises(urllib.error.HTTPError):
            client.get_pack_info("nonexistent-pack")

    def _mock_https_conn(self, body: bytes = b"fake archive content", status: int = 200):
        """Build a mock HTTPSConnection that returns the given body on getresponse()."""
        mock_response = MagicMock()
        mock_response.status = status
        # Simulate chunked reads: return body on first read(), then b""
        read_calls = iter([body, b""])
        mock_response.read.side_effect = lambda sz=None: next(read_calls)

        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response
        return mock_conn

    @patch("wikigr.packs.registry_api.validate_download_url")
    @patch("wikigr.packs.registry_api.http.client.HTTPSConnection")
    def test_download_pack(self, mock_https_cls, mock_validate, tmp_path: Path):
        """Test download_pack downloads and returns path."""
        mock_validate.return_value = ipaddress.ip_address("93.184.216.34")
        mock_https_cls.return_value = self._mock_https_conn(b"fake archive content")

        # Mock get_pack_info to return download URL
        with patch.object(PackRegistryClient, "get_pack_info") as mock_get_info:
            mock_get_info.return_value = PackListing(
                name="physics-expert",
                version="1.0.0",
                description="Physics",
                author="WikiGR",
                download_url="https://example.com/physics-expert-1.0.0.tar.gz",
                size_mb=50,
                downloads=100,
            )

            client = PackRegistryClient()
            result_path = client.download_pack("physics-expert", "1.0.0")

            assert result_path.exists()
            assert result_path.name == "physics-expert-1.0.0.tar.gz"
            assert b"fake archive content" in result_path.read_bytes()

    @patch("wikigr.packs.registry_api.validate_download_url")
    @patch("wikigr.packs.registry_api.http.client.HTTPSConnection")
    def test_download_pack_latest_version(self, mock_https_cls, mock_validate, tmp_path: Path):
        """Test download_pack with 'latest' version."""
        mock_validate.return_value = ipaddress.ip_address("93.184.216.34")
        mock_https_cls.return_value = self._mock_https_conn(b"content")

        with patch.object(PackRegistryClient, "get_pack_info") as mock_get_info:
            mock_get_info.return_value = PackListing(
                name="test-pack",
                version="2.5.0",  # Latest version
                description="Test",
                author="Test",
                download_url="https://example.com/test-pack-2.5.0.tar.gz",
                size_mb=10,
                downloads=50,
            )

            client = PackRegistryClient()
            result_path = client.download_pack("test-pack", "latest")

            assert result_path.exists()
            # Should use actual version from registry, not "latest"
            assert "2.5.0" in result_path.name

    @patch("wikigr.packs.registry_api.validate_download_url")
    @patch("wikigr.packs.registry_api.http.client.HTTPSConnection")
    def test_download_pack_network_error(self, mock_https_cls, mock_validate):
        """Test download_pack handles network errors."""
        mock_validate.return_value = ipaddress.ip_address("93.184.216.34")
        mock_conn = MagicMock()
        mock_conn.request.side_effect = Exception("Download failed")
        mock_https_cls.return_value = mock_conn

        with patch.object(PackRegistryClient, "get_pack_info") as mock_get_info:
            mock_get_info.return_value = PackListing(
                name="test-pack",
                version="1.0.0",
                description="Test",
                author="Test",
                download_url="https://example.com/test.tar.gz",
                size_mb=10,
                downloads=50,
            )

            client = PackRegistryClient()
            with pytest.raises(Exception, match="Download failed"):
                client.download_pack("test-pack", "1.0.0")

    def test_search_constructs_correct_url(self):
        """Test search constructs correct API URL."""
        client = PackRegistryClient(registry_url="https://test.com/api")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b"[]"
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            client.search("test query")

            # Verify correct URL was called
            call_args = mock_urlopen.call_args[0][0]
            assert "https://test.com/api/search" in call_args.get_full_url()
            assert "test+query" in call_args.get_full_url()

    def test_get_pack_info_constructs_correct_url(self):
        """Test get_pack_info constructs correct API URL."""
        client = PackRegistryClient(registry_url="https://test.com/api")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b'{"name":"test","version":"1.0.0","description":"Test","author":"Test","download_url":"https://example.com","size_mb":10,"downloads":1}'
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_response

            client.get_pack_info("test-pack")

            # Verify correct URL was called
            call_args = mock_urlopen.call_args[0][0]
            assert "https://test.com/api/packs/test-pack" in call_args.get_full_url()
