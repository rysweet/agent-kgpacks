"""Pack registry API client for searching and downloading packs.

This module provides a client for interacting with the pack registry service.
For MVP, the registry backend is not implemented - this provides the interface
that will be used when the registry service is available.
"""

import json
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from wikigr.packs._url_validation import validate_download_url


@dataclass
class PackListing:
    """Information about a pack in the registry.

    Attributes:
        name: Pack name
        version: Pack version
        description: Human-readable description
        author: Pack author/maintainer
        download_url: URL to download pack archive
        size_mb: Pack size in megabytes
        downloads: Number of times pack has been downloaded
    """

    name: str
    version: str
    description: str
    author: str
    download_url: str
    size_mb: int
    downloads: int


class PackRegistryClient:
    """Client for pack registry service.

    Provides methods for searching packs, getting pack information,
    and downloading pack archives from the registry.

    Note: For MVP, this is a client-only implementation. The actual
    registry backend service is future work.

    Attributes:
        registry_url: Base URL of the registry API
    """

    def __init__(self, registry_url: str = "https://registry.wikigr.com/api/v1"):
        """Initialize registry client.

        Args:
            registry_url: Base URL of the registry API
        """
        self.registry_url = registry_url.rstrip("/")

    def search(self, query: str) -> list[PackListing]:
        """Search published packs.

        Args:
            query: Search query string

        Returns:
            List of matching pack listings

        Raises:
            urllib.error.URLError: If network request fails
        """
        # URL-encode query
        encoded_query = urllib.parse.quote_plus(query)
        url = f"{self.registry_url}/search?q={encoded_query}"

        # Make HTTP request
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Parse results into PackListing objects
        listings = []
        for item in data:
            listing = PackListing(
                name=item["name"],
                version=item["version"],
                description=item["description"],
                author=item["author"],
                download_url=item["download_url"],
                size_mb=item["size_mb"],
                downloads=item["downloads"],
            )
            listings.append(listing)

        return listings

    def get_pack_info(self, name: str) -> PackListing:
        """Get pack metadata from registry.

        Args:
            name: Pack name

        Returns:
            PackListing with pack information

        Raises:
            urllib.error.HTTPError: If pack not found (404) or other HTTP error
            urllib.error.URLError: If network request fails
        """
        url = f"{self.registry_url}/packs/{name}"

        request = urllib.request.Request(url)
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read().decode("utf-8"))

        return PackListing(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data["author"],
            download_url=data["download_url"],
            size_mb=data["size_mb"],
            downloads=data["downloads"],
        )

    def download_pack(self, name: str, version: str) -> Path:
        """Download pack archive.

        Args:
            name: Pack name
            version: Pack version (or "latest" for most recent version)

        Returns:
            Path to downloaded pack archive in temp directory

        Raises:
            urllib.error.URLError: If download fails
        """
        # Get pack info to get download URL
        pack_info = self.get_pack_info(name)

        # If version is "latest", use version from registry
        if version == "latest":
            version = pack_info.version

        # Create temp file for download
        temp_dir = Path(tempfile.gettempdir())
        output_path = temp_dir / f"{name}-{version}.tar.gz"

        # Validate URL before download (SSRF prevention)
        validate_download_url(pack_info.download_url)

        # Download pack archive
        urllib.request.urlretrieve(pack_info.download_url, output_path)

        return output_path
