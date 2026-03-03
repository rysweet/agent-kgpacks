# Pack Distribution Reference

The `wikigr.packs.distribution` module handles the packaging and unpackaging of
Knowledge Pack archives (`.tar.gz`). This document describes the archive format,
extraction safety model, and the public Python API.

---

## Archive Format

A pack archive is a gzip-compressed tar file with a flat structure rooted at the
pack directory. The archive contains:

| Path (relative to archive root) | Required | Description |
|---------------------------------|----------|-------------|
| `manifest.json` | Yes | Pack metadata (name, version, description, …) |
| `pack.db/` | Yes | Kuzu graph database directory |
| `skill.md` | Yes | Claude Code skill definition |
| `kg_config.json` | Yes | Knowledge graph build configuration |
| `README.md` | No | Human-readable documentation |
| `eval/` | No | Evaluation questions and results |

The following paths are excluded when packaging:

- `__pycache__/` directories and `.pyc` files
- Hidden files and directories (names starting with `.`)
- `cache/` directories
- Files with extensions `.tmp`, `.cache`, `.log`

---

## Extraction Safety

Pack archives may originate from untrusted sources (e.g. a registry or third-party
author). The `unpackage_pack` function applies three layers of protection:

### 1. Member path validation

Before extracting any bytes, every member in the archive is inspected:

- Members with absolute paths (starting with `/`) are rejected.
- Members containing `..` path components are rejected.
- Symbolic links and hard links are rejected.

Any violation raises `ValueError` and extraction is aborted before any files are written.

### 2. PEP 706 data filter (`filter='data'`)

`tar.extractall` is called with `filter='data'`, which applies Python's built-in
safe-extraction filter (standardised in [PEP 706](https://peps.python.org/pep-0706/)).
This filter:

- Strips `setuid`/`setgid` bits and device nodes
- Rejects members that would write outside the destination directory
- Normalises paths to prevent double-dot traversal that slips past simple string checks

This filter is required by Python 3.12+ to suppress the `DeprecationWarning` that
signals impending removal of the unsafe default behaviour in Python 3.14.

### 3. Extract-then-validate-then-move pattern

Extraction always lands in a temporary directory (`tempfile.TemporaryDirectory`).
The extracted content is validated against `validate_pack_structure` before being
moved to its final installation path. If validation fails, the temporary directory
is discarded automatically and the installation directory is never touched.

> **Path containment check (R-PT-1 — implemented):** After extracting the archive, the
> pack name is read from `manifest.json` (attacker-controlled content). The code asserts that
> `(install_dir / pack_name).resolve()` is contained within `install_dir.resolve()` before
> performing the `shutil.move`. A crafted manifest with a name such as `../../target` raises
> `ValueError: Pack name '...' resolves outside installation directory` and the move is aborted.

---

## Python API

### `package_pack`

```python
from wikigr.packs.distribution import package_pack
from pathlib import Path

archive_path = package_pack(
    pack_dir: Path,
    output_path: Path,
) -> Path
```

Create a `.tar.gz` archive from a pack directory.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `pack_dir` | `Path` | Source pack directory |
| `output_path` | `Path` | Destination path for the `.tar.gz` file |

**Returns:** `output_path` (the archive that was written).

**Raises:**

| Exception | When |
|-----------|------|
| `FileNotFoundError` | `pack_dir` does not exist |
| `ValueError` | Pack structure validation failed (missing required files) |

**Example:**

```python
from pathlib import Path
from wikigr.packs.distribution import package_pack

archive = package_pack(
    pack_dir=Path("data/packs/go-expert"),
    output_path=Path("dist/go-expert.tar.gz"),
)
print(f"Created {archive} ({archive.stat().st_size // 1024} KB)")
```

---

### `unpackage_pack`

```python
from wikigr.packs.distribution import unpackage_pack
from pathlib import Path

installed_path = unpackage_pack(
    archive_path: Path,
    install_dir: Path,
) -> Path
```

Extract and install a pack archive.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `archive_path` | `Path` | Path to the `.tar.gz` archive |
| `install_dir` | `Path` | Base installation directory (e.g. `~/.wikigr/packs`) |

**Returns:** `install_dir / manifest.name` — the final path of the installed pack.

**Raises:**

| Exception | When |
|-----------|------|
| `FileNotFoundError` | `archive_path` does not exist |
| `tarfile.TarError` | Archive is corrupt or not a valid tar file |
| `ValueError` | Archive contains illegal paths, symlinks, or fails pack validation |

**Side effects:**
- Creates `install_dir` if it does not exist.
- If a pack with the same name is already installed, it is replaced (the old
  directory is removed with `shutil.rmtree` before the new one is moved in).

**Example:**

```python
from pathlib import Path
from wikigr.packs.distribution import unpackage_pack

installed = unpackage_pack(
    archive_path=Path("dist/go-expert.tar.gz"),
    install_dir=Path.home() / ".wikigr" / "packs",
)
print(f"Installed to {installed}")
```

---

## CLI equivalent

The `wikigr pack` commands use these functions internally:

```bash
# Package a local pack directory
wikigr pack package data/packs/go-expert --output dist/go-expert.tar.gz

# Install a pack from an archive
wikigr pack install dist/go-expert.tar.gz
```

See [CLI Commands](cli-commands.md) for the full command reference.
