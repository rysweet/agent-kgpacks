# Pack Installer Security Reference

The `wikigr.packs.installer` module provides the `PackInstaller` class for installing,
uninstalling, and updating Knowledge Packs. This document describes its security model,
configuration constants, and full Python API.

---

## Security Model Overview

Pack archives can arrive from untrusted sources (public registries, third-party authors,
CI artefact stores). The installer applies multiple independent defences so that a
compromised or malicious archive cannot harm the host machine:

| Layer | Where | Threat mitigated |
|-------|-------|-----------------|
| Pack-name validation (`PACK_NAME_RE`) | `uninstall()`, `update()` entry points | Path traversal via caller-supplied name |
| HTTPS-only + private-IP rejection | `_url_validation.validate_download_url()` | SSRF, plain-text interception |
| DNS-bind download | `install_from_url()` | DNS rebinding (TOCTOU between validation and download) |
| Size limit + timeout | `install_from_url()` | Disk exhaustion, bandwidth DoS, hang |
| SHA-256 verification | `install_from_url()` optional | Tampered archive substitution |
| Archive member scan | `distribution.unpackage_pack()` | Zip-slip, symlink escapes |
| PEP 706 `filter='data'` | `distribution.unpackage_pack()` | setuid bits, device nodes, path normalisation |
| Path containment check | `distribution.unpackage_pack()` | Crafted `manifest.name` redirecting install path |
| World-writable directory warning | `PackInstaller.__init__()` | Privilege escalation via install_dir permissions |
| Source-URL HTTPS check | `manifest.validate_manifest()` | Non-HTTPS source provenance recorded in manifests |

---

## Class: `PackInstaller`

```python
from wikigr.packs.installer import PackInstaller
from pathlib import Path

installer = PackInstaller(install_dir=Path.home() / ".wikigr" / "packs")
```

### Class-level constants

| Constant | Default | Description |
|----------|---------|-------------|
| `PackInstaller.MAX_DOWNLOAD_BYTES` | `2_147_483_648` (2 GiB) | Maximum bytes accepted in a streaming download. Override on the class before constructing an instance to change the limit globally. |

**Example — lowering the limit in resource-constrained environments:**

```python
PackInstaller.MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024  # 512 MiB
installer = PackInstaller()
```

---

### `__init__`

```python
PackInstaller(install_dir: Path | None = None)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `install_dir` | `Path \| None` | `~/.wikigr/packs` | Base directory under which each pack gets its own subdirectory. |

**Side effects:**

After resolving `install_dir`, the constructor checks whether the directory is
*world-writable* (permission bit `o+w`, i.e. `stat & 0o002`). If it is, a
`warnings.warn` is emitted:

```
UserWarning: install_dir '/path/to/packs' is world-writable. Any local user
can replace pack files. Consider restricting permissions with:
  chmod o-w /path/to/packs
