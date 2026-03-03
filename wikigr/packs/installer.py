# File: wikigr/packs/installer.py
"""Pack installer for installing, uninstalling, and updating packs.

This module provides the PackInstaller class for managing pack installations.
"""

import hashlib
import http.client
import ipaddress
import shutil
import stat
import tempfile
import warnings
from pathlib import Path
from urllib.parse import urlparse

from wikigr.packs._url_validation import validate_download_url
from wikigr.packs.distribution import unpackage_pack
from wikigr.packs.manifest import PACK_NAME_RE, load_manifest
from wikigr.packs.models import PackInfo

_CHUNK_SIZE: int = 65_536  # 64 KiB read buffer for streaming downloads


class PackInstaller:
    """Installer for knowledge packs.

    Handles installation, uninstallation, and updates of knowledge packs.

    Attributes:
        install_dir: Base directory for pack installations (default: ~/.wikigr/packs)
        MAX_DOWNLOAD_BYTES: Maximum bytes allowed for a single pack download (2 GiB).
    """

    MAX_DOWNLOAD_BYTES: int = 2_147_483_648  # 2 GiB

    def __init__(self, install_dir: Path | None = None):
        """Initialize pack installer.

        Args:
            install_dir: Base directory for pack installations.
                        Defaults to ~/.wikigr/packs if not specified.

        Warns:
            UserWarning: If install_dir exists and is world-writable.
        """
        self.install_dir = install_dir or (Path.home() / ".wikigr/packs")
        # Single stat() call instead of exists() + stat() (two syscalls → one).
        try:
            mode = self.install_dir.stat().st_mode
            if mode & stat.S_IWOTH:
                warnings.warn(
                    f"install_dir '{self.install_dir}' is world-writable. "
                    "This is a security misconfiguration that may allow unauthorized "
                    "pack modifications.",
                    stacklevel=2,
                )
        except FileNotFoundError:
            pass

    def _validate_pack_name(self, pack_name: str) -> None:
        """Raise ValueError if pack_name contains invalid characters."""
        if not PACK_NAME_RE.match(pack_name):
            raise ValueError(
                f"Pack name '{pack_name}' contains invalid characters. "
                "Only alphanumeric, hyphens, and underscores are allowed."
            )

    def install_from_file(self, archive_path: Path) -> PackInfo:
        """Install pack from .tar.gz file.

        Args:
            archive_path: Path to pack archive file

        Returns:
            PackInfo for installed pack

        Raises:
            FileNotFoundError: If archive doesn't exist
            ValueError: If pack validation fails
            tarfile.TarError: If archive is invalid
        """
        # Unpackage to install directory
        pack_path = unpackage_pack(archive_path, self.install_dir)

        # Load manifest and create PackInfo
        manifest = load_manifest(pack_path)
        pack_info = PackInfo(
            name=manifest.name,
            version=manifest.version,
            path=pack_path,
            manifest=manifest,
            skill_path=pack_path / "skill.md",
        )

        return pack_info

    def install_from_url(
        self,
        url: str,
        *,
        expected_sha256: str | None = None,
        max_bytes: int | None = None,
        timeout: int = 30,
    ) -> PackInfo:
        """Install pack from URL (download then install).

        Connects directly to the pre-resolved IP address returned by
        validate_download_url() to prevent DNS rebinding attacks.  Enforces a
        download size limit and optionally verifies a SHA-256 digest before
        installation.

        Args:
            url: HTTPS URL to pack archive (.tar.gz).
            expected_sha256: Optional hex-encoded SHA-256 digest of the archive.
                Comparison is case-insensitive. If provided, the download is
                rejected when the digest does not match (security best practice
                even when not required).
            max_bytes: Per-call byte limit override. When None,
                PackInstaller.MAX_DOWNLOAD_BYTES applies.
            timeout: Socket timeout in seconds for the HTTP connection (default 30).

        Returns:
            PackInfo for installed pack

        Raises:
            ValueError: If DNS resolution fails, the download exceeds the byte
                limit, or the SHA-256 digest does not match.
            http.client.HTTPException: If the HTTP request fails.
            FileNotFoundError: If downloaded file not found
        """
        # Validate URL and obtain the pre-resolved IP (SSRF + DNS-rebinding prevention)
        resolved_ip = validate_download_url(url)
        if resolved_ip is None:
            raise ValueError(
                f"DNS resolution failed for URL: {url}. "
                "Cannot download pack from an unresolvable hostname."
            )

        parsed = urlparse(url)
        hostname = parsed.hostname
        port = parsed.port or 443
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        # Connect to the pre-resolved IP — not the hostname — to prevent DNS rebinding.
        # Use the original hostname in the Host header for SNI and virtual hosting.
        if isinstance(resolved_ip, ipaddress.IPv6Address):
            ip_str = f"[{resolved_ip}]"
        else:
            ip_str = str(resolved_ip)

        conn = http.client.HTTPSConnection(ip_str, port=port, timeout=timeout)

        # Stream response directly to a temp file, enforce size limit,
        # and compute SHA-256 incrementally — avoids holding the full
        # archive in memory twice (chunks list + joined bytes).
        # The try/finally guarantees conn.close() even when exceptions occur
        # mid-download (size limit, network error, etc.).
        byte_limit = max_bytes if max_bytes is not None else self.MAX_DOWNLOAD_BYTES
        hasher = hashlib.sha256() if expected_sha256 is not None else None
        total_bytes = 0

        try:
            conn.request("GET", path, headers={"Host": hostname})
            response = conn.getresponse()

            if response.status != 200:
                raise ValueError(
                    f"Download failed with HTTP status {response.status} for URL: {url}"
                )

            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                while True:
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > byte_limit:
                        tmp_path.unlink(missing_ok=True)
                        raise ValueError(
                            f"Download size exceeded limit of {byte_limit} bytes "
                            f"for URL: {url}. Pack archive is too large."
                        )
                    if hasher is not None:
                        hasher.update(chunk)
                    tmp_file.write(chunk)
        finally:
            conn.close()

        # Verify SHA-256 digest when the caller supplies an expected value
        if hasher is not None:
            actual_sha256 = hasher.hexdigest()
            if actual_sha256.lower() != expected_sha256.lower():
                tmp_path.unlink(missing_ok=True)
                raise ValueError(
                    f"SHA-256 mismatch for URL: {url}. "
                    f"Expected {expected_sha256!r}, got {actual_sha256!r}. "
                    "The downloaded archive may have been tampered with."
                )

        try:
            return self.install_from_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def uninstall(self, pack_name: str) -> bool:
        """Remove installed pack.

        Args:
            pack_name: Name of pack to uninstall

        Returns:
            True if pack was uninstalled, False if pack wasn't installed

        Raises:
            ValueError: If pack_name is invalid
        """
        self._validate_pack_name(pack_name)
        pack_path = self.install_dir / pack_name

        if not pack_path.exists():
            return False

        # Remove pack directory
        shutil.rmtree(pack_path)
        return True

    def update(self, pack_name: str, archive_path: Path) -> PackInfo:
        """Update existing pack (preserves eval results).

        Eval results are backed up to a sibling directory
        (install_dir/.eval-backup-<pack_name>/) on the same filesystem before
        the old pack is replaced.  This ensures the backup survives a process
        kill during the update.  The backup is removed on success and left
        intact on failure so operators can recover results manually.

        Args:
            pack_name: Name of pack to update
            archive_path: Path to new pack archive

        Returns:
            PackInfo for updated pack

        Raises:
            FileNotFoundError: If pack not installed or archive doesn't exist
            ValueError: If pack_name is invalid or new pack validation fails
        """
        self._validate_pack_name(pack_name)
        pack_path = self.install_dir / pack_name

        if not pack_path.exists():
            raise FileNotFoundError(f"Pack not installed: {pack_name}")

        # Preserve eval results if they exist
        eval_results_dir = pack_path / "eval" / "results"

        if eval_results_dir.exists():
            # Back up to a sibling path on the same filesystem so the backup
            # survives a process kill (unlike tempfile.TemporaryDirectory).
            backup_dir = self.install_dir / f".eval-backup-{pack_name}"
            saved_results = backup_dir / "results"

            # Remove any stale backup from a previously interrupted update
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

            shutil.copytree(eval_results_dir, saved_results)

            # Install new version (replaces old installation).
            # On failure the exception propagates; backup is left intact
            # so operators can recover eval results manually.
            pack_info = self.install_from_file(archive_path)

            # Restore eval results into the new installation
            new_eval_dir = pack_info.path / "eval"
            new_eval_dir.mkdir(exist_ok=True)
            new_results_dir = new_eval_dir / "results"

            if new_results_dir.exists():
                shutil.rmtree(new_results_dir)

            shutil.copytree(saved_results, new_results_dir)

            # Clean up backup only on success
            shutil.rmtree(backup_dir)

            return pack_info
        else:
            # No eval results to preserve, just install new version
            return self.install_from_file(archive_path)
