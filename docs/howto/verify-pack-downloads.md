# How to Verify Pack Downloads

This guide explains how to install Knowledge Packs securely using SHA-256 checksum
verification and how to understand the other download-time protections that are active
by default.

---

## Why verification matters

When a pack archive travels over a network, it can be tampered with — even over HTTPS —
if the registry is compromised or if a man-in-the-middle attack strips TLS. Supplying an
`expected_sha256` checksum (obtained from a trusted, independent source) ties the
installed bytes to a specific, known-good archive.

---

## Step 1 — Obtain the checksum

Checksums for official packs are published alongside the download links. Typical sources:

- **Registry checksums page** — a separate file (e.g. `go-expert-1.2.0.tar.gz.sha256`)
  hosted on the registry.
- **Pack author's signed release notes** — a GPG-signed release with embedded digests.
- **CI configuration** — checksums pinned in your `pyproject.toml` or lockfile.

The checksum is a 64-character lowercase hex string, for example:

```
a3f5b2c1d8e4f709b0c2d3e4a5f6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4
```

---

## Step 2 — Install with verification

Pass the checksum as `expected_sha256` to `install_from_url`:

```python
from wikigr.packs.installer import PackInstaller

installer = PackInstaller()

pack_info = installer.install_from_url(
    "https://registry.wikigr.com/packs/go-expert-1.2.0.tar.gz",
    expected_sha256="a3f5b2c1d8e4f709b0c2d3e4a5f6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4",
)

print(f"Installed {pack_info.name} v{pack_info.version} to {pack_info.path}")
```

If the downloaded bytes do not match the expected digest, `ValueError` is raised and
**no files are written to disk**:

```
ValueError: SHA-256 mismatch for 'go-expert-1.2.0.tar.gz':
  expected: a3f5b2c1…
  got:      7f3e9d12…
```

---

## Step 3 — Verify the checksum file itself

For high-security environments, also verify the authenticity of the checksum source.
If the registry publishes GPG-signed checksum files:

```bash
# Download the archive and its detached signature
curl -O https://registry.wikigr.com/packs/go-expert-1.2.0.tar.gz
curl -O https://registry.wikigr.com/packs/go-expert-1.2.0.tar.gz.sha256
curl -O https://registry.wikigr.com/packs/go-expert-1.2.0.tar.gz.sha256.asc

# Verify the GPG signature on the checksum file
gpg --verify go-expert-1.2.0.tar.gz.sha256.asc go-expert-1.2.0.tar.gz.sha256

# Confirm the local archive matches
sha256sum -c go-expert-1.2.0.tar.gz.sha256

# Install from the locally verified archive
python - <<'EOF'
from pathlib import Path
from wikigr.packs.installer import PackInstaller

installer = PackInstaller()
pack_info = installer.install_from_file(Path("go-expert-1.2.0.tar.gz"))
print(f"Installed {pack_info.name} v{pack_info.version}")
EOF
```

---

## Default protections (always active)

Even without supplying `expected_sha256`, every call to `install_from_url` enforces:

### HTTPS-only

Plain HTTP URLs are rejected before any network connection is attempted:

```python
installer.install_from_url("http://example.com/pack.tar.gz")
# ValueError: Only HTTPS URLs allowed for downloads, got: 'http'
```

### Private-IP blocking (SSRF prevention)

The destination hostname is resolved and the resulting IP is checked. Connections to
private (`192.168.x.x`, `10.x.x.x`), reserved, and loopback (`127.0.0.1`) addresses
are blocked:

```python
installer.install_from_url("https://internal-registry.corp/pack.tar.gz")
# ValueError: Downloads from private/reserved IPs not allowed: 192.168.1.10
```

### DNS-bind download

The hostname is resolved *once*, the IP is validated, and the download connection is
made directly to that IP. This prevents DNS rebinding attacks where a second lookup
(inside the HTTP client) could return a different, private address.

### Size limit

Downloads are streamed and counted. If the response body exceeds
`PackInstaller.MAX_DOWNLOAD_BYTES` (default 2 GiB), the connection is closed and
`ValueError` is raised:

```python
installer.install_from_url("https://example.com/huge-pack.tar.gz")
# ValueError: Download exceeded 2147483648 bytes limit
```

Lower the limit for resource-constrained environments:

```python
PackInstaller.MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024  # 256 MiB
installer = PackInstaller()
```

### Connection timeout

The default timeout is 30 seconds for both connection establishment and read. Override
per call:

```python
installer.install_from_url(url, timeout=120)
```

---

## Using a proxy

`install_from_url` connects directly to the pre-resolved IP, bypassing system proxy
settings. If your network requires a proxy, download the archive separately and use
`install_from_file`:

```bash
# Download via proxy
https_proxy="http://proxy.corp:3128" \
  curl -O https://registry.wikigr.com/packs/go-expert-1.2.0.tar.gz

# Install the local file
python -c "
from pathlib import Path
from wikigr.packs.installer import PackInstaller
installer = PackInstaller()
info = installer.install_from_file(Path('go-expert-1.2.0.tar.gz'))
print(info.name, info.version)
"
```

---

## Updating a pack with verification

`update()` does not currently accept `expected_sha256` because it takes a local
`archive_path`. Download and verify the archive first, then update:

```python
import hashlib
from pathlib import Path
from wikigr.packs.installer import PackInstaller

archive = Path("go-expert-2.0.0.tar.gz")
expected = "b4e6f8a2…"

# Verify locally
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
if digest != expected:
    raise ValueError(f"Checksum mismatch: {digest!r} != {expected!r}")

installer = PackInstaller()
pack_info = installer.update("go-expert", archive)
print(f"Updated to {pack_info.version}")
```

---

## Pinning checksums in CI

Store pack checksums alongside your configuration so updates are deliberate and
auditable:

```toml
# pyproject.toml (or a dedicated packs.toml)

[tool.wikigr.packs]
"go-expert" = { version = "1.2.0", sha256 = "a3f5b2c1d8e4…" }
"python-expert" = { version = "3.1.0", sha256 = "d7c9e1a3f5b2…" }
```

Then in your CI install script:

```python
import tomllib
from pathlib import Path
from wikigr.packs.installer import PackInstaller

config = tomllib.loads(Path("pyproject.toml").read_text())
packs_cfg = config["tool"]["wikigr"]["packs"]
installer = PackInstaller()

for pack_name, spec in packs_cfg.items():
    url = f"https://registry.wikigr.com/packs/{pack_name}-{spec['version']}.tar.gz"
    installer.install_from_url(url, expected_sha256=spec["sha256"])
    print(f"Installed {pack_name} {spec['version']}")
```

---

## See also

- [Pack Installer Security Reference](../reference/pack-installer-security.md) — full API
  documentation for `PackInstaller`, `validate_download_url`, and related constants
- [Pack Distribution Reference](../reference/pack-distribution.md) — archive format and
  extraction safety (path validation, PEP 706 filter)
- [Pack Manifest Reference](../reference/pack-manifest.md) — `manifest.json` format and
  validation rules including the HTTPS `source_urls` requirement
