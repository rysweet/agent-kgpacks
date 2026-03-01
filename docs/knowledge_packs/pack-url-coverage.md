# Pack URL Coverage: Expanded Packs

Source URL coverage for the five packs expanded in Issue 211 (Improvement 6). Each pack's `urls.txt` was audited and expanded to close documentation gaps that were limiting retrieval quality.

## Summary

| Pack | URLs Before | URLs After | Delta | Primary Canonical Host |
|------|-------------|------------|-------|------------------------|
| langchain-expert | 28 | 71 | +43 | `python.langchain.com` |
| openai-api-expert | 35 | 45 | +10 | `platform.openai.com` |
| vercel-ai-sdk | 38 | 45 | +7 | `sdk.vercel.ai` |
| llamaindex-expert | 28 | 74 | +46 | `docs.llamaindex.ai/en/stable` |
| zig-expert | 38 | 47 | +9 | `ziglang.org` + `zig.guide` |
| **Total** | **167** | **282** | **+115** | |

---

## langchain-expert (71 URLs)

**File:** `data/packs/langchain-expert/urls.txt`

### Coverage

| Section | URLs | Notes |
|---------|------|-------|
| Core concepts (16 pages) | 16 | agents, tools, models, retrievers, loaders, splitters, runnables, callbacks, streaming, embeddings, output parsers |
| How-to guides index + 20 sub-pages | 21 | tool calling, structured output, custom tools, agent executor, multi-vector, parent document retriever, Q&A sources/per-user, CSV/PDF loaders, recursive splitter, JSON/XML parsers, streaming, callbacks, multimodal, few-shot, message history, custom LLM |
| Tutorials index + 11 sub-pages | 12 | RAG, agents, chatbot, extraction, Q&A with chat history, summarization, classification, SQL Q&A, graph, local RAG, PDF Q&A |
| API reference (core, langchain, community) | 3 | |
| LangGraph | 1 | agent orchestration |
| Integrations (12 sub-pages) | 15 | providers, chat, vector stores, LLMs, document loaders, text embedding, retrievers, tools, memory, callbacks, OpenAI chat, Anthropic chat, Chroma, Pinecone, FAISS |
| GitHub repository | 1 | `github.com/langchain-ai/langchain` |
| LangSmith observability | 1 | `docs.smith.langchain.com` (separate service from deprecated `docs.langchain.com`) |
| LangChain Hub | 1 | `smith.langchain.com/hub` |

### Important Notes

- All URLs use `python.langchain.com` — the deprecated `docs.langchain.com` domain is not used anywhere in this pack
- `docs.smith.langchain.com` is retained; it is the LangSmith observability platform, a distinct service from the old LangChain docs site
- Integration sub-pages cover all major vector store providers (Chroma, Pinecone, FAISS) and both flagship model providers (OpenAI, Anthropic)

---

## openai-api-expert (45 URLs)

**File:** `data/packs/openai-api-expert/urls.txt`

### Coverage

| Section | URLs | Notes |
|---------|------|-------|
| Getting started (4 pages) | 4 | overview, quickstart, models, API reference introduction |
| API reference core (11 pages) | 11 | chat, chat/create, responses, embeddings, embeddings/create, fine-tuning, batch, images, audio, moderations, assistants |
| Guides (12 pages) | 12 | text generation, function calling, structured outputs, vision, embeddings, fine-tuning, batch, reasoning, prompt engineering, safety best practices, latency optimisation, production best practices |
| Migration and updates (3 pages) | 3 | migrate to responses, deprecations, changelog |
| Assistants (2 pages) | 2 | deep-dive, tools/function-calling |
| SDKs (2 repos) | 2 | `github.com/openai/openai-python`, `github.com/openai/openai-node` |
| Cookbook | 1 | `cookbook.openai.com` |
| OpenAI Agents SDK (2 pages) | 2 | `github.com/openai/openai-agents-python`, `openai.github.io/openai-agents-python/` |
| SDK README | 1 | `github.com/openai/openai-python/blob/main/README.md` |
| Cookbook examples (7 pages) | 7 | how-to function calling (cookbook.openai.com), assistants API overview (cookbook.openai.com), plus 5 GitHub notebook blobs |

