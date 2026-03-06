# Build a Pack

Step-by-step instructions for building a new Knowledge Pack from scratch.

## Prerequisites

- Python 3.12+
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `ANTHROPIC_API_KEY` environment variable set
- Network access to fetch source URLs

## Step 1: Create the Pack Directory

```bash
PACK_NAME="my-domain-expert"
mkdir -p data/packs/${PACK_NAME}/eval
```

## Step 2: Create urls.txt

Create `data/packs/${PACK_NAME}/urls.txt` with the documentation URLs to ingest:

```
# My Domain Expert - Official Documentation
# Covers: core concepts, API reference, tutorials, guides

# Core Documentation
https://docs.example.com/overview
https://docs.example.com/concepts
https://docs.example.com/getting-started

# API Reference
https://docs.example.com/api/
https://docs.example.com/api/core-module
https://docs.example.com/api/utils-module

# How-To Guides
https://docs.example.com/guides/
https://docs.example.com/guides/authentication
https://docs.example.com/guides/deployment

# Tutorials
https://docs.example.com/tutorials/quickstart
https://docs.example.com/tutorials/advanced-usage

# GitHub
https://github.com/example/project
https://github.com/example/project/blob/main/README.md
```

!!! tip "URL quality checklist"
    - All URLs use `https://`
    - All URLs are publicly accessible
    - No duplicate URLs
    - No credentials or API keys in query parameters
    - Section headers (`#` comments) group related URLs

### Validate URLs

```bash
python scripts/validate_pack_urls.py data/packs/${PACK_NAME}/urls.txt
```

This checks that all URLs return HTTP 200 and serve text-based content.

## Step 3: Create a Build Script

Create `scripts/build_my_domain_expert_pack.py` using an existing script as a template. The simplest approach is to copy and modify an existing build script:

```bash
cp scripts/build_go_pack.py scripts/build_my_domain_expert_pack.py
```

Edit the copy to point to your pack's `urls.txt` and output directory. Key variables to change:

- `PACK_NAME`: Your pack's name
- `URLS_FILE`: Path to your `urls.txt`
- `OUTPUT_DIR`: Path to `data/packs/${PACK_NAME}`

### Shared `load_urls` Utility

All build scripts import `load_urls` from the shared utility module rather than defining it locally:

```python
sys.path.insert(0, str(Path(__file__).parent.parent))

from wikigr.packs.utils import load_urls  # noqa: E402
```

`load_urls` strips blank lines and `#` comments from `urls.txt`, enforces HTTPS-only filtering, and returns a plain list of URL strings. Pass `limit=5` for test mode (the standard test-mode limit):

```python
limit = 5 if test_mode else None
urls = load_urls(URLS_FILE, limit=limit)
```

Do **not** define a local `def load_urls(...)` in new scripts — use the shared import.

See [Pack Utilities API Reference](../reference/pack-utils.md) for full details.

### Exception Narrowing in `process_url()`

The `process_url()` function in every build script must catch only specific, recoverable exceptions. Broad `except Exception` handlers are not permitted.

**Required handler:**

```python
except (requests.RequestException, json.JSONDecodeError) as e:
    logger.error(f"Failed to process {url}: {e}")
    return False
```

- `requests.RequestException` — network timeouts, DNS failures, connection resets
- `json.JSONDecodeError` — malformed JSON in LLM extraction responses

All other exceptions (LadybugDB `RuntimeError`, embedding `OSError`, programming bugs like `AttributeError` or `TypeError`) are **not caught** in `process_url()`. They propagate to `build_pack()` and abort the build with a visible traceback. A corrupt partial database write is worse than a fast failure.

See [Handle Exceptions from WikiGR Components](./handle-exceptions.md) for the full exception contract.

### DB_PATH Safety Guard (Required)

Every build script's `build_pack()` function must include a safety guard before any `shutil.rmtree()` call. This prevents accidental deletion of data outside the `data/packs/` directory if `DB_PATH` is ever misconfigured:

```python
if DB_PATH.exists():
    # SEC-06: prevent deletion outside data/packs/
    if not str(DB_PATH).startswith("data/packs/"):
        raise ValueError(f"Unsafe DB_PATH: {DB_PATH}")
    shutil.rmtree(DB_PATH) if DB_PATH.is_dir() else DB_PATH.unlink()
```

