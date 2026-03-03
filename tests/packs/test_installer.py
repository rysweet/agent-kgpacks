"""Tests for pack installer."""

import contextlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wikigr.packs.distribution import package_pack
from wikigr.packs.installer import PackInstaller
from wikigr.packs.manifest import EvalScores, GraphStats, PackManifest, save_manifest
from wikigr.packs.models import PackInfo


class TestPackInstaller:
    """Test PackInstaller class."""

    def create_test_pack_archive(
        self, tmp_path: Path, pack_name: str = "test-pack", version: str = "1.0.0"
    ) -> Path:
        """Create a test pack archive."""
        pack_dir = tmp_path / f"pack_source_{pack_name}_{version}"
        pack_dir.mkdir(exist_ok=True)

        # Create pack structure
        manifest = PackManifest(
            name=pack_name,
            version=version,
            description="Test knowledge pack",
            graph_stats=GraphStats(articles=100, entities=200, relationships=300, size_mb=10),
            eval_scores=EvalScores(accuracy=0.9, hallucination_rate=0.05, citation_quality=0.95),
            source_urls=["https://example.com"],
            created="2026-02-24T10:00:00Z",
            license="CC-BY-SA-4.0",
        )
        save_manifest(manifest, pack_dir)
        (pack_dir / "pack.db").mkdir()
        (pack_dir / "pack.db" / "data.kuzu").write_text("data")
        (pack_dir / "skill.md").write_text("# Test Skill\n\nSkill content")
        (pack_dir / "kg_config.json").write_text(json.dumps({"pack_name": pack_name}))

        # Package it
        archive_path = tmp_path / f"{pack_name}-{version}.tar.gz"
        package_pack(pack_dir, archive_path)

        return archive_path

    def test_installer_default_directory(self):
        """Test installer uses default directory."""
        installer = PackInstaller()
        assert installer.install_dir == Path.home() / ".wikigr/packs"

    def test_installer_custom_directory(self, tmp_path: Path):
        """Test installer with custom install directory."""
        custom_dir = tmp_path / "custom_packs"
        installer = PackInstaller(install_dir=custom_dir)
        assert installer.install_dir == custom_dir

    def test_install_from_file(self, tmp_path: Path):
        """Test installing pack from file."""
        archive_path = self.create_test_pack_archive(tmp_path)
        install_dir = tmp_path / "installed"

        installer = PackInstaller(install_dir=install_dir)
        pack_info = installer.install_from_file(archive_path)

        # Verify PackInfo
        assert isinstance(pack_info, PackInfo)
        assert pack_info.name == "test-pack"
        assert pack_info.version == "1.0.0"
        assert pack_info.path == install_dir / "test-pack"
        assert pack_info.skill_path == install_dir / "test-pack" / "skill.md"
        assert pack_info.manifest.name == "test-pack"

        # Verify installation
        assert (install_dir / "test-pack").exists()
        assert (install_dir / "test-pack" / "manifest.json").exists()
        assert (install_dir / "test-pack" / "pack.db").is_dir()
        assert (install_dir / "test-pack" / "skill.md").exists()

    def test_install_creates_install_directory(self, tmp_path: Path):
        """Test install creates installation directory if needed."""
        archive_path = self.create_test_pack_archive(tmp_path)
        install_dir = tmp_path / "new_dir" / "installed"

        installer = PackInstaller(install_dir=install_dir)
        pack_info = installer.install_from_file(archive_path)

        assert install_dir.exists()
        assert pack_info.path.exists()

    def test_install_overwrites_existing_pack(self, tmp_path: Path):
        """Test installing over existing pack replaces it."""
        archive_path = self.create_test_pack_archive(tmp_path)
        install_dir = tmp_path / "installed"

        installer = PackInstaller(install_dir=install_dir)

        # Install first time
        pack_info1 = installer.install_from_file(archive_path)
        install_time1 = (pack_info1.path / "manifest.json").stat().st_mtime

        # Install again (should replace)
        pack_info2 = installer.install_from_file(archive_path)
        install_time2 = (pack_info2.path / "manifest.json").stat().st_mtime

        assert pack_info1.path == pack_info2.path
        assert install_time2 >= install_time1

    def test_install_invalid_archive(self, tmp_path: Path):
        """Test installing invalid archive raises error."""
        archive_path = tmp_path / "invalid.tar.gz"
        archive_path.write_text("not a tar file")

        installer = PackInstaller(install_dir=tmp_path / "installed")

        import tarfile

        with pytest.raises((tarfile.TarError, ValueError)):
            installer.install_from_file(archive_path)

    def test_install_nonexistent_file(self, tmp_path: Path):
        """Test installing nonexistent file raises error."""
        archive_path = tmp_path / "nonexistent.tar.gz"
        installer = PackInstaller(install_dir=tmp_path / "installed")

        with pytest.raises(FileNotFoundError):
            installer.install_from_file(archive_path)

    def test_uninstall_existing_pack(self, tmp_path: Path):
        """Test uninstalling existing pack."""
        archive_path = self.create_test_pack_archive(tmp_path)
        install_dir = tmp_path / "installed"

        installer = PackInstaller(install_dir=install_dir)
        installer.install_from_file(archive_path)

        # Verify installed
        assert (install_dir / "test-pack").exists()

        # Uninstall
        result = installer.uninstall("test-pack")

        assert result is True
        assert not (install_dir / "test-pack").exists()

    def test_uninstall_nonexistent_pack(self, tmp_path: Path):
        """Test uninstalling nonexistent pack returns False."""
        installer = PackInstaller(install_dir=tmp_path / "installed")
        result = installer.uninstall("nonexistent-pack")

        assert result is False

    def test_update_pack(self, tmp_path: Path):
        """Test updating existing pack."""
        # Create and install v1.0.0
        archive_v1 = self.create_test_pack_archive(tmp_path, "test-pack", "1.0.0")
        install_dir = tmp_path / "installed"

        installer = PackInstaller(install_dir=install_dir)
        pack_info_v1 = installer.install_from_file(archive_v1)

        assert pack_info_v1.version == "1.0.0"

        # Create and update to v2.0.0
        archive_v2 = self.create_test_pack_archive(tmp_path, "test-pack", "2.0.0")
        pack_info_v2 = installer.update("test-pack", archive_v2)

        assert pack_info_v2.version == "2.0.0"
        assert pack_info_v2.path == pack_info_v1.path
        assert (install_dir / "test-pack" / "manifest.json").exists()

    def test_update_preserves_eval_results(self, tmp_path: Path):
        """Test updating pack preserves eval results."""
        # Create and install v1.0.0 with eval results
        archive_v1 = self.create_test_pack_archive(tmp_path, "test-pack", "1.0.0")
        install_dir = tmp_path / "installed"

        installer = PackInstaller(install_dir=install_dir)
        pack_info_v1 = installer.install_from_file(archive_v1)

        # Add eval results manually
        eval_dir = pack_info_v1.path / "eval" / "results"
        eval_dir.mkdir(parents=True)
        eval_file = eval_dir / "my_results.json"
        eval_file.write_text('{"score": 0.95}')

        # Update to v2.0.0
        archive_v2 = self.create_test_pack_archive(tmp_path, "test-pack", "2.0.0")
        installer.update("test-pack", archive_v2)

        # Verify eval results preserved
        assert eval_file.exists()
        assert eval_file.read_text() == '{"score": 0.95}'

    def test_uninstall_invalid_pack_name(self, tmp_path: Path):
        """Test uninstalling with invalid pack name raises ValueError."""
        installer = PackInstaller(install_dir=tmp_path / "installed")

        with pytest.raises(ValueError, match="invalid name!"):
            installer.uninstall("invalid name!")

    def test_update_invalid_pack_name(self, tmp_path: Path):
        """Test updating with invalid pack name raises ValueError."""
        archive_path = self.create_test_pack_archive(tmp_path)
        installer = PackInstaller(install_dir=tmp_path / "installed")

        with pytest.raises(ValueError, match="invalid name!"):
            installer.update("invalid name!", archive_path)

    def test_update_nonexistent_pack(self, tmp_path: Path):
        """Test updating nonexistent pack raises error."""
        archive_path = self.create_test_pack_archive(tmp_path)
        installer = PackInstaller(install_dir=tmp_path / "installed")

        with pytest.raises(FileNotFoundError):
            installer.update("nonexistent-pack", archive_path)

    def test_install_from_url(self, tmp_path: Path):
        """Test installing pack from URL."""
        import http.client
        import ipaddress

        # Create test archive
        archive_path = self.create_test_pack_archive(tmp_path)
        archive_data = archive_path.read_bytes()
        resolved_ip = ipaddress.IPv4Address("93.184.216.34")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [archive_data, b""]
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        # Install from URL
        installer = PackInstaller(install_dir=tmp_path / "installed")
        url = "https://example.com/packs/test-pack-1.0.0.tar.gz"

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", return_value=mock_conn),
        ):
            pack_info = installer.install_from_url(url)

        # Verify installation
        assert pack_info.name == "test-pack"
        assert pack_info.version == "1.0.0"
        assert pack_info.path.exists()

    def test_install_from_url_download_failure(self, tmp_path: Path):
        """Test install from URL handles download failure."""
        import http.client
        import ipaddress

        resolved_ip = ipaddress.IPv4Address("93.184.216.34")

        installer = PackInstaller(install_dir=tmp_path / "installed")
        url = "https://example.com/packs/test-pack-1.0.0.tar.gz"

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", side_effect=Exception("Network error")),
            pytest.raises(Exception, match="Network error"),
        ):
            installer.install_from_url(url)

    def test_install_from_url_invalid_archive(self, tmp_path: Path):
        """Test install from URL with invalid archive."""
        import http.client
        import ipaddress
        import tarfile

        resolved_ip = ipaddress.IPv4Address("93.184.216.34")
        invalid_data = b"not a valid tar file"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [invalid_data, b""]
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        installer = PackInstaller(install_dir=tmp_path / "installed")
        url = "https://example.com/packs/invalid.tar.gz"

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", return_value=mock_conn),
            pytest.raises((tarfile.TarError, ValueError)),
        ):
            installer.install_from_url(url)

    # --- TDD: Security hardening tests (GAP 1, GAP 2, GAP 3, world-writable, eval-backup) ---

    def test_max_download_bytes_constant_exists(self):
        """PackInstaller must expose MAX_DOWNLOAD_BYTES class constant (GAP 2)."""
        assert hasattr(PackInstaller, "MAX_DOWNLOAD_BYTES"), (
            "PackInstaller.MAX_DOWNLOAD_BYTES not found. "
            "Add it as a class-level constant for size-limit enforcement."
        )
        assert isinstance(PackInstaller.MAX_DOWNLOAD_BYTES, int)
        assert PackInstaller.MAX_DOWNLOAD_BYTES > 0

    def test_install_from_url_sha256_mismatch_raises_value_error(self, tmp_path: Path):
        """install_from_url() raises ValueError when expected_sha256 doesn't match (GAP 3)."""
        import http.client
        import ipaddress

        archive_path = self.create_test_pack_archive(tmp_path)
        installer = PackInstaller(install_dir=tmp_path / "installed")

        resolved_ip = ipaddress.IPv4Address("93.184.216.34")
        archive_data = archive_path.read_bytes()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [archive_data, b""]
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        wrong_sha256 = "0" * 64  # 64 hex zeros — guaranteed mismatch

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", return_value=mock_conn),
            pytest.raises(ValueError),
        ):
            installer.install_from_url(
                "https://example.com/packs/test-pack-1.0.0.tar.gz",
                expected_sha256=wrong_sha256,
            )

    def test_install_from_url_sha256_match_succeeds(self, tmp_path: Path):
        """install_from_url() succeeds when expected_sha256 matches the download (GAP 3)."""
        import hashlib
        import http.client
        import ipaddress

        archive_path = self.create_test_pack_archive(tmp_path)
        installer = PackInstaller(install_dir=tmp_path / "installed")

        resolved_ip = ipaddress.IPv4Address("93.184.216.34")
        archive_data = archive_path.read_bytes()
        correct_sha256 = hashlib.sha256(archive_data).hexdigest()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [archive_data, b""]
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", return_value=mock_conn),
        ):
            pack_info = installer.install_from_url(
                "https://example.com/packs/test-pack-1.0.0.tar.gz",
                expected_sha256=correct_sha256,
            )

        assert pack_info.name == "test-pack"
        assert pack_info.version == "1.0.0"

    def test_install_from_url_size_limit_exceeded_raises_value_error(self, tmp_path: Path):
        """install_from_url() raises ValueError when download exceeds MAX_DOWNLOAD_BYTES (GAP 2)."""
        import http.client
        import ipaddress

        installer = PackInstaller(install_dir=tmp_path / "installed")
        resolved_ip = ipaddress.IPv4Address("93.184.216.34")

        tiny_limit = 50  # bytes — override MAX_DOWNLOAD_BYTES for this test
        oversized_data = b"x" * (tiny_limit + 1)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [oversized_data, b""]
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", return_value=mock_conn),
            patch.object(PackInstaller, "MAX_DOWNLOAD_BYTES", tiny_limit),
            pytest.raises(ValueError, match=r"[Ss]ize|[Ll]imit|[Ll]arge|[Ee]xceed"),
        ):
            installer.install_from_url("https://example.com/packs/pack.tar.gz")

    def test_install_from_url_dns_bind_uses_resolved_ip(self, tmp_path: Path):
        """install_from_url() must connect to the pre-resolved IP, not the hostname (GAP 1).

        validate_download_url() resolves the hostname once and returns the IP.
        install_from_url() must then open its HTTP connection to that IP directly
        (with the original hostname in the Host header) to eliminate the TOCTOU
        window between DNS validation and the actual download (DNS rebinding attack).
        """
        import http.client
        import ipaddress

        archive_path = self.create_test_pack_archive(tmp_path)
        installer = PackInstaller(install_dir=tmp_path / "installed")

        resolved_ip = ipaddress.IPv4Address("93.184.216.34")
        archive_data = archive_path.read_bytes()

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [archive_data, b""]
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        connection_targets: list[str] = []

        def tracking_https_conn(host, **kwargs):
            connection_targets.append(host)
            return mock_conn

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", side_effect=tracking_https_conn),
            contextlib.suppress(Exception),
        ):
            installer.install_from_url("https://example.com/packs/test-pack-1.0.0.tar.gz")

        assert connection_targets, (
            "install_from_url() never called http.client.HTTPSConnection. "
            "DNS-bind not implemented: switch from urlretrieve to manual http.client flow."
        )
        assert connection_targets[0] == str(resolved_ip), (
            f"Expected connection to pre-resolved IP {resolved_ip}, "
            f"but connected to {connection_targets[0]!r}. "
            "The connection host must be the resolved IP, not the hostname."
        )

    def test_installer_warns_on_world_writable_install_dir(self, tmp_path: Path):
        """PackInstaller.__init__ must emit a warning when install_dir is world-writable."""
        import stat
        import warnings

        world_writable_dir = tmp_path / "world_writable"
        world_writable_dir.mkdir()
        original_mode = world_writable_dir.stat().st_mode
        world_writable_dir.chmod(original_mode | stat.S_IWOTH)

        try:
            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always")
                PackInstaller(install_dir=world_writable_dir)
        finally:
            world_writable_dir.chmod(original_mode)  # restore for cleanup

        assert caught_warnings, (
            "PackInstaller.__init__ emitted no warnings for a world-writable install_dir. "
            "Add a stat check and warnings.warn() call in __init__."
        )
        messages = [str(w.message) for w in caught_warnings]
        assert any(
            "world" in m.lower() or "writable" in m.lower() or "permission" in m.lower()
            for m in messages
        ), f"Expected world-writable warning, got: {messages}"

    def test_update_eval_backup_persists_in_sibling_dir_on_failure(self, tmp_path: Path):
        """When update() fails mid-way, the eval backup must survive in a sibling directory.

        The sibling path install_dir/.eval-backup-<pack_name>/ is on the same filesystem,
        so it survives a process kill. tempfile.TemporaryDirectory() is deleted by the
        context manager exit and does NOT survive a failure.
        """
        archive_v1 = self.create_test_pack_archive(tmp_path, "test-pack", "1.0.0")
        install_dir = tmp_path / "installed"
        installer = PackInstaller(install_dir=install_dir)
        pack_info = installer.install_from_file(archive_v1)

        # Add eval results so the backup path is triggered
        eval_dir = pack_info.path / "eval" / "results"
        eval_dir.mkdir(parents=True)
        (eval_dir / "my_results.json").write_text('{"score": 0.95}')

        archive_v2 = self.create_test_pack_archive(tmp_path, "test-pack", "2.0.0")
        expected_backup_dir = install_dir / ".eval-backup-test-pack"

        # Simulate a crash during install_from_file (mid-update)
        with (
            patch.object(
                installer, "install_from_file", side_effect=RuntimeError("simulated crash")
            ),
            pytest.raises(RuntimeError, match="simulated crash"),
        ):
            installer.update("test-pack", archive_v2)

        # After crash: backup must persist in the SIBLING path, not be deleted with a tempfile
        assert expected_backup_dir.exists(), (
            f"Expected backup dir {expected_backup_dir} to persist after failed update. "
            "Current impl uses tempfile.TemporaryDirectory() which is auto-deleted on exit. "
            "Switch to install_dir/.eval-backup-<pack_name>/ so it survives process kills."
        )
        assert (
            expected_backup_dir / "results" / "my_results.json"
        ).exists(), "Backup dir exists but does not contain the eval results"

    def test_update_eval_backup_removed_after_success(self, tmp_path: Path):
        """After a successful update(), the sibling backup dir must be cleaned up."""
        archive_v1 = self.create_test_pack_archive(tmp_path, "test-pack", "1.0.0")
        install_dir = tmp_path / "installed"
        installer = PackInstaller(install_dir=install_dir)
        pack_info = installer.install_from_file(archive_v1)

        # Add eval results so the backup path is triggered
        eval_dir = pack_info.path / "eval" / "results"
        eval_dir.mkdir(parents=True)
        (eval_dir / "my_results.json").write_text('{"score": 0.95}')

        archive_v2 = self.create_test_pack_archive(tmp_path, "test-pack", "2.0.0")
        expected_backup_dir = install_dir / ".eval-backup-test-pack"

        installer.update("test-pack", archive_v2)

        # After success: backup dir must be gone (cleaned up)
        assert not expected_backup_dir.exists(), (
            f"Expected backup dir {expected_backup_dir} to be cleaned up after successful update, "
            "but it still exists."
        )
        # And eval results must be preserved in the updated install
        assert (
            install_dir / "test-pack" / "eval" / "results" / "my_results.json"
        ).exists(), "Eval results were not preserved after successful update"

    def test_install_from_url_http_non200(self, tmp_path: Path):
        """HTTP non-200 status raises ValueError with the status code in the message."""
        import http.client
        import ipaddress

        installer = PackInstaller(install_dir=tmp_path / "installed")
        resolved_ip = ipaddress.IPv4Address("93.184.216.34")

        mock_response = MagicMock()
        mock_response.status = 404
        mock_conn = MagicMock()
        mock_conn.getresponse.return_value = mock_response

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", return_value=mock_conn),
            pytest.raises(ValueError, match="HTTP status 404"),
        ):
            installer.install_from_url("https://example.com/pack.tar.gz")

    def test_install_from_url_ipv6(self, tmp_path: Path):
        """IPv6 address is wrapped in brackets when passed to HTTPSConnection."""
        import http.client
        import ipaddress

        installer = PackInstaller(install_dir=tmp_path / "installed")
        resolved_ip = ipaddress.IPv6Address("::1")

        connection_targets: list[str] = []
        mock_conn = MagicMock()
        # Raise after the connection is opened so we can inspect the call args
        mock_conn.getresponse.side_effect = RuntimeError("stop after connect")

        def tracking_https_conn(host, **kwargs):
            connection_targets.append(host)
            return mock_conn

        with (
            patch("wikigr.packs.installer.validate_download_url", return_value=resolved_ip),
            patch.object(http.client, "HTTPSConnection", side_effect=tracking_https_conn),
            pytest.raises(RuntimeError, match="stop after connect"),
        ):
            installer.install_from_url("https://example.com/pack.tar.gz")

        assert connection_targets, "HTTPSConnection was never called"
        assert (
            connection_targets[0] == "[::1]"
        ), f"Expected IPv6 address wrapped in brackets '[::1]', got {connection_targets[0]!r}"
