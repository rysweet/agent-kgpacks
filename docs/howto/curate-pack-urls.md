# How to Curate and Expand Pack URL Lists

Add, verify, and organise source URLs for an existing knowledge pack to improve coverage and retrieval quality.

## Problem

A pack's `urls.txt` has too few source pages, uses dead or redirect-heavy URLs, or is missing entire documentation sections (how-to guides, tutorials, API reference sub-categories, integration pages). Retrieval quality suffers because the knowledge graph lacks breadth.

## Solution

Audit the current `urls.txt`, identify coverage gaps, add authoritative URLs by section, and validate that all URLs remain reachable before rebuilding.

## Before You Start

- Identify which pack you are expanding: `data/packs/<pack-name>/urls.txt`
- Know the canonical documentation host for that technology (see [Pack URL Conventions](../reference/urls-txt-format.md#canonical-hosts))
- Have network access to verify URLs are reachable

## Step 1 — Audit Existing URLs

Count URLs and review section coverage:

```bash
# Count non-comment, non-blank lines
grep -v '^\s*#' data/packs/langchain-expert/urls.txt | grep -v '^\s*$' | wc -l

# List sections (comment headers)
grep '^\s*#' data/packs/langchain-expert/urls.txt
```

**Coverage checklist for typical documentation sites:**

- [ ] Root/overview page
- [ ] Concepts / architecture
- [ ] Getting started / quickstart
- [ ] How-to guides (top-level + key sub-pages)
- [ ] Tutorials (top-level + individual tutorials)
- [ ] API reference (top-level + major sub-categories)
- [ ] Integrations or providers (top-level + popular ones)
- [ ] GitHub repository / README
- [ ] Community resources (if applicable)

## Step 2 — Identify Canonical Hosts

Always use the current canonical hostname. Some documentation sites have moved:

| Pack | Canonical Host | Dead / Deprecated Host |
|------|----------------|------------------------|
| langchain-expert | `python.langchain.com` | `docs.langchain.com` (dead) |
| openai-api-expert | `platform.openai.com` | `beta.openai.com` (redirects) |
| vercel-ai-sdk | `sdk.vercel.ai` | `vercel-sdk.com` (unofficial) |
| llamaindex-expert | `docs.llamaindex.ai/en/stable` | `gpt-index.readthedocs.io` (dead) |
| zig-expert | `ziglang.org`, `zig.guide` | `ziglearn.org` (still live, community) |

If the canonical site returns 4xx or rate-limits heavily, add GitHub alternatives:

```
# Primary
https://sdk.vercel.ai/docs/ai-sdk-core/overview

# GitHub fallback (reliable text extraction)
https://raw.githubusercontent.com/vercel/ai/main/packages/ai/README.md
https://github.com/vercel/ai/blob/main/content/docs/01-ai-sdk-core/01-overview.mdx
```

## Step 3 — Add URLs by Section

Edit `urls.txt` using comment headers to group URLs by documentation section. Keep one URL per line.

### Add How-To Sub-Pages (LangChain example)

```
# How-To Guides - Additional Sub-Pages
https://python.langchain.com/docs/how_to/custom_tools/
https://python.langchain.com/docs/how_to/agent_executor/
https://python.langchain.com/docs/how_to/multi_vector/
https://python.langchain.com/docs/how_to/document_loader_csv/
https://python.langchain.com/docs/how_to/document_loader_pdf/
https://python.langchain.com/docs/how_to/recursive_text_splitter/
https://python.langchain.com/docs/how_to/output_parser_json/
https://python.langchain.com/docs/how_to/streaming/
https://python.langchain.com/docs/how_to/callbacks_runtime/
https://python.langchain.com/docs/how_to/few_shot_examples/
https://python.langchain.com/docs/how_to/message_history/
```

### Add Tutorial Sub-Pages (LangChain example)

```
# Tutorials - Additional Sub-Pages
https://python.langchain.com/docs/tutorials/extraction/
https://python.langchain.com/docs/tutorials/qa_chat_history/
https://python.langchain.com/docs/tutorials/summarization/
https://python.langchain.com/docs/tutorials/classification/
https://python.langchain.com/docs/tutorials/sql_qa/
https://python.langchain.com/docs/tutorials/local_rag/
```

### Add API Reference Sub-Categories (LlamaIndex example)

```
# API Reference Sub-Categories
https://docs.llamaindex.ai/en/stable/api_reference/llms/
https://docs.llamaindex.ai/en/stable/api_reference/embeddings/
https://docs.llamaindex.ai/en/stable/api_reference/indices/
https://docs.llamaindex.ai/en/stable/api_reference/query/
https://docs.llamaindex.ai/en/stable/api_reference/storage/
https://docs.llamaindex.ai/en/stable/api_reference/readers/
https://docs.llamaindex.ai/en/stable/api_reference/node_parsers/
```

### Add GitHub Alternatives for 403-Heavy Sites (OpenAI example)

Some cookbook or documentation pages return 403 to crawlers. Add GitHub blob or `raw.githubusercontent.com` equivalents:

```
# Cookbook - Specific Examples (GitHub alternatives bypass 403 blocks)
https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models
https://github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb
https://github.com/openai/openai-cookbook/blob/main/examples/How_to_format_inputs_to_ChatGPT_models.ipynb
https://github.com/openai/openai-cookbook/blob/main/examples/How_to_stream_completions.ipynb
```

### Add Community Resources (Zig example)

For languages with thin official documentation, community guides carry significant weight:

```
# Community Resources
https://ziglearn.org/
https://zig.guide/language-basics/assignment/
https://zig.guide/standard-library/allocators/
https://zig.guide/standard-library/hashmaps/
https://zig.guide/standard-library/threads/
```

## Step 4 — Validate Reachability

Run the URL validator against the modified pack before rebuilding:

```bash
python scripts/validate_pack_urls.py --pack langchain-expert
```

Expected output:

```
Checking 71 URLs for langchain-expert...
  71 reachable
   0 unreachable
   0 redirects (followed automatically)
OK
```

For any failures, either remove the URL or replace it with an equivalent working source.

### Bulk Validation (All 5 Packs)

```bash
for pack in langchain-expert openai-api-expert vercel-ai-sdk llamaindex-expert zig-expert; do
  echo "=== $pack ==="
  python scripts/validate_pack_urls.py --pack "$pack"
done
```

## Step 5 — Rebuild the Pack

After validation, rebuild to ingest the new URLs:

```bash
python scripts/build_langchain_expert_pack.py
```

The build script reads `urls.txt`, fetches each page, and runs LLM extraction. New entities and relationships are added to the pack's knowledge graph.

## Step 6 — Update the Manifest

After the build completes, update `data/packs/<pack-name>/manifest.json` with the new article count:

```json
{
  "pack_name": "langchain-expert",
  "article_count": 71,
  "build_date": "2026-03-01",
  "source": "web"
}
```

## Step 7 — Evaluate Pack Quality

Run a single-pack evaluation to verify retrieval quality improved:

```bash
python scripts/eval_single_pack.py --pack langchain-expert
```

Compare the accuracy score against the pre-expansion baseline recorded in `data/packs/langchain-expert/eval/`.

## Rules for URLs

- **HTTPS only** — no `http://` links
- **No private addresses** — no `localhost`, `127.0.0.1`, `10.x`, `192.168.x`, or cloud metadata endpoints (`169.254.169.254`)
- **No authentication** — all URLs must be publicly accessible without credentials
- **No secrets** — `urls.txt` must never contain API keys, tokens, or passwords in query parameters
- **Additive changes** — never remove a working URL when expanding a list; only add new ones

## Troubleshooting

### Site Returns 403 to Crawler

**Symptoms:** Validator reports the URL reachable in browser but 403 during build.

**Fix:** Add an equivalent GitHub blob or raw URL instead:

```
# Instead of:
https://docs.example.com/internal-guide/

# Add:
https://github.com/example-org/docs/blob/main/internal-guide.md
https://raw.githubusercontent.com/example-org/docs/main/internal-guide.md
```

### URL Redirects to Wrong Page

**Symptoms:** Article content extracted from the wrong page (e.g., root instead of sub-page).

**Fix:** Follow the redirect manually and update to the final canonical URL.

### Community Domain Risk

Third-party community sites (e.g., `zig.guide`, `ziglearn.org`) are not controlled by the language maintainers. Monitor these at build time. If a community domain becomes unavailable:

1. Remove its URLs from `urls.txt`
2. Verify official documentation at the canonical host provides equivalent coverage
3. Open an issue to track the domain change

## Related Documentation

- [urls.txt Format and Conventions](../reference/urls-txt-format.md)
- [Pack URL Coverage: Expanded Packs](../knowledge_packs/pack-url-coverage.md)
- [Web Content Source API Reference](../reference/web-content-source.md)
- [How to Configure LLM Extraction](./configure-llm-extraction.md)
