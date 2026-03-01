"""TDD tests for Issue 211 Improvement 6 - URL list coverage for 5 packs.

These tests define the contract for:
  - langchain-expert: python.langchain.com, how-to/tutorial/integration sub-pages
  - openai-api-expert: Agents SDK, cookbook examples, GitHub 403-bypass fallbacks
  - vercel-ai-sdk:     GitHub raw/blob sources for reliable text extraction
  - llamaindex-expert: 70+ URLs, all major doc sections covered
  - zig-expert:        community guide, standard-library sub-pages, GitHub repo

Tests FAIL when the urls.txt files are missing the required additions,
and PASS once the implementation is in place.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_PACKS = Path(__file__).parent.parent.parent / "data" / "packs"


def load_urls(pack_name: str) -> list[str]:
    """Return the non-blank, non-comment URLs from a pack's urls.txt."""
    urls_file = DATA_PACKS / pack_name / "urls.txt"
    if not urls_file.exists():
        return []
    lines = urls_file.read_text().splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            result.append(stripped)
    return result


def urls_starting_with(urls: list[str], prefix: str) -> list[str]:
    return [u for u in urls if u.startswith(prefix)]


# ---------------------------------------------------------------------------
# Shared contract: every pack must use HTTPS only
# ---------------------------------------------------------------------------

PACKS_UNDER_TEST = [
    "langchain-expert",
    "openai-api-expert",
    "vercel-ai-sdk",
    "llamaindex-expert",
    "zig-expert",
]


@pytest.mark.parametrize("pack_name", PACKS_UNDER_TEST)
class TestHttpsOnly:
    """Every URL in the 5 target packs must use HTTPS."""

    def test_all_urls_use_https(self, pack_name: str) -> None:
        urls = load_urls(pack_name)
        assert urls, f"{pack_name}/urls.txt must contain at least one URL"
        non_https = [u for u in urls if not u.startswith("https://")]
        assert (
            non_https == []
        ), f"{pack_name}: found non-HTTPS URLs (security requirement): {non_https}"

    def test_urls_file_exists(self, pack_name: str) -> None:
        urls_file = DATA_PACKS / pack_name / "urls.txt"
        assert urls_file.exists(), f"Missing {pack_name}/urls.txt"


# ---------------------------------------------------------------------------
# langchain-expert
# ---------------------------------------------------------------------------

LANGCHAIN_PACK = "langchain-expert"


