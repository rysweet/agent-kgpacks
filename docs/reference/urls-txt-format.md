# urls.txt Format and Conventions

Complete reference for the `urls.txt` file used to specify source URLs for knowledge packs.

## File Location

```
data/packs/<pack-name>/urls.txt
```

**Example:**

```
data/packs/langchain-expert/urls.txt
data/packs/openai-api-expert/urls.txt
data/packs/vercel-ai-sdk/urls.txt
data/packs/llamaindex-expert/urls.txt
data/packs/zig-expert/urls.txt
```

## File Format

Plain text. One URL or comment per line. No trailing whitespace requirements.

```
# This is a comment (full-line comment only)
https://example.com/docs/overview
https://example.com/docs/concepts/

# Another section comment
https://example.com/docs/api/
```

### Lines

| Type | Syntax | Description |
|------|--------|-------------|
| URL | `https://...` | A fully-qualified HTTPS URL to ingest |
| Comment | `# text` | Section header or explanatory note; ignored by build |
| Blank | (empty) | Visual separator; ignored by build |

### URL Rules

**Required:**

- Must begin with `https://` (HTTP is rejected)
- Must be a public URL reachable without authentication
- Must not contain private IP ranges or cloud metadata endpoints

**Prohibited:**

| Pattern | Example | Reason |
|---------|---------|--------|
| Plain HTTP | `http://example.com` | No cleartext transport |
| Localhost | `http://localhost:8080` | Not a public source |
| Private IP | `http://10.0.0.1/` | Not a public source |
| Cloud metadata | `http://169.254.169.254/` | SSRF risk |
| Credentials in URL | `https://user:pass@example.com/` | Secret exposure |
| API keys in query | `https://example.com?api_key=sk-…` | Secret exposure |

**Optional but recommended:**

- Trailing slash on directory-style URLs (`/docs/concepts/` not `/docs/concepts`)
- Ordering within a section from most general to most specific

## Comment Conventions

Comments serve as section headers. They appear in build logs when verbose logging is enabled.

**Preferred style:**

```
# Section Name - Optional Subtitle
```

**Examples from production packs:**

```
# Core Documentation
# How-To Guides
# How-To Guides - Additional Sub-Pages
# Tutorials - Additional Sub-Pages
# API Reference Sub-Categories
# GitHub - Raw Content & Source Files (reliable text extraction)
# Community Resources
```

Comments should describe the *category* of URLs that follow, not individual URLs. Per-URL comments are not supported.

## Canonical Hosts

Use the current canonical hostname. Do not use deprecated or unofficial mirrors.

| Pack | Canonical Host(s) | Notes |
|------|-------------------|-------|
| langchain-expert | `python.langchain.com` | Use this, NOT `docs.langchain.com` (dead) |
| langchain-expert | `docs.smith.langchain.com` | LangSmith observability — separate service, valid |
| openai-api-expert | `platform.openai.com` | Official API docs |
| openai-api-expert | `cookbook.openai.com`, `github.com/openai/openai-cookbook` | Cookbook examples |
| openai-api-expert | `openai.github.io/openai-agents-python` | Agents SDK docs |
| vercel-ai-sdk | `sdk.vercel.ai` | Official SDK docs |
| vercel-ai-sdk | `raw.githubusercontent.com/vercel/ai`, `github.com/vercel/ai` | Rate-limit fallback |
| llamaindex-expert | `docs.llamaindex.ai/en/stable` | Stable release docs |
| zig-expert | `ziglang.org` | Official language reference |
| zig-expert | `zig.guide` | Community tutorial, structured learning path |
| zig-expert | `ziglearn.org` | Community resource |

## GitHub URL Formats

GitHub URLs may appear in two forms, each serving a different extraction strategy:

### Blob URLs

```
https://github.com/owner/repo/blob/main/path/to/file.md
```

- Returns rendered HTML with file content
- Use for Markdown, Jupyter notebooks (`.ipynb`), and documentation files
- Jupyter notebooks: code cells and markdown cells are both extracted as text

### Raw URLs

```
https://raw.githubusercontent.com/owner/repo/main/path/to/file.md
```

- Returns raw file content (plain text, Markdown, etc.)
- Faster and more reliable for text extraction
- Preferred for Markdown and MDX files when both options are available

