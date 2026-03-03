# Pack Utilities API Reference

Reference documentation for `wikigr.packs.utils` — shared helper functions used by all knowledge pack build scripts.

## Overview

`wikigr/packs/utils.py` is the single source of truth for common operations shared across the 49+ build scripts in `scripts/`. It eliminates copy-paste drift between scripts and ensures consistent behaviour for URL loading, filtering, and logging.

All build scripts import `load_urls` from this module. Local definitions of `load_urls` inside individual scripts are not permitted — use the shared import.

## `load_urls`

```python
from wikigr.packs.utils import load_urls

def load_urls(urls_file: Path, limit: int | None = None) -> list[str]:
    ...
```

Reads a `urls.txt` file and returns a filtered list of URLs, skipping blank lines and `#` comments.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `urls_file` | `pathlib.Path` | — | Path to the `urls.txt` file to read. Must exist; raises `FileNotFoundError` otherwise. |
| `limit` | `int \| None` | `None` | If set and truthy, truncates the result to the first `limit` URLs. Intended for test-mode builds. A value of `0` is falsy and treated as no limit. |

### Returns

`list[str]` — Filtered list of URL strings. Each entry:

- Has leading and trailing whitespace stripped.
- Starts with `"https://"` — plain `http://` URLs are silently dropped (SEC-01).
- Is not a `#` comment line.
- Is not a blank line.

Order is preserved from the file.

### Side Effects

Up to two `logging.INFO` messages are emitted via the module-level logger (`wikigr.packs.utils`):

1. `"Limited to N URLs for testing"` — emitted first, only when `limit` is truthy.
2. `"Loaded N URLs from <path>"` — always emitted last. When `limit` is truthy, `N` reflects the truncated count, not the total lines in the file.

### Raises

| Exception | When |
|-----------|------|
| `FileNotFoundError` | `urls_file` does not exist. |
| `PermissionError` | `urls_file` cannot be read by the current process. |
| `OSError` | Any other OS-level I/O failure. |

`load_urls` does **not** validate that URLs are reachable or well-formed. HTTPS is enforced at load time via the `startswith("https://")` filter. Use [`validate_download_url`](./pack-installer-security.md) or `scripts/validate_pack_urls.py` to check reachability and additional safety constraints (private IPs, cloud metadata endpoints, etc.).

### Filter Details

The function uses a generator expression with `itertools.islice` to strip, filter, and limit in a single pass:

```python
candidates = (
    stripped
    for line in f
    if (stripped := line.strip())        # skip blank lines
    and not stripped.startswith("#")      # skip comments
    and stripped.startswith("https://")  # HTTPS-only (SEC-01)
)
urls = list(islice(candidates, limit or None))
```

The `startswith("https://")` filter enforces HTTPS at parse time (SEC-01). Plain `http://` lines in `urls.txt` are silently dropped before they reach any network layer. This provides defence-in-depth alongside the SSRF guard in `WebContentSource` and `validate_download_url`, which re-validate each URL at fetch time.

---

## Usage

### Basic Usage

```python
from pathlib import Path
from wikigr.packs.utils import load_urls

urls_file = Path("data/packs/my-pack/urls.txt")
urls = load_urls(urls_file)

for url in urls:
    process(url)
```

### Test Mode (Limit URLs)

Build scripts accept `--test-mode` to process only the first few URLs:

```python
import argparse
from pathlib import Path
from wikigr.packs.utils import load_urls

parser = argparse.ArgumentParser()
parser.add_argument("--test-mode", action="store_true")
args = parser.parse_args()

urls_file = Path("data/packs/my-pack/urls.txt")
limit = 5 if args.test_mode else None
urls = load_urls(urls_file, limit=limit)
```

### Guard for Optional urls.txt

When a `urls.txt` may or may not exist (e.g. freshness checking over arbitrary pack directories), guard the call at the call site rather than passing a non-existent path:

```python
urls = load_urls(urls_file) if urls_file.exists() else []
```

This pattern is used in `scripts/check_pack_freshness.py`.

### Import Path

All build scripts resolve the project root and insert it into `sys.path` before importing:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from wikigr.packs.utils import load_urls  # noqa: E402
```

The `# noqa: E402` suppresses the `E402 module level import not at top of file` linter warning that results from the `sys.path` manipulation above.

---

## Logging Configuration

`load_urls` uses the standard library `logging` module. The logger name is `wikigr.packs.utils`.

To see `INFO`-level messages from `load_urls`, configure the root logger or the `wikigr` hierarchy:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Or more targeted:

```python
import logging
logging.getLogger("wikigr.packs.utils").setLevel(logging.INFO)
```

Build scripts that use `logging.basicConfig(level=logging.INFO, ...)` in their `main()` function will automatically surface these messages.

---

## Writing a New Build Script

When creating a new `scripts/build_<name>_pack.py`, follow this import pattern:

```python
#!/usr/bin/env python3
"""
Build <Name> Knowledge Pack from URLs.
...
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# ... other stdlib and third-party imports ...

os.environ["TOKENIZERS_PARALLELISM"] = "false"

sys.path.insert(0, str(Path(__file__).parent.parent))

import real_ladybug as kuzu  # noqa: E402

import wikigr.bootstrap  # noqa: E402
from wikigr.packs.utils import load_urls  # noqa: E402

PACK_NAME = "my-domain-expert"
URLS_FILE = Path(__file__).parent.parent / "data" / "packs" / PACK_NAME / "urls.txt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-mode", action="store_true")
    args = parser.parse_args()

    limit = 5 if args.test_mode else None
    urls = load_urls(URLS_FILE, limit=limit)

    for url in urls:
        build_from_url(url)
```

Do **not** define a local `def load_urls(...)` in new scripts. Use the shared import.

---

## Related

- [urls.txt Format and Conventions](./urls-txt-format.md) — Format rules for the `urls.txt` input file.
- [Pack Installer Security](./pack-installer-security.md) — `validate_download_url` for SSRF prevention before HTTP requests.
- [How to Build a Pack](../howto/build-a-pack.md) — End-to-end guide for creating and verifying a new knowledge pack.
- [How to Validate Pack URLs](../howto/curate-pack-urls.md) — Using `scripts/validate_pack_urls.py` to check URL reachability.