### GitHub Notebook URLs

The 5 GitHub blob notebook URLs bypass 403 responses that the direct `cookbook.openai.com` crawler encounters on some machines:

```
github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb
github.com/openai/openai-cookbook/blob/main/examples/How_to_format_inputs_to_ChatGPT_models.ipynb
github.com/openai/openai-cookbook/blob/main/examples/How_to_stream_completions.ipynb
github.com/openai/openai-cookbook/blob/main/examples/Embedding_Wikipedia_articles_for_search.ipynb
github.com/openai/openai-cookbook/blob/main/examples/Fine-tuned_classification.ipynb
```

GitHub renders `.ipynb` files as HTML with code cells; the extractor parses both markdown and code cells as text.

---

## vercel-ai-sdk (45 URLs)

**File:** `data/packs/vercel-ai-sdk/urls.txt`

### Coverage

| Section | URLs | Notes |
|---------|------|-------|
| Core docs (5 pages) | 5 | root, foundations: overview, agents, prompts, streaming |
| AI SDK Core (8 pages) | 8 | generate-text, stream-text, generate-object, stream-object, embed, telemetry, settings, testing |
| Concepts (3 pages) | 3 | tools, middleware, AI RSC |
| AI SDK UI (5 pages) | 5 | overview, chatbot, chatbot with tool calling, completion, storing messages |
| Providers (5 pages) | 5 | OpenAI, Anthropic, Google Generative AI, Amazon Bedrock, Azure |
| Guides (5 pages) | 5 | guides index, RAG chatbot, multi-modal chatbot, o3, o1 |
| Cookbook and advanced (3 pages) | 3 | cookbook, advanced, custom provider |
| Reference (3 pages) | 3 | AI SDK Core, AI SDK UI, AI SDK RSC |
| GitHub (8 sources) | 8 | repository, raw README, blob README, packages/ai README, raw packages/ai README, AI SDK Core overview MDX blob, RAG chatbot MDX blob, RAG chatbot raw MDX |

### GitHub Fallback Sources

`sdk.vercel.ai` may rate-limit the build-time crawler under sustained load. The 7 GitHub raw/blob sources provide reliable text extraction as parallel fallbacks:

| URL Type | Purpose |
|----------|---------|
| `raw.githubusercontent.com/vercel/ai/main/README.md` | Root README (plain text) |
| `github.com/vercel/ai/blob/main/README.md` | Root README (rendered) |
| `github.com/vercel/ai/blob/main/packages/ai/README.md` | Core package README |
| `raw.githubusercontent.com/vercel/ai/main/packages/ai/README.md` | Core package README (plain text) |
| `github.com/vercel/ai/blob/main/content/docs/01-ai-sdk-core/01-overview.mdx` | AI SDK Core overview (MDX) |
| `github.com/vercel/ai/blob/main/content/docs/02-guides/01-rag-chatbot.mdx` | RAG chatbot guide (MDX) |
| `raw.githubusercontent.com/vercel/ai/main/content/docs/02-guides/01-rag-chatbot.mdx` | RAG chatbot guide (plain MDX) |

MDX files contain JSX component syntax. The LLM extractor handles partial text gracefully; Markdown prose is extracted even when JSX fragments are not fully parseable.

---

## llamaindex-expert (74 URLs)

**File:** `data/packs/llamaindex-expert/urls.txt`

### Coverage