```

This is a warning, not an error, so existing automation is not broken. Operators
running shared systems should fix the directory permissions.

---

### `install_from_file`

```python
pack_info = installer.install_from_file(archive_path: Path) -> PackInfo
```

Install a pack from a local `.tar.gz` archive.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `archive_path` | `Path` | Local path to the `.tar.gz` pack archive |

**Returns:** `PackInfo` for the newly installed pack.

**Raises:**

| Exception | When |
|-----------|------|
| `FileNotFoundError` | `archive_path` does not exist |
| `tarfile.TarError` | Archive is corrupt or not a valid tar file |
| `ValueError` | Archive contains illegal paths, symlinks, or manifest validation fails |

---

### `install_from_url`

```python
pack_info = installer.install_from_url(
    url: str,
    *,
    expected_sha256: str | None = None,
    max_bytes: int | None = None,
    timeout: int = 30,
) -> PackInfo
```

Download and install a pack from an HTTPS URL.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | — | HTTPS URL of the `.tar.gz` pack archive |
| `expected_sha256` | `str \| None` | `None` | Hex digest of the expected SHA-256 hash of the archive. When supplied, the downloaded bytes are hashed and compared before installation proceeds. |
| `max_bytes` | `int \| None` | `None` | Per-call byte limit. When `None`, `PackInstaller.MAX_DOWNLOAD_BYTES` applies. |
| `timeout` | `int` | `30` | Connection and read timeout in seconds. |

**Security behaviour — DNS binding:**

`install_from_url` calls `validate_download_url()` to resolve the hostname and validate the
resulting IP address *once*. It then opens a direct TCP connection to that resolved IP
address (not to the hostname string) with the original hostname supplied in the `Host:`
HTTP header. This eliminates the DNS rebinding window that exists when validation and
download use separate DNS lookups.

For IPv6 addresses, the connection target is wrapped in square brackets as required by
RFC 7230 (`[::1]`).

!!! note "Proxy support"
    Because connections are made directly to the pre-resolved IP, system HTTP proxies
    configured via `HTTPS_PROXY` or `HTTP_PROXY` environment variables are **bypassed**.
    If your network requires a proxy for outbound HTTPS, use `install_from_file` with a
    separately downloaded archive instead.

**SHA-256 verification:**

When `expected_sha256` is supplied, the installer:

1. Streams the archive to a temporary file in 64 KiB chunks (up to `max_bytes`).
2. Computes `hashlib.sha256` incrementally over each chunk during the stream.
3. Compares the final hex digest to `expected_sha256` (case-insensitive).
4. Raises `ValueError` if the digests do not match — the temporary file is deleted and no pack files are written.
5. Calls `install_from_file` on the verified temporary file.

!!! note "Memory usage"
    The archive is streamed to a temporary file in 64 KiB chunks; the SHA-256 digest is
    computed incrementally over each chunk. Memory consumption is effectively constant
    regardless of archive size — only the hasher state (≈ 256 bytes) and one chunk buffer
    (64 KiB) are held in RAM at any time.

**Raises:**

| Exception | When |
|-----------|------|
| `ValueError` | URL is not HTTPS, hostname resolves to a private/reserved/loopback IP, DNS resolution fails (hostname not found), download exceeds `max_bytes`, or SHA-256 digest does not match `expected_sha256` |
| `http.client.HTTPException` | HTTP-level error during download |
| `socket.timeout` | Connection or read exceeded `timeout` seconds |
| `tarfile.TarError` | Downloaded bytes are not a valid tar archive |

**Example — basic:**

```python
installer = PackInstaller()
pack_info = installer.install_from_url(
    "https://registry.wikigr.com/packs/go-expert-1.2.0.tar.gz"
)
```

**Example — with SHA-256 verification (recommended):**

```python
pack_info = installer.install_from_url(
    "https://registry.wikigr.com/packs/go-expert-1.2.0.tar.gz",
    expected_sha256="e3b0c44298fc1c149afb…",  # from registry checksums page
)
```

**Example — tighter limits for constrained environments:**

```python
pack_info = installer.install_from_url(
    "https://cdn.example.com/packs/small-pack-1.0.0.tar.gz",
    max_bytes=128 * 1024 * 1024,  # 128 MiB
    timeout=60,
)
```

---

### `uninstall`

```python
removed = installer.uninstall(pack_name: str) -> bool
```

Remove an installed pack.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `pack_name` | `str` | Name of the pack to remove. Must match `PACK_NAME_RE`. |

**Returns:** `True` if the pack was found and removed; `False` if the pack was not installed.

**Raises:**

| Exception | When |
|-----------|------|
| `ValueError` | `pack_name` does not match `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$` |

The `ValueError` is raised *before* any filesystem operations, preventing path-traversal
attacks from reaching the directory tree.

---

### `update`

```python
pack_info = installer.update(pack_name: str, archive_path: Path) -> PackInfo
```

Replace an existing pack installation with a new archive, preserving the pack's
accumulated evaluation results.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `pack_name` | `str` | Name of the currently-installed pack to update. Must match `PACK_NAME_RE`. |
| `archive_path` | `Path` | Local path to the new `.tar.gz` archive |

**Returns:** `PackInfo` for the updated pack.

**Raises:**

| Exception | When |
|-----------|------|
| `ValueError` | `pack_name` does not match `PACK_NAME_RE` |
| `FileNotFoundError` | Pack is not currently installed, or `archive_path` does not exist |
| `tarfile.TarError` | `archive_path` is corrupt or not a valid tar file |
| `ValueError` | New archive fails manifest validation |

**Eval-result preservation — crash-resilient design:**

If the installed pack contains an `eval/results/` directory, `update()` backs it up to
a *sibling path on the same filesystem* before installing the new version:

```
~/.wikigr/packs/.eval-backup-<pack_name>/results/
```

Because the backup lives on the same filesystem as the install directory, the restore
from backup to the new `eval/results/` uses `shutil.move`. When the destination does not
yet exist, the underlying `os.rename` call is atomic and survives a mid-update process kill.
If a stale backup directory already exists (from a previously interrupted update),
`shutil.move` falls back to a copy-then-delete sequence, which is not atomic — clean up
stale `.eval-backup-<pack_name>` directories before retrying if this matters for your
deployment. A temporary directory in `/tmp` (the previous approach) would be lost
entirely if the process was killed after the old pack was removed but before the backup
was restored.

The backup directory is cleaned up only on *success*. If the update fails, the backup
remains and can be inspected manually.

!!! warning "Stale backups"
    If an update is interrupted and restarted, the existing backup directory is
    overwritten. Do not rely on the backup directory for long-term archival.

---

## Module: `wikigr.packs._url_validation`

### `validate_download_url`

```python
from wikigr.packs._url_validation import validate_download_url
import ipaddress

