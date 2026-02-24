# Phase 4: Distribution & Installation System

This document describes the Phase 4 implementation of Knowledge Packs: the distribution and installation system.

## Overview

Phase 4 provides the infrastructure for packaging, distributing, and installing knowledge packs across systems. It enables:

- **Pack Packaging**: Create distributable `.tar.gz` archives from pack directories
- **Pack Installation**: Install packs from archives or URLs
- **Version Management**: Semantic versioning and compatibility checking
- **Pack Updates**: Update existing packs while preserving evaluation results
- **Registry API**: Client for future pack registry service

## Components

### 1. Distribution (`distribution.py`)

Functions for creating and extracting pack archives.

**Key Functions:**

- `package_pack(pack_dir: Path, output_path: Path) -> Path`
  - Creates `.tar.gz` archive from pack directory
  - Validates pack structure before packaging
  - Excludes cache files, `__pycache__`, hidden files
  - Preserves file permissions and directory structure

- `unpackage_pack(archive_path: Path, install_dir: Path) -> Path`
  - Extracts pack archive to installation directory
  - Validates extracted pack before finalizing
  - Uses atomic operations (extract to temp, then move)
  - Returns path to extracted pack

**Example:**

```python
from wikigr.packs import package_pack, unpackage_pack

# Package a pack
archive = package_pack(
    pack_dir=Path("./physics-expert"),
    output_path=Path("./physics-expert-1.0.0.tar.gz")
)

# Unpackage to install directory
pack_path = unpackage_pack(
    archive_path=archive,
    install_dir=Path.home() / ".wikigr/packs"
)
```

### 2. Installer (`installer.py`)

High-level API for managing pack installations.

**Key Class: `PackInstaller`**

```python
class PackInstaller:
    def __init__(self, install_dir: Path | None = None):
        """Initialize installer (default: ~/.wikigr/packs)."""

    def install_from_file(self, archive_path: Path) -> PackInfo:
        """Install pack from local .tar.gz file."""

    def install_from_url(self, url: str) -> PackInfo:
        """Download and install pack from URL."""

    def uninstall(self, pack_name: str) -> bool:
        """Remove installed pack."""

    def update(self, pack_name: str, archive_path: Path) -> PackInfo:
        """Update pack while preserving eval results."""
```

**Example:**

```python
from wikigr.packs import PackInstaller

installer = PackInstaller()

# Install from file
pack_info = installer.install_from_file(Path("./physics-expert-1.0.0.tar.gz"))

# Install from URL
pack_info = installer.install_from_url("https://example.com/pack.tar.gz")

# Update pack (preserves eval results)
pack_info = installer.update("physics-expert", Path("./physics-expert-2.0.0.tar.gz"))

# Uninstall pack
installer.uninstall("physics-expert")
```

### 3. Versioning (`versioning.py`)

Semantic version comparison and compatibility checking.

**Key Functions:**

- `compare_versions(v1: str, v2: str) -> int`
  - Compare two semantic versions
  - Returns: `-1` (v1 < v2), `0` (equal), `1` (v1 > v2)
  - Supports pre-release and build metadata

- `is_compatible(required: str, installed: str) -> bool`
  - Check version compatibility
  - Same major version = compatible
  - Different major version = incompatible
  - Pre-release versions must match exactly

**Example:**

```python
from wikigr.packs import compare_versions, is_compatible

# Compare versions
compare_versions("2.0.0", "1.9.9")  # Returns 1 (newer)
compare_versions("1.0.0", "1.0.0")  # Returns 0 (equal)

# Check compatibility
is_compatible("1.0.0", "1.5.0")  # True (same major version)
is_compatible("1.0.0", "2.0.0")  # False (different major version)
```

### 4. Registry API Client (`registry_api.py`)

Client for interacting with pack registry service (future).

**Key Classes:**

- `PackListing`: Metadata about a pack in the registry
  - `name`, `version`, `description`, `author`
  - `download_url`, `size_mb`, `downloads`

- `PackRegistryClient`: Client for registry API
  - `search(query: str) -> list[PackListing]`
  - `get_pack_info(name: str) -> PackListing`
  - `download_pack(name: str, version: str) -> Path`

**Example:**

```python
from wikigr.packs import PackRegistryClient

client = PackRegistryClient()

# Search packs
results = client.search("physics")
for pack in results:
    print(f"{pack.name} v{pack.version} - {pack.description}")

# Get pack info
pack_info = client.get_pack_info("physics-expert")

# Download pack
archive = client.download_pack("physics-expert", "1.0.0")
```

**Note:** For MVP, the registry backend is not implemented. This provides the client interface that will be used when the registry service becomes available.

## Archive Format

Pack archives (`.tar.gz`) contain:

**Required files:**
- `manifest.json` - Pack metadata
- `pack.db/` - Kuzu database directory
- `skill.md` - Skill definition
- `kg_config.json` - Knowledge graph configuration

**Optional files:**
- `README.md` - Documentation
- `eval/` - Evaluation questions and results

**Excluded from archives:**
- `__pycache__/` - Python bytecode
- `.*/` - Hidden files/directories
- `cache/` - Cache directory
- `*.tmp`, `*.cache`, `*.log` - Temporary files

## Installation Workflow

1. **Download/Locate Archive**: Get `.tar.gz` file (local or from URL)
2. **Validation**: Validate pack structure before installing
3. **Atomic Extraction**: Extract to temp directory first
4. **Final Installation**: Move to install directory (atomic operation)
5. **PackInfo Creation**: Return metadata about installed pack

## Update Workflow

Updating packs preserves evaluation results:

1. **Check Existing Pack**: Verify pack is installed
2. **Backup Eval Results**: Copy `eval/results/` to temp directory
3. **Install New Version**: Install new pack (overwrites old)
4. **Restore Eval Results**: Copy eval results back
5. **Return Updated PackInfo**: Return metadata for new version

## Version Compatibility Rules

Following semantic versioning:

- **Major version**: Breaking changes (1.x.x → 2.x.x)
  - Incompatible with different major versions
- **Minor version**: New features, backwards compatible (1.0.x → 1.1.x)
  - Compatible within same major version
- **Patch version**: Bug fixes (1.0.0 → 1.0.1)
  - Compatible within same major version

**Pre-release versions** (e.g., `1.0.0-alpha`):
- Must match exactly for compatibility
- Incompatible with stable releases

**Build metadata** (e.g., `1.0.0+build123`):
- Ignored for comparison and compatibility

## Testing

All components have comprehensive test coverage:

- **`test_distribution.py`**: 13 tests for packaging/unpackaging
- **`test_installer.py`**: 15 tests for installation workflow
- **`test_versioning.py`**: 15 tests for version management
- **`test_registry_api.py`**: 13 tests for registry client

**Total: 56 tests, all passing**

Run tests:

```bash
uv run pytest tests/packs/test_distribution.py -v
uv run pytest tests/packs/test_installer.py -v
uv run pytest tests/packs/test_versioning.py -v
uv run pytest tests/packs/test_registry_api.py -v
```

## Examples

Phase 4 includes example scripts demonstrating all functionality:

1. **`package_example_pack.py`**
   - Package a pack into distributable archive
   - Show archive contents and size

2. **`install_from_archive.py`**
   - Install pack from archive file
   - Display pack information and statistics

3. **`update_pack.py`**
   - Update existing pack to newer version
   - Preserve evaluation results

4. **`version_compatibility_check.py`**
   - Version comparison examples
   - Compatibility checking scenarios
   - Dependency resolution patterns

Run examples:

```bash
# Package a pack
python wikigr/packs/examples/package_example_pack.py

# Install from archive
python wikigr/packs/examples/install_from_archive.py

# Update pack
python wikigr/packs/examples/update_pack.py

# Version compatibility
python wikigr/packs/examples/version_compatibility_check.py
```

## Integration with Other Phases

**Phase 1 (Format & Manifest):**
- Uses `PackManifest` for metadata
- Validates packs with `validate_pack_structure()`

**Phase 2 (Skills Integration):**
- Installs skill files (`skill.md`)
- Integrates with pack discovery system

**Phase 3 (Evaluation Framework):**
- Preserves eval results during updates
- Includes eval directories in archives

**Phase 5 (CLI Commands - Future):**
- Will provide command-line interface:
  - `wikigr pack install <archive>`
  - `wikigr pack update <name>`
  - `wikigr pack search <query>`

## Future Enhancements

### Registry Service Backend

The registry API client is ready, but requires backend implementation:

- **Pack upload/publishing**: Allow users to publish packs
- **Version management**: Multiple versions per pack
- **Search indexing**: Full-text search across pack metadata
- **Download statistics**: Track pack downloads and popularity
- **Authentication**: User accounts and API keys

### Additional Features

- **Digital signatures**: Verify pack authenticity
- **Delta updates**: Download only changed files
- **Pack dependencies**: Declare and resolve dependencies
- **Automatic updates**: Check for updates periodically
- **Pack collections**: Bundle multiple packs together

## Summary

Phase 4 provides a complete distribution and installation system for knowledge packs:

✅ Pack packaging into distributable archives
✅ Pack installation from files or URLs
✅ Semantic versioning and compatibility checking
✅ Pack updates with eval result preservation
✅ Registry API client (ready for backend)
✅ Comprehensive test coverage (56 tests)
✅ Example scripts for all functionality

The system is production-ready and provides the foundation for a full pack ecosystem. The registry backend is the next step to enable community-driven pack sharing.
