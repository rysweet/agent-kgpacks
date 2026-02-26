"""Tests for pack installer."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from wikigr.agent.distribution import package_pack
from wikigr.agent.installer import PackInstaller
from wikigr.agent.manifest import EvalScores, GraphStats, PackManifest, save_manifest
from wikigr.agent.models import PackInfo


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

    def test_update_nonexistent_pack(self, tmp_path: Path):
        """Test updating nonexistent pack raises error."""
        archive_path = self.create_test_pack_archive(tmp_path)
        installer = PackInstaller(install_dir=tmp_path / "installed")

        with pytest.raises(FileNotFoundError):
            installer.update("nonexistent-pack", archive_path)

    @patch("urllib.request.urlretrieve")
    def test_install_from_url(self, mock_urlretrieve, tmp_path: Path):
        """Test installing pack from URL."""
        # Create test archive
        archive_path = self.create_test_pack_archive(tmp_path)

        # Mock URL download to return our test archive
        def mock_download(url, filename):
            # Copy our test archive to the download location
            import shutil

            shutil.copy(archive_path, filename)
            return filename, None

        mock_urlretrieve.side_effect = mock_download

        # Install from URL
        installer = PackInstaller(install_dir=tmp_path / "installed")
        url = "https://example.com/packs/test-pack-1.0.0.tar.gz"
        pack_info = installer.install_from_url(url)

        # Verify installation
        assert pack_info.name == "test-pack"
        assert pack_info.version == "1.0.0"
        assert pack_info.path.exists()

        # Verify urlretrieve was called
        mock_urlretrieve.assert_called_once()

    @patch("urllib.request.urlretrieve")
    def test_install_from_url_download_failure(self, mock_urlretrieve, tmp_path: Path):
        """Test install from URL handles download failure."""
        # Mock download failure
        mock_urlretrieve.side_effect = Exception("Network error")

        installer = PackInstaller(install_dir=tmp_path / "installed")
        url = "https://example.com/packs/test-pack-1.0.0.tar.gz"

        with pytest.raises(Exception, match="Network error"):
            installer.install_from_url(url)

    def test_install_from_url_invalid_archive(self, tmp_path: Path):
        """Test install from URL with invalid archive."""
        # Create invalid file
        invalid_file = tmp_path / "invalid.tar.gz"
        invalid_file.write_text("not a valid tar file")

        with patch("urllib.request.urlretrieve") as mock_urlretrieve:

            def mock_download(url, filename):
                import shutil

                shutil.copy(invalid_file, filename)
                return filename, None

            mock_urlretrieve.side_effect = mock_download

            installer = PackInstaller(install_dir=tmp_path / "installed")
            url = "https://example.com/packs/invalid.tar.gz"

            import tarfile

            with pytest.raises((tarfile.TarError, ValueError)):
                installer.install_from_url(url)