class TestLangchainExpertUrls:
    """Contract tests for langchain-expert/urls.txt (Issue 211 Improvement 6)."""

    @pytest.fixture(scope="class")
    def urls(self) -> list[str]:
        return load_urls(LANGCHAIN_PACK)

    # --- Deprecated domain ---

    def test_no_deprecated_docs_langchain_domain(self, urls: list[str]) -> None:
        """docs.langchain.com is dead — no URLs must use it."""
        deprecated = [u for u in urls if "docs.langchain.com" in u]
        assert deprecated == [], (
            "langchain-expert must NOT contain docs.langchain.com URLs "
            f"(deprecated site): {deprecated}"
        )

    # --- Minimum total count ---

    def test_minimum_url_count(self, urls: list[str]) -> None:
        """Pack must have at least 71 URLs after expansion."""
        assert len(urls) >= 71, f"langchain-expert needs ≥71 URLs, found {len(urls)}"

    # --- Core documentation base ---

    def test_has_python_langchain_concepts(self, urls: list[str]) -> None:
        """Must have coverage of the core concepts pages."""
        concepts = urls_starting_with(urls, "https://python.langchain.com/docs/concepts/")
        assert len(concepts) >= 5, f"Expected ≥5 concepts/ pages, found {len(concepts)}: {concepts}"

    # --- How-To Guides ---

    def test_has_how_to_index(self, urls: list[str]) -> None:
        """Must include the how_to/ index page."""
        assert "https://python.langchain.com/docs/how_to/" in urls, "Missing how_to/ index page"

    def test_minimum_how_to_subpages(self, urls: list[str]) -> None:
        """Must have ≥17 how-to sub-pages (beyond the index)."""
        how_to_sub = [
            u
            for u in urls
            if u.startswith("https://python.langchain.com/docs/how_to/")
            and u != "https://python.langchain.com/docs/how_to/"
        ]
        assert (
            len(how_to_sub) >= 17
        ), f"langchain-expert needs ≥17 how_to/ sub-pages, found {len(how_to_sub)}: {how_to_sub}"

    def test_how_to_custom_tools(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/how_to/custom_tools/" in urls

    def test_how_to_agent_executor(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/how_to/agent_executor/" in urls

    def test_how_to_streaming(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/how_to/streaming/" in urls

    def test_how_to_message_history(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/how_to/message_history/" in urls

    # --- Tutorials ---

    def test_has_tutorials_index(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/tutorials/" in urls

    def test_minimum_tutorial_subpages(self, urls: list[str]) -> None:
        """Must have ≥8 tutorial sub-pages (beyond the index)."""
        tut_sub = [
            u
            for u in urls
            if u.startswith("https://python.langchain.com/docs/tutorials/")
            and u != "https://python.langchain.com/docs/tutorials/"
        ]
        assert (
            len(tut_sub) >= 8
        ), f"langchain-expert needs ≥8 tutorials/ sub-pages, found {len(tut_sub)}: {tut_sub}"

    def test_tutorial_rag(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/tutorials/rag/" in urls

    def test_tutorial_agents(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/tutorials/agents/" in urls

    def test_tutorial_extraction(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/tutorials/extraction/" in urls

    def test_tutorial_summarization(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/tutorials/summarization/" in urls

    def test_tutorial_sql_qa(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/tutorials/sql_qa/" in urls

    # --- Integrations ---

    def test_minimum_integration_subpages(self, urls: list[str]) -> None:
        """Must have ≥10 integrations/ sub-pages beyond providers root."""
        all_integrations = urls_starting_with(
            urls, "https://python.langchain.com/docs/integrations/"
        )
        assert len(all_integrations) >= 10, (
            f"langchain-expert needs ≥10 integrations/ pages, found {len(all_integrations)}: "
            f"{all_integrations}"
        )

    def test_integration_llms(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/integrations/llms/" in urls

    def test_integration_document_loaders(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/integrations/document_loaders/" in urls

    def test_integration_chat_openai(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/integrations/chat/openai/" in urls

    def test_integration_chat_anthropic(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/integrations/chat/anthropic/" in urls

    def test_integration_vectorstores_chroma(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/integrations/vectorstores/chroma/" in urls

    def test_integration_vectorstores_faiss(self, urls: list[str]) -> None:
        assert "https://python.langchain.com/docs/integrations/vectorstores/faiss/" in urls

    # --- LangSmith is kept (different service, not deprecated) ---

    def test_langsmith_url_retained(self, urls: list[str]) -> None:
        """docs.smith.langchain.com (LangSmith) is a valid active service, not deprecated."""
        langsmith = [u for u in urls if "smith.langchain.com" in u]
        assert (
            len(langsmith) >= 1
        ), "LangSmith URL (docs.smith.langchain.com) must be retained — it is active"

    # --- GitHub ---

    def test_has_github_repo(self, urls: list[str]) -> None:
        assert "https://github.com/langchain-ai/langchain" in urls


# ---------------------------------------------------------------------------
# openai-api-expert
# ---------------------------------------------------------------------------

OPENAI_PACK = "openai-api-expert"

# Baseline URLs that must be preserved from before the expansion
_OPENAI_BASELINE_URLS = [
    "https://platform.openai.com/docs/overview",
    "https://platform.openai.com/docs/quickstart",
    "https://platform.openai.com/docs/models",
    "https://platform.openai.com/docs/api-reference/introduction",
    "https://platform.openai.com/docs/api-reference/chat",
    "https://platform.openai.com/docs/api-reference/chat/create",
    "https://platform.openai.com/docs/api-reference/responses",
    "https://platform.openai.com/docs/api-reference/embeddings",
    "https://platform.openai.com/docs/api-reference/embeddings/create",
    "https://platform.openai.com/docs/api-reference/fine-tuning",
    "https://platform.openai.com/docs/api-reference/batch",
    "https://platform.openai.com/docs/api-reference/images",
    "https://platform.openai.com/docs/api-reference/audio",
    "https://platform.openai.com/docs/api-reference/moderations",
    "https://platform.openai.com/docs/api-reference/assistants",
    "https://platform.openai.com/docs/guides/text-generation",
    "https://platform.openai.com/docs/guides/function-calling",
    "https://platform.openai.com/docs/guides/structured-outputs",
    "https://platform.openai.com/docs/guides/vision",
    "https://platform.openai.com/docs/guides/embeddings",
    "https://platform.openai.com/docs/guides/fine-tuning",
    "https://platform.openai.com/docs/guides/batch",
    "https://platform.openai.com/docs/guides/reasoning",
    "https://platform.openai.com/docs/guides/prompt-engineering",
    "https://platform.openai.com/docs/guides/safety-best-practices",
    "https://platform.openai.com/docs/guides/latency-optimization",
    "https://platform.openai.com/docs/guides/production-best-practices",
    "https://platform.openai.com/docs/guides/migrate-to-responses",
    "https://platform.openai.com/docs/deprecations",
    "https://platform.openai.com/docs/changelog",
    "https://platform.openai.com/docs/assistants/deep-dive",
    "https://platform.openai.com/docs/assistants/tools/function-calling",
    "https://github.com/openai/openai-python",
    "https://github.com/openai/openai-node",
    "https://cookbook.openai.com/",
]


class TestOpenAIApiExpertUrls:
    """Contract tests for openai-api-expert/urls.txt (Issue 211 Improvement 6)."""

    @pytest.fixture(scope="class")
    def urls(self) -> list[str]:
        return load_urls(OPENAI_PACK)

    # --- Minimum total count ---

    def test_minimum_url_count(self, urls: list[str]) -> None:
        """Pack must have at least 45 URLs after expansion."""
        assert len(urls) >= 45, f"openai-api-expert needs ≥45 URLs, found {len(urls)}"

    # --- Baseline URLs preserved ---

    @pytest.mark.parametrize("url", _OPENAI_BASELINE_URLS)
    def test_baseline_url_preserved(self, url: str, urls: list[str]) -> None:
        """All pre-existing URLs must still be present."""
        assert url in urls, f"Baseline URL was removed: {url}"

    # --- Agents SDK ---

    def test_has_agents_sdk_github(self, urls: list[str]) -> None:
        assert (
            "https://github.com/openai/openai-agents-python" in urls
        ), "Missing OpenAI Agents SDK GitHub URL"

    def test_has_agents_sdk_docs(self, urls: list[str]) -> None:
        assert (
            "https://openai.github.io/openai-agents-python/" in urls
        ), "Missing OpenAI Agents SDK documentation URL"

    # --- SDK README (GitHub 403 bypass) ---

    def test_has_sdk_readme_blob(self, urls: list[str]) -> None:
        assert (
            "https://github.com/openai/openai-python/blob/main/README.md" in urls
        ), "Missing openai-python SDK README blob URL"

    # --- Cookbook examples (≥5) ---

    def test_minimum_cookbook_example_count(self, urls: list[str]) -> None:
        """Must have ≥5 cookbook example URLs (beyond the cookbook root)."""
        cookbook_examples = [
            u
            for u in urls
            if (
                u.startswith("https://cookbook.openai.com/examples/")
                or u.startswith("https://github.com/openai/openai-cookbook/blob/main/examples/")
            )
        ]
        assert len(cookbook_examples) >= 5, (
            f"openai-api-expert needs ≥5 cookbook example URLs, found {len(cookbook_examples)}: "
            f"{cookbook_examples}"
        )

    def test_has_function_calling_cookbook(self, urls: list[str]) -> None:
        """Function-calling cookbook page must be present."""
        has_fc = any(
            "function" in u.lower() and ("cookbook" in u or "openai-cookbook" in u) for u in urls
        )
        assert has_fc, "Missing function-calling cookbook example URL"

    def test_has_github_cookbook_notebook(self, urls: list[str]) -> None:
        """At least one raw GitHub notebook URL (403-bypass fallback) must exist."""
        github_notebooks = [
            u for u in urls if u.startswith("https://github.com/openai/openai-cookbook/blob/")
        ]
        assert (
            len(github_notebooks) >= 1
        ), f"Need ≥1 github.com/openai/openai-cookbook/blob/ URL, found: {github_notebooks}"


# ---------------------------------------------------------------------------
# vercel-ai-sdk
# ---------------------------------------------------------------------------

VERCEL_PACK = "vercel-ai-sdk"

_VERCEL_BASELINE_URLS = [
    "https://sdk.vercel.ai/docs",
    "https://sdk.vercel.ai/docs/foundations/overview",
    "https://sdk.vercel.ai/docs/foundations/agents",
    "https://sdk.vercel.ai/docs/foundations/prompts",
    "https://sdk.vercel.ai/docs/foundations/streaming",
    "https://sdk.vercel.ai/docs/ai-core/generate-text",
    "https://sdk.vercel.ai/docs/ai-core/stream-text",
    "https://sdk.vercel.ai/docs/ai-core/generate-object",
    "https://sdk.vercel.ai/docs/ai-core/stream-object",
    "https://sdk.vercel.ai/docs/ai-core/embed",
    "https://sdk.vercel.ai/docs/ai-core/telemetry",
    "https://sdk.vercel.ai/docs/ai-core/settings",
    "https://sdk.vercel.ai/docs/ai-sdk-core/testing",
    "https://sdk.vercel.ai/docs/concepts/tools",
    "https://sdk.vercel.ai/docs/concepts/middleware",
    "https://sdk.vercel.ai/docs/concepts/ai-rsc",
    "https://sdk.vercel.ai/docs/ai-sdk-ui/overview",
    "https://sdk.vercel.ai/docs/ai-sdk-ui/chatbot",
    "https://sdk.vercel.ai/docs/ai-sdk-ui/chatbot-with-tool-calling",
    "https://sdk.vercel.ai/docs/ai-sdk-ui/completion",
    "https://sdk.vercel.ai/docs/ai-sdk-ui/storing-messages",
    "https://sdk.vercel.ai/docs/guides/providers/openai",
    "https://sdk.vercel.ai/docs/guides/providers/anthropic",
    "https://sdk.vercel.ai/docs/guides/providers/google-generative-ai",
    "https://sdk.vercel.ai/docs/guides/providers/amazon-bedrock",
    "https://sdk.vercel.ai/docs/guides/providers/azure",
    "https://sdk.vercel.ai/docs/guides",
    "https://sdk.vercel.ai/docs/guides/rag-chatbot",
    "https://sdk.vercel.ai/docs/guides/multi-modal-chatbot",
    "https://sdk.vercel.ai/cookbook",
    "https://sdk.vercel.ai/docs/advanced",
    "https://sdk.vercel.ai/docs/advanced/custom-provider",
    "https://sdk.vercel.ai/docs/reference/ai-sdk-core",
    "https://sdk.vercel.ai/docs/reference/ai-sdk-ui",
    "https://sdk.vercel.ai/docs/reference/ai-sdk-rsc",
    "https://github.com/vercel/ai",
]


class TestVercelAISdkUrls:
    """Contract tests for vercel-ai-sdk/urls.txt (Issue 211 Improvement 6)."""

    @pytest.fixture(scope="class")
    def urls(self) -> list[str]:
        return load_urls(VERCEL_PACK)

    # --- Minimum total count ---

    def test_minimum_url_count(self, urls: list[str]) -> None:
        """Pack must have at least 45 URLs after expansion."""
        assert len(urls) >= 45, f"vercel-ai-sdk needs ≥45 URLs, found {len(urls)}"

    # --- Baseline URLs preserved ---

    @pytest.mark.parametrize("url", _VERCEL_BASELINE_URLS)
    def test_baseline_url_preserved(self, url: str, urls: list[str]) -> None:
        """All pre-existing URLs must still be present."""
        assert url in urls, f"Baseline URL was removed: {url}"

    # --- GitHub raw/blob sources (reliable fallback) ---

    def test_minimum_github_source_count(self, urls: list[str]) -> None:
        """Must have ≥5 GitHub raw or blob URLs for text extraction fallback."""
        github_sources = [
            u
            for u in urls
            if u.startswith("https://raw.githubusercontent.com/vercel/ai/")
            or u.startswith("https://github.com/vercel/ai/blob/")
        ]
        assert len(github_sources) >= 5, (
            f"vercel-ai-sdk needs ≥5 GitHub raw/blob URLs, found {len(github_sources)}: "
            f"{github_sources}"
        )

    def test_has_root_readme_raw(self, urls: list[str]) -> None:
        """Root README.md raw URL for reliable text extraction."""
        assert (
            "https://raw.githubusercontent.com/vercel/ai/main/README.md" in urls
        ), "Missing raw.githubusercontent.com root README.md"

    def test_has_root_readme_blob(self, urls: list[str]) -> None:
        """Root README.md blob URL as fallback."""
        assert (
            "https://github.com/vercel/ai/blob/main/README.md" in urls
        ), "Missing github.com blob root README.md"

    def test_has_packages_ai_readme(self, urls: list[str]) -> None:
        """packages/ai README.md must be included (core package docs)."""
        has_pkg_readme = any(
            "vercel/ai" in u and "packages/ai" in u and "README" in u for u in urls
        )
        assert has_pkg_readme, "Missing packages/ai README URL (blob or raw)"

    def test_has_core_mdx_or_docs_source(self, urls: list[str]) -> None:
        """At least one content/docs MDX source file from the GitHub repo."""
        mdx_sources = [u for u in urls if "content/docs" in u and "vercel/ai" in u]
        assert len(mdx_sources) >= 1, f"Need ≥1 content/docs MDX source URL, found: {mdx_sources}"


# ---------------------------------------------------------------------------
# llamaindex-expert
# ---------------------------------------------------------------------------

LLAMA_PACK = "llamaindex-expert"

# 28 baseline URLs that must be preserved
_LLAMA_BASELINE_URLS = [
    "https://docs.llamaindex.ai/en/stable/",
    "https://docs.llamaindex.ai/en/stable/getting_started/concepts/",
    "https://docs.llamaindex.ai/en/stable/getting_started/starter_example_local/",
    "https://docs.llamaindex.ai/en/stable/understanding/",
    "https://docs.llamaindex.ai/en/stable/understanding/rag/",
    "https://docs.llamaindex.ai/en/stable/understanding/agent/",
    "https://docs.llamaindex.ai/en/stable/understanding/putting_it_all_together/",
    "https://docs.llamaindex.ai/en/stable/understanding/evaluating/evaluating/",
    "https://docs.llamaindex.ai/en/stable/understanding/tracing_and_debugging/tracing_and_debugging/",
    "https://docs.llamaindex.ai/en/stable/module_guides/models/llms/",
    "https://docs.llamaindex.ai/en/stable/module_guides/models/embeddings/",
    "https://docs.llamaindex.ai/en/stable/module_guides/indexing/",
    "https://docs.llamaindex.ai/en/stable/module_guides/querying/",
    "https://docs.llamaindex.ai/en/stable/module_guides/loading/",
    "https://docs.llamaindex.ai/en/stable/module_guides/storing/",
    "https://docs.llamaindex.ai/en/stable/module_guides/evaluating/",
    "https://docs.llamaindex.ai/en/stable/module_guides/deploying/",
    "https://docs.llamaindex.ai/en/stable/use_cases/q_and_a/",
    "https://docs.llamaindex.ai/en/stable/use_cases/agents/",
    "https://docs.llamaindex.ai/en/stable/optimizing/production_rag/",
    "https://docs.llamaindex.ai/en/stable/optimizing/building_rag_from_scratch/",
    "https://docs.llamaindex.ai/en/stable/optimizing/evaluation/evaluation/",
    "https://docs.llamaindex.ai/en/stable/examples/cookbooks/GraphRAG_v1/",
    "https://docs.llamaindex.ai/en/stable/examples/graph_rag/llama_index_cognee_integration/",
    "https://docs.llamaindex.ai/en/stable/examples/low_level/oss_ingestion_retrieval/",
    "https://github.com/run-llama/llama_index",
    "https://docs.llamaindex.ai/en/latest/",
    "https://docs.llamaindex.ai/en/stable/api_reference/",
]


class TestLlamaIndexExpertUrls:
    """Contract tests for llamaindex-expert/urls.txt (Issue 211 Improvement 6)."""

    @pytest.fixture(scope="class")
    def urls(self) -> list[str]:
        return load_urls(LLAMA_PACK)

    # --- Minimum total count ---

    def test_minimum_url_count(self, urls: list[str]) -> None:
        """Pack must have at least 70 URLs after expansion (target: 74)."""
        assert len(urls) >= 70, f"llamaindex-expert needs ≥70 URLs, found {len(urls)}"

    # --- All 28 baseline URLs preserved ---

    @pytest.mark.parametrize("url", _LLAMA_BASELINE_URLS)
    def test_baseline_url_preserved(self, url: str, urls: list[str]) -> None:
        """All pre-existing 28 URLs must still be present."""
        assert url in urls, f"Baseline URL was removed: {url}"

    # --- Getting Started section expansion ---

    def test_has_getting_started_installation(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/getting_started/installation/" in urls

    def test_has_getting_started_starter_example(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/getting_started/starter_example/" in urls

    def test_has_getting_started_customization(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/getting_started/customization/" in urls

    # --- Understanding sub-sections ---

    def test_minimum_understanding_subpages(self, urls: list[str]) -> None:
        """Understanding section must have ≥5 sub-pages (beyond root)."""
        understanding = [
            u
            for u in urls
            if u.startswith("https://docs.llamaindex.ai/en/stable/understanding/")
            and u != "https://docs.llamaindex.ai/en/stable/understanding/"
        ]
        assert (
            len(understanding) >= 5
        ), f"llamaindex-expert needs ≥5 understanding/ sub-pages, found {len(understanding)}"

    def test_has_understanding_loading(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/understanding/loading/loading/" in urls

    def test_has_understanding_indexing(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/understanding/indexing/indexing/" in urls

    def test_has_understanding_querying(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/understanding/querying/querying/" in urls

    def test_has_understanding_workflows(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/understanding/workflows/" in urls

    # --- Optimizing sub-sections ---

    def test_minimum_optimizing_subpages(self, urls: list[str]) -> None:
        """Optimizing section must have ≥3 sub-pages beyond the 3 existing ones."""
        optimizing = urls_starting_with(urls, "https://docs.llamaindex.ai/en/stable/optimizing/")
        assert (
            len(optimizing) >= 6
        ), f"llamaindex-expert needs ≥6 optimizing/ pages total, found {len(optimizing)}"

    def test_has_optimizing_basic_strategies(self, urls: list[str]) -> None:
        assert (
            "https://docs.llamaindex.ai/en/stable/optimizing/basic_strategies/basic_strategies/"
            in urls
        )

    def test_has_optimizing_advanced_retrieval(self, urls: list[str]) -> None:
        assert (
            "https://docs.llamaindex.ai/en/stable/optimizing/advanced_retrieval/advanced_retrieval/"
            in urls
        )

    def test_has_optimizing_agentic_strategies(self, urls: list[str]) -> None:
        assert (
            "https://docs.llamaindex.ai/en/stable/optimizing/agentic_strategies/agentic_strategies/"
            in urls
        )

    # --- Module Guides sub-pages ---

    def test_minimum_module_guide_subpages(self, urls: list[str]) -> None:
        """Module guides must have sub-pages beyond the 8 category roots."""
        module_guides = urls_starting_with(
            urls, "https://docs.llamaindex.ai/en/stable/module_guides/"
        )
        assert (
            len(module_guides) >= 18
        ), f"llamaindex-expert needs ≥18 module_guides/ pages total, found {len(module_guides)}"

    def test_has_module_guide_query_engine(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/module_guides/querying/query_engine/" in urls

    def test_has_module_guide_retriever(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/module_guides/querying/retriever/" in urls

    def test_has_module_guide_documents_and_nodes(self, urls: list[str]) -> None:
        assert (
            "https://docs.llamaindex.ai/en/stable/module_guides/loading/documents_and_nodes/"
            in urls
        )

    def test_has_module_guide_vector_store_index(self, urls: list[str]) -> None:
        assert (
            "https://docs.llamaindex.ai/en/stable/module_guides/indexing/vector_store_index/"
            in urls
        )

    def test_has_module_guide_vector_stores_storage(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/module_guides/storing/vector_stores/" in urls

    def test_has_module_guide_agents_deploy(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/" in urls

    def test_has_module_guide_workflow(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/module_guides/workflow/" in urls

    # --- Examples section ---

    def test_minimum_example_pages(self, urls: list[str]) -> None:
        """Must have ≥5 example page URLs."""
        examples = urls_starting_with(urls, "https://docs.llamaindex.ai/en/stable/examples/")
        assert (
            len(examples) >= 5
        ), f"llamaindex-expert needs ≥5 examples/ pages, found {len(examples)}"

    def test_has_examples_agent_openai(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/examples/agent/openai_agent/" in urls

    def test_has_examples_vector_store_demo(self, urls: list[str]) -> None:
        assert (
            "https://docs.llamaindex.ai/en/stable/examples/vector_stores/SimpleIndexDemo/" in urls
        )

    # --- API Reference sub-categories ---

    def test_minimum_api_reference_subpages(self, urls: list[str]) -> None:
        """Must have ≥5 api_reference/ sub-category URLs."""
        api_ref = [
            u
            for u in urls
            if u.startswith("https://docs.llamaindex.ai/en/stable/api_reference/")
            and u != "https://docs.llamaindex.ai/en/stable/api_reference/"
        ]
        assert (
            len(api_ref) >= 5
        ), f"llamaindex-expert needs ≥5 api_reference/ sub-pages, found {len(api_ref)}: {api_ref}"

    def test_has_api_reference_llms(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/api_reference/llms/" in urls

    def test_has_api_reference_indices(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/api_reference/indices/" in urls

    def test_has_api_reference_query(self, urls: list[str]) -> None:
        assert "https://docs.llamaindex.ai/en/stable/api_reference/query/" in urls


# ---------------------------------------------------------------------------
# zig-expert
# ---------------------------------------------------------------------------

ZIG_PACK = "zig-expert"


class TestZigExpertUrls:
    """Contract tests for zig-expert/urls.txt (Issue 211 Improvement 6)."""

    @pytest.fixture(scope="class")
    def urls(self) -> list[str]:
        return load_urls(ZIG_PACK)

    # --- Minimum total count ---

    def test_minimum_url_count(self, urls: list[str]) -> None:
        """Pack must have more than 40 URLs after expansion."""
        assert len(urls) > 40, f"zig-expert needs >40 URLs, found {len(urls)}"

    # --- Official documentation ---

    def test_has_official_reference_master(self, urls: list[str]) -> None:
        assert "https://ziglang.org/documentation/master/" in urls

    def test_has_release_notes(self, urls: list[str]) -> None:
        """Must have at least one release notes page."""
        release_notes = [u for u in urls if "release-notes" in u and "ziglang.org" in u]
        assert len(release_notes) >= 1, "Missing ziglang.org release notes"

    # --- GitHub repository ---

    def test_has_github_repo(self, urls: list[str]) -> None:
        """GitHub ziglang/zig repository must be present."""
        assert "https://github.com/ziglang/zig" in urls, "Missing https://github.com/ziglang/zig"

    # --- Community resource ---

    def test_has_ziglearn_community(self, urls: list[str]) -> None:
        """ziglearn.org community guide must be present."""
        assert "https://ziglearn.org/" in urls, "Missing community resource: https://ziglearn.org/"

    # --- zig.guide language-basics section ---

    def test_has_zig_guide_language_basics(self, urls: list[str]) -> None:
        """zig.guide language-basics section must be represented."""
        lang_basics = [u for u in urls if u.startswith("https://zig.guide/language-basics/")]
        assert (
            len(lang_basics) >= 5
        ), f"zig-expert needs ≥5 zig.guide/language-basics/ pages, found {len(lang_basics)}"

    def test_has_zig_guide_comptime(self, urls: list[str]) -> None:
        assert "https://zig.guide/language-basics/comptime/" in urls

    def test_has_zig_guide_error_union(self, urls: list[str]) -> None:
        assert "https://zig.guide/language-basics/error-union-type/" in urls

    # --- zig.guide standard-library section ---

    def test_has_zig_guide_standard_library_base(self, urls: list[str]) -> None:
        """Must have at least 4 standard-library sub-pages from zig.guide."""
        stdlib_pages = [u for u in urls if u.startswith("https://zig.guide/standard-library/")]
        assert len(stdlib_pages) >= 4, (
            f"zig-expert needs ≥4 zig.guide/standard-library/ pages, found {len(stdlib_pages)}: "
            f"{stdlib_pages}"
        )

    def test_has_zig_guide_hashmaps(self, urls: list[str]) -> None:
        assert "https://zig.guide/standard-library/hashmaps/" in urls

    def test_has_zig_guide_threads(self, urls: list[str]) -> None:
        assert "https://zig.guide/standard-library/threads/" in urls

    def test_has_zig_guide_readers_and_writers(self, urls: list[str]) -> None:
        assert "https://zig.guide/standard-library/readers-and-writers/" in urls

    def test_has_zig_guide_json(self, urls: list[str]) -> None:
        assert "https://zig.guide/standard-library/json/" in urls

    # --- ziglang.org/learn pages ---

    def test_has_ziglang_learn(self, urls: list[str]) -> None:
        assert "https://ziglang.org/learn/" in urls

    def test_has_ziglang_learn_overview(self, urls: list[str]) -> None:
        assert "https://ziglang.org/learn/overview/" in urls

    def test_has_ziglang_build_system_or_why(self, urls: list[str]) -> None:
        """Must include at least one additional ziglang.org/learn/ sub-page."""
        extra_learn = [
            u
            for u in urls
            if u.startswith("https://ziglang.org/learn/")
            and u
            not in (
                "https://ziglang.org/learn/",
                "https://ziglang.org/learn/overview/",
            )
        ]
        assert (
            len(extra_learn) >= 1
        ), f"Need ≥1 extra ziglang.org/learn/ sub-page, found: {extra_learn}"

    # --- Build system coverage ---

    def test_has_build_system_coverage(self, urls: list[str]) -> None:
        """Must have at least one build system URL."""
        build_urls = [u for u in urls if "build" in u.lower() and "zig" in u.lower()]
        assert len(build_urls) >= 1, f"No build system URL found in zig-expert: {urls}"