The guard uses a string prefix check (`str(DB_PATH).startswith("data/packs/")`) rather than `resolve()`, which ensures it works correctly with relative paths as used throughout the build scripts.

**Important:** The guard must appear *before* the `shutil.rmtree` call, not after. Build scripts in which the guard follows `rmtree` fail the `test_db_path_assertion_precedes_rmtree_in_source` test.

## Step 4: Build the Pack

### Test Build (Subset of URLs)

```bash
echo "y" | uv run python scripts/build_my_domain_expert_pack.py --test-mode
```

Test mode processes only the first few URLs, completing in 5-10 minutes. Use this to verify the build pipeline works before committing to a full build.

### Full Build

```bash
echo "y" | uv run python scripts/build_my_domain_expert_pack.py
```

A full build processes all URLs. Depending on the number of URLs and page sizes, this takes 3-5 hours.

### What Happens During Build

1. **Fetch**: Each URL is downloaded and text content extracted
2. **Parse**: Content is split into sections by headings
3. **Extract**: Claude identifies entities, relationships, and facts from each section
4. **Embed**: BAAI/bge-base-en-v1.5 generates 768-dim vectors for each section
5. **Store**: Everything is written to a LadybugDB graph database

### Build Output

```
data/packs/my-domain-expert/
├── pack.db/            # LadybugDB graph database
├── manifest.json       # Pack metadata
├── urls.txt            # Source URLs
├── skill.md            # Claude Code skill description
└── kg_config.json      # Agent configuration
```

## Step 5: Verify the Build

Check the manifest to verify the build completed successfully:

```bash
cat data/packs/${PACK_NAME}/manifest.json | python -m json.tool
```

Look for:

- `graph_stats.articles` should roughly match your URL count
- `graph_stats.entities` should be non-zero
- `graph_stats.size_mb` should be reasonable (1-50 MB for most packs)

### Quick Query Test

Query the pack using the Python API:

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path=f"data/packs/{PACK_NAME}/pack.db",
    use_enhancements=True,
)

result = agent.query("What is the core concept of this domain?")
print(result["answer"])
print(f"Sources: {result['sources']}")
print(f"Query type: {result['query_type']}")
```

## Step 6: Generate Evaluation Questions

```bash
python scripts/generate_eval_questions.py --pack ${PACK_NAME} --count 50
```

This generates 50 questions distributed across difficulty levels and saves them to `data/packs/${PACK_NAME}/eval/questions.jsonl`.

!!! warning "Review generated questions"
    Auto-generated questions often test general knowledge that Claude already has. Review and replace generic questions with pack-specific ones. See [Improving Accuracy](../evaluation/improving-accuracy.md) for guidance.

## Step 7: Run Evaluation

```bash
# Quick check
uv run python scripts/eval_single_pack.py ${PACK_NAME} --sample 5

# Full evaluation
uv run python scripts/eval_single_pack.py ${PACK_NAME}
```

### Interpreting Results

| Delta (Pack - Training) | Meaning |
|----------------------------|---------|
| +5pp or more | Strong -- pack clearly adds value |
| +1pp to +5pp | Moderate -- investigate for further improvement |
| 0pp | Neutral -- pack matches training |
| Negative | Problem -- review content quality and questions |

## Step 8: Iterate

If results are unsatisfactory:

1. **Expand URLs**: Add more source pages to improve coverage
2. **Calibrate questions**: Replace generic questions with specific ones
3. **Rebuild**: Re-run the build script after URL changes
4. **Re-evaluate**: Run evaluation again to measure improvement

See [Improving Accuracy](../evaluation/improving-accuracy.md) for detailed improvement strategies.

## Using the CLI

Alternatively, you can use the `wikigr pack` CLI for pack lifecycle management:

```bash
# Create a pack (Wikipedia source)
wikigr pack create --name my-pack --topics topics.txt --target 500 --output ./output

# Validate pack structure
wikigr pack validate data/packs/${PACK_NAME}

# Install pack for Claude Code integration
cd data/packs && tar -czf ${PACK_NAME}.tar.gz ${PACK_NAME}
wikigr pack install ${PACK_NAME}.tar.gz

# List installed packs
wikigr pack list
```

See [CLI Commands](../reference/cli-commands.md) for the complete command reference.