| Section | URLs | Notes |
|---------|------|-------|
| Main documentation root | 1 | |
| Getting started (5 pages) | 5 | root, concepts, starter example local, installation, starter example, customisation |
| Understanding LlamaIndex (11 pages) | 11 | root, RAG, agent, putting it all together, evaluating, tracing & debugging, loading, indexing, querying, storing, workflows |
| Module guides root (8 top-level) | 8 | models/LLMs, models/embeddings, indexing, querying, loading, storing, evaluating, deploying |
| Module guides: LLM sub-pages (2) | 2 | usage pattern, local models |
| Module guides: querying sub-pages (4) | 4 | query engine, retriever, node postprocessors, response synthesisers |
| Module guides: loading sub-pages (4) | 4 | documents and nodes, connectors, node parsers, ingestion pipeline |
| Module guides: indexing sub-pages (3) | 3 | vector store index, document summary index, knowledge graph index |
| Module guides: storing sub-pages (3) | 3 | vector stores, docstores, index stores |
| Module guides: deploying sub-pages (3) | 3 | agents, chat engines, workflows |
| Optimising production (6 pages) | 6 | production RAG, building RAG from scratch, evaluation, basic strategies, advanced retrieval, agentic strategies |
| API reference (8 pages) | 8 | root, LLMs, embeddings, indices, query, storage, readers, node parsers |
| Examples (7 pages) | 7 | root, OpenAI agent, React agent with query engine, vector stores/SimpleIndexDemo, query engine/CustomRetrievers, chat engine, Langchain embeddings |
| Use cases (4 pages) | 4 | Q&A, agents, chatbots, multimodal |
| GitHub repository | 1 | `github.com/run-llama/llama_index` |
| Latest docs pointer | 1 | `docs.llamaindex.ai/en/latest/` |

### Path Stability

All paths use `/en/stable/` which is a stable redirect by convention across LlamaIndex releases. The `/en/latest/` URL is included as a single pointer for users who want to track unreleased changes.

---

## zig-expert (47 URLs)

**File:** `data/packs/zig-expert/urls.txt`

### Coverage

| Section | URLs | Notes |
|---------|------|-------|
| Official language reference (master + 0.13 + 0.14) | 4 | includes standard library doc pages |
| zig.guide language basics (18 pages) | 18 | assignment, arrays, comptime, optionals, error-union-type, payload-captures, functions, slices, enums, structs, unions, pointers, labelled-blocks, labelled-loops, while-loops, for-loops, if-expressions, switch |
| zig.guide standard library (8 pages) | 8 | allocators, arraylist, filesystem, formatting-and-printing, hashmaps, threads, readers-and-writers, json |
| zig.guide build system (2 pages) | 2 | build-modes, build-zig |
| zig.guide working with C (3 pages) | 3 | c-import, abi, translate-c |
| ziglang.org learning resources (5 pages) | 5 | overview, samples, build system guide, why Zig vs Rust/D/C++, learn root |
| Release notes (3 versions) | 3 | 0.12, 0.13, 0.14 |
| Versioned standard library (2) | 2 | 0.13.0/std, 0.14.0/std |
| GitHub repository | 1 | `github.com/ziglang/zig` |
| Community resources (2) | 2 | `ziglearn.org`, (zig.guide counted in language-basics above) |

### Community Domain Considerations

Two community-owned domains are included:

| Domain | Owner | Risk |
|--------|-------|------|
| `zig.guide` | Community maintainer | Low — stable, widely linked from `ziglang.org` |
| `ziglearn.org` | Community maintainer | Low — long-standing resource |

If either domain becomes unavailable, `ziglang.org` provides complete official coverage independently. Monitor at build time; remove from `urls.txt` if the domain fails validation.

---

## URL Security Properties (All 5 Packs)

All 282 URLs across the five packs satisfy these security properties:

- **HTTPS only** — no plain HTTP links
- **Public hostnames** — all target hostnames are public documentation CDNs or GitHub; no private IP ranges, no localhost, no cloud metadata endpoints
- **No credentials** — no authentication tokens, API keys, or passwords appear in any URL
- **No SSRF vectors** — all verified domains are: `python.langchain.com`, `github.com`, `raw.githubusercontent.com`, `openai.github.io`, `cookbook.openai.com`, `platform.openai.com`, `sdk.vercel.ai`, `docs.llamaindex.ai`, `ziglang.org`, `zig.guide`, `ziglearn.org`, `docs.smith.langchain.com`, `smith.langchain.com`

---

## Related Documentation

- [How to Curate and Expand Pack URL Lists](../howto/curate-pack-urls.md)
- [urls.txt Format and Conventions](../reference/urls-txt-format.md)
- [Web Content Source API Reference](../reference/web-content-source.md)
- [Knowledge Packs Design](../design/knowledge-packs.md)