**Best practice:** include both `blob/` and `raw.githubusercontent.com/` variants for important files:

```
# GitHub - Raw Content & Source Files (reliable text extraction)
https://raw.githubusercontent.com/vercel/ai/main/README.md
https://github.com/vercel/ai/blob/main/README.md
```

## URL Count Guidelines

Minimum and recommended URL counts by pack complexity:

| Pack Complexity | Minimum URLs | Recommended URLs | Example |
|-----------------|-------------|------------------|---------|
| Focused library | 30 | 45–60 | `openai-api-expert` |
| Framework with integrations | 50 | 65–80 | `langchain-expert` |
| Full platform (RAG + agents) | 50 | 70–90 | `llamaindex-expert` |
| Language reference | 30 | 45–60 | `zig-expert` |
| TypeScript SDK | 35 | 45–55 | `vercel-ai-sdk` |

URL count does not equal article count. Build scripts may crawl additional linked pages; the `urls.txt` provides seed URLs only.

## Section Ordering

Recommended section order for a typical technology pack:

1. File header comment (technology name, topics covered, any important notes)
2. Core Documentation / Overview
3. Getting Started / Quickstart
4. Concepts / Architecture
5. How-To Guides (index + sub-pages)
6. Tutorials (index + sub-pages)
7. API Reference (index + sub-categories)
8. Integrations / Providers
9. GitHub (repository, README)
10. SDK / CLI Tools
11. Observability / Tooling
12. Community Resources

## Validation

The `scripts/validate_pack_urls.py` script checks all URLs in a pack file:

```bash
python scripts/validate_pack_urls.py --pack langchain-expert
```

**Checks performed:**

- HTTP GET returns 2xx status
- `Content-Type` is text-based (HTML, Markdown, plain text, JSON)
- URL matches allowed-hostname policy (rejects private IPs, localhost)
- No duplicate URLs within the file

**Output:**

```
Checking 71 URLs for langchain-expert...
  69 reachable
   2 unreachable
   0 duplicates

Unreachable:
  [404] https://python.langchain.com/docs/how_to/deprecated_example/
  [403] https://platform.openai.com/docs/internal-only-page

Action required: remove or replace unreachable URLs before rebuilding.
```

## Additive Changes Policy

When expanding an existing `urls.txt`:

- **Never remove** a URL that is currently reachable
- **Replace** only URLs that are confirmed dead (404, domain gone)
- **Add** new URLs by appending new section blocks at the end or inserting within the relevant existing section

This policy ensures that pack rebuilds always have at least as much source coverage as the previous build.

## Example: Complete urls.txt Structure

```
# LangChain Framework - Official Documentation
# Agents, chains, retrievers, prompts, embeddings, vector stores, LCEL
# NOTE: Use python.langchain.com (NOT docs.langchain.com which is dead)

# Core Documentation
https://python.langchain.com/docs/concepts/
https://python.langchain.com/docs/concepts/architecture/
https://python.langchain.com/docs/concepts/agents/

# How-To Guides
https://python.langchain.com/docs/how_to/
https://python.langchain.com/docs/how_to/tool_calling/

# How-To Guides - Additional Sub-Pages
https://python.langchain.com/docs/how_to/custom_tools/
https://python.langchain.com/docs/how_to/agent_executor/

# Tutorials
https://python.langchain.com/docs/tutorials/
https://python.langchain.com/docs/tutorials/rag/

# Tutorials - Additional Sub-Pages
https://python.langchain.com/docs/tutorials/extraction/
https://python.langchain.com/docs/tutorials/sql_qa/

# API Reference
https://python.langchain.com/api_reference/core/index.html

# Integrations - Additional Categories
https://python.langchain.com/docs/integrations/llms/
https://python.langchain.com/docs/integrations/vectorstores/chroma/

# GitHub
https://github.com/langchain-ai/langchain

# LangSmith (Observability)
https://docs.smith.langchain.com/
```

## Related Documentation

- [How to Curate and Expand Pack URL Lists](../howto/curate-pack-urls.md)
- [Pack URL Coverage: Expanded Packs](../knowledge_packs/pack-url-coverage.md)
- [Web Content Source API Reference](./web-content-source.md)