resolved_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = \
    validate_download_url(url: str)
```

Validate a URL for safe download and return the resolved IP address.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | `str` | URL to validate |

**Returns:**

- An `ipaddress.IPv4Address` or `ipaddress.IPv6Address` object representing the IP
  that the hostname resolved to, *or*
- `None` if DNS resolution fails (`socket.gaierror`) — the caller is responsible for
  treating a `None` return as a fatal error and raising an appropriate exception.

**Raises:**

| Exception | When |
|-----------|------|
| `ValueError` | Scheme is not `https` |
| `ValueError` | URL has no hostname |
| `ValueError` | Hostname resolves to a private, reserved, or loopback IP address |

`install_from_url` converts a `None` return into a `ValueError("DNS resolution failed for …")` before attempting the download, so callers of `install_from_url` never see a silent pass-through.

**Why the return value matters:**

`install_from_url` binds its download connection directly to this resolved IP to close
the DNS rebinding window. Callers that only want validation (and do not need the IP)
can ignore the return value.

```python
# Validation only
validate_download_url("https://registry.wikigr.com/packs/foo-1.0.tar.gz")

# Validation + IP binding
ip = validate_download_url("https://registry.wikigr.com/packs/foo-1.0.tar.gz")
if ip:
    # connect directly to ip, supplying Host: header separately
    ...
```

---

## Module: `wikigr.packs.manifest`

### `PACK_NAME_RE`

```python
from wikigr.packs.manifest import PACK_NAME_RE
import re

PACK_NAME_RE: re.Pattern = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
```

Compiled regular expression used to validate pack names throughout the installer and
manifest modules. A valid pack name:

- Starts with an alphanumeric character (`[a-zA-Z0-9]`)
- Continues with zero to 63 more characters from `[a-zA-Z0-9_-]`
- Total maximum length: **64 characters**

### `validate_manifest`

The `validate_manifest` function (see [Pack Manifest Reference](pack-manifest.md))
now enforces an additional rule on `source_urls`:

> Every entry in `source_urls` must use the `https://` scheme.

A manifest with HTTP or other non-HTTPS source URLs fails validation:

```python
errors = validate_manifest(manifest)
# errors → ["source_urls entry 0 must use https://, got: 'http://example.com'"]
```

This rule applies at manifest validation time, independently of the download-time
HTTPS check in `validate_download_url`. It ensures that provenance metadata recorded
in a published pack is itself HTTPS, even if the distribution archive was downloaded
from a different location.

---

## Security FAQ

**Q: What happens if a pack archive contains a symlink?**

Symlinks are rejected by `unpackage_pack` before any extraction begins. The check
iterates all archive members and raises `ValueError` on the first symlink or hard link
found. See [Pack Distribution Reference](pack-distribution.md) for details.

**Q: Can a crafted `manifest.name` (e.g. `../../etc`) escape the install directory?**

No. After extraction to a temporary directory, `unpackage_pack` resolves
`install_dir / manifest.name` and asserts it is contained within `install_dir.resolve()`.
A name that resolves outside raises `ValueError` before any `shutil.move` occurs.

**Q: Why is DNS rebinding a concern for pack downloads?**

Without IP binding, two DNS lookups occur: one in `validate_download_url` (validation)
and one inside `urllib.request.urlretrieve` (download). If an attacker controls the DNS
record and returns a public IP for the first lookup and a private IP for the second, the
validation passes but the download reaches an internal service. `install_from_url`
eliminates this window by resolving the hostname once, validating the IP, and connecting
directly to that IP for the download.

**Q: Does the SHA-256 check protect against a registry being compromised?**

Yes, provided the `expected_sha256` digest comes from a source independent of the
registry (e.g. a separate checksums file signed by the pack author, or pinned in your
CI configuration). If both the archive and the digest come from the same untrusted
registry, the check provides no additional protection.

**Q: Does `install_from_url` work through a corporate HTTP proxy?**

No. Because the download connects directly to the pre-resolved IP, `HTTPS_PROXY`/
`HTTP_PROXY` environment variables are ignored. Use `install_from_file` with an archive
downloaded via your proxy tooling instead.
