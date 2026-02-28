#!/usr/bin/env python3
"""Generate evaluation Q&A pairs for a knowledge pack using Claude.

Generates 50 diverse evaluation questions per pack. When a pack database
exists, article titles and content snippets are sampled to ground the
questions in actual pack content. When no database exists, questions are
generated from domain knowledge about the pack topic.

Usage:
    python scripts/generate_eval_questions.py --pack azure-lighthouse
    python scripts/generate_eval_questions.py --pack physics-expert --db data/packs/physics-expert/pack.db
    python scripts/generate_eval_questions.py --pack security-copilot --count 50

Output:
    data/packs/{pack-name}/eval/questions.json  (JSON array)
    data/packs/{pack-name}/eval/questions.jsonl (JSONL, one object per line)
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import anthropic

# Add project root to path for optional kuzu import
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
DEFAULT_COUNT = 50

# Domain descriptions for well-known packs (used when no DB is available)
DOMAIN_DESCRIPTIONS: dict[str, str] = {
    "azure-lighthouse": (
        "Azure Lighthouse is a service that enables cross-tenant management, "
        "allowing service providers to manage customer Azure resources at scale. "
        "Key topics: delegated resource management, Azure Active Directory, "
        "managed services offers, Azure Marketplace, role assignments, "
        "just-in-time access, Azure Policy, Azure Monitor, ARM templates, "
        "Bicep templates, multi-tenant architectures, and security best practices."
    ),
    "security-copilot": (
        "Microsoft Security Copilot is an AI-powered security analysis tool that "
        "combines large language models with security-specific plugins and skills. "
        "Key topics: threat intelligence, incident response, vulnerability assessment, "
        "KQL queries, Microsoft Sentinel integration, Defender for Endpoint, "
        "Entra ID security, MITRE ATT&CK framework, promptbooks, custom plugins, "
        "natural language queries, and security operations center (SOC) workflows."
    ),
    "sentinel-graph": (
        "Microsoft Sentinel is a cloud-native SIEM (Security Information and Event "
        "Management) and SOAR (Security Orchestration, Automation, and Response) "
        "solution. Key topics: KQL (Kusto Query Language), analytic rules, "
        "workbooks, playbooks (Logic Apps), data connectors, threat hunting, "
        "incidents and alerts, UEBA, entity mapping, watchlists, content hub, "
        "Microsoft Graph Security API, investigation graph, and automation rules."
    ),
    # Note: fabric-graphql-expert was generated before the pack DB was built and used
    # the fallback domain description path. This results in 30 questions instead of 50.
    # 30 questions is acceptable when no DB exists. To generate 50, build the pack DB
    # first and re-run: python scripts/generate_eval_questions.py --pack fabric-graphql-expert
    "fabric-graphql-expert": (
        "Microsoft Fabric API for GraphQL provides GraphQL access to Fabric data "
        "sources. Key topics: GraphQL schema generation, authentication with "
        "Microsoft Entra ID, pagination (cursor-based), filtering operators, "
        "mutations, VS Code development, schema export/introspection, security "
        "best practices, performance optimization, monitoring with Azure Monitor, "
        "troubleshooting, OneLake, lakehouses, data warehouses, and SQL databases."
    ),
    "physics-expert": (
        "Comprehensive physics knowledge spanning classical mechanics, quantum "
        "mechanics, thermodynamics, electromagnetism, relativity, and modern physics."
    ),
    "dotnet-expert": (
        "Expert .NET development knowledge covering C#, ASP.NET Core, Entity "
        "Framework, LINQ, async/await, dependency injection, minimal APIs, and Blazor."
    ),
    "rust-expert": (
        "Expert Rust programming knowledge covering ownership, borrowing, lifetimes, "
        "traits, async/await, unsafe code, macros, Cargo, and systems programming."
    ),
    "rust-async-expert": (
        "Expert knowledge of Rust asynchronous programming covering async/await syntax, "
        "the Tokio runtime (spawning tasks, shared state, channels, select!, streams), "
        "Pin and Unpin mechanics, the Future trait and polling, Send/Sync marker traits, "
        "async traits, Waker and task wakeups, tokio::sync primitives (Mutex, mpsc, "
        "oneshot, broadcast, watch), AsyncRead/AsyncWrite, tokio::time utilities, "
        "bridging sync and async code, and error handling in async contexts."
    ),
    "postgresql-internals": (
        "Deep knowledge of PostgreSQL internals covering MVCC (multi-version concurrency "
        "control, transaction isolation levels, tuple visibility), Write-Ahead Logging "
        "(WAL configuration, checkpoints, async commit, WAL internals), query planner "
        "(EXPLAIN/EXPLAIN ANALYZE, cost estimation, plan nodes, join strategies), index "
        "types (B-tree, GIN, GiST, SP-GiST, BRIN, Hash, partial and expression indexes), "
        "table partitioning (range, list, hash), VACUUM and autovacuum (dead tuple cleanup, "
        "transaction ID wraparound prevention, VACUUM FULL), and performance tuning "
        "(shared_buffers, work_mem, effective_cache_size, statistics collection)."
    ),
    "wasm-components": (
        "Expert knowledge of the WebAssembly Component Model covering WIT (WebAssembly "
        "Interface Types) language for defining interfaces and worlds, WASI Preview 2 "
        "(wasi:io, wasi:http, wasi:cli, wasi:filesystem), wit-bindgen code generation "
        "for guest languages, wasmtime embedding API (Component, Linker, Store, Engine), "
        "host/guest interface patterns, WasiCtx configuration, adapter modules, "
        "component composition with wasm-tools, resource types and handles, canonical ABI, "
        "and the WebAssembly component ecosystem (wasmCloud, Fermyon Spin)."
    ),
    "prompt-engineering": (
        "Comprehensive prompt engineering knowledge covering system prompts and role "
        "assignment, tool use and function calling patterns, chain-of-thought (CoT) "
        "reasoning, few-shot and multishot prompting with examples, XML tag structuring, "
        "prompt chaining for complex tasks, extended thinking and reasoning models, "
        "structured outputs (JSON mode, schema adherence), constitutional AI principles, "
        "evaluation techniques (evals, benchmarks, A/B testing), context engineering "
        "for agents, prompt templates and variables, safety best practices, and "
        "model-specific optimizations for Claude and GPT models."
    ),
    "bicep-infrastructure": (
        "Expert knowledge of Azure Bicep infrastructure-as-code covering Bicep file "
        "structure and syntax, modules (local and registry), deployment stacks with "
        "lifecycle management, what-if operations for deployment preview, private "
        "module registry (Azure Container Registry), user-defined data types and "
        "functions, linter rules and bicepconfig.json, deployment patterns (CLI, "
        "PowerShell, GitHub Actions), conditional deployment and loops, Key Vault "
        "parameter references, template specs, deployment scripts, Azure Verified "
        "Modules (AVM), and Azure Landing Zones with Bicep."
    ),
    "swift-expert": (
        "Expert Swift programming knowledge covering Swift 6 strict concurrency with "
        "actors and sendable types, typed throws, noncopyable types (~Copyable), macros, "
        "SwiftUI, async/await, structured concurrency, protocol-oriented programming, "
        "generics, optionals, closures, memory safety, ARC, opaque types, and the Swift "
        "standard library. Key topics: data-race safety at compile time, MainActor, "
        "actor isolation, task groups, async sequences, Swift Package Manager, "
        "result builders, property wrappers, C++ interop, and embedded Swift."
    ),
    "kotlin-expert": (
        "Expert Kotlin programming knowledge covering Kotlin 2.x with the K2 compiler, "
        "coroutines and structured concurrency, Kotlin Multiplatform (KMP), Compose "
        "Multiplatform, sealed classes, data classes, null safety, extension functions, "
        "scope functions, delegation, generics with variance, inline functions, flow, "
        "channels, and Android development. Key topics: suspend functions, coroutine "
        "context and dispatchers, StateFlow and SharedFlow, Kotlin/Native, Kotlin/JS, "
        "Kotlin/Wasm, K2 compiler migration, context receivers, and Gradle DSL."
    ),
    "ruby-expert": (
        "Expert Ruby programming knowledge covering Ruby 3.3+ with YJIT JIT compiler, "
        "Ractors for actor-based parallelism, pattern matching (case/in), RBS type "
        "signatures, Prism parser, M:N thread scheduler, fibers, blocks and procs, "
        "metaprogramming, mixins, open classes, and the core standard library. Key "
        "topics: Enumerable, method_missing, define_method, refinements, frozen string "
        "literals, garbage collection, Ruby gems, Bundler, Rack, and Rails integration."
    ),
    "cpp-expert": (
        "Expert C++ programming knowledge covering C++23 and C++26 features including "
        "modules, ranges library with views and adaptors, std::expected for error handling, "
        "coroutines with std::generator, constexpr and consteval, std::mdspan for "
        "multidimensional arrays, concepts and constraints, std::format and std::print, "
        "flat_map, span, structured bindings, and lambda improvements. Key topics: "
        "RAII, smart pointers (unique_ptr, shared_ptr), move semantics, perfect forwarding, "
        "template metaprogramming, STL containers and algorithms, threading with jthread, "
        "atomic operations, and memory model."
    ),
    "zig-expert": (
        "Expert Zig programming knowledge covering comptime metaprogramming and "
        "compile-time code execution, error unions and error handling, explicit allocator "
        "pattern, the build system (build.zig), safety features and undefined behavior "
        "checks, C interoperability via @cImport, optionals, slices, packed structs, "
        "and the standard library. Key topics: comptime generics, @typeInfo reflection, "
        "ArenaAllocator, page_allocator, FixedBufferAllocator, errdefer, payload captures, "
        "labeled blocks, sentinel-terminated types, async I/O, and cross-compilation."
    ),
    "python-expert": (
        "Expert Python programming knowledge covering Python 3.12+ features. "
        "Key topics: structural pattern matching (match/case statements, PEP 636), "
        "modern typing system (PEP 695 type parameter syntax, Self type PEP 673, "
        "TypedDict kwargs PEP 692, type defaults PEP 696, dataclass transforms PEP 681), "
        "asyncio (coroutines, tasks, event loops, streams, synchronization primitives, "
        "subprocess, TaskGroup), dataclasses (field, post_init, frozen, slots, KW_ONLY), "
        "packaging with pyproject.toml and tomllib, pathlib, collections (Counter, deque, "
        "defaultdict, namedtuple), functools (cache, lru_cache, reduce, partial, wraps), "
        "itertools, contextlib (contextmanager, asynccontextmanager, suppress), enum, "
        "abstract base classes, f-string improvements, per-interpreter GIL, "
        "free-threaded CPython, and improved error messages."
    ),
    "typescript-expert": (
        "Expert TypeScript programming knowledge covering the TypeScript 5.x type system. "
        "Key topics: generics (type parameters, constraints, inference), decorators "
        "(class, method, property, parameter decorators, stage 3 decorators in TS 5.0), "
        "satisfies operator, const assertions, template literal types, conditional types "
        "(infer keyword, distributive conditional types), mapped types (key remapping, "
        "modifiers), utility types (Partial, Required, Pick, Omit, Exclude, Extract, "
        "NonNullable, ReturnType, Parameters, Awaited, NoInfer), type narrowing "
        "(type guards, discriminated unions, exhaustiveness checking), keyof and typeof "
        "type operators, indexed access types, modules and module resolution, "
        "declaration files, project references, tsconfig configuration, "
        "and TypeScript 5.0-5.9 release features."
    ),
    "go-expert": (
        "Expert Go programming knowledge covering Go 1.22+ features. "
        "Key topics: generics (type parameters, type constraints, type inference, "
        "when to use generics), range-over-func iterators (Go 1.23, iterator functions, "
        "slices.All, maps.Keys), structured logging with slog (Logger, Handler, Attrs, "
        "context integration), error handling (errors.Is, errors.As, fmt.Errorf wrapping, "
        "custom error types), concurrency (goroutines, channels, select, WaitGroups, "
        "mutexes, context, worker pools, pipelines), modules (go.mod, dependencies, "
        "versioning, workspaces), testing (table-driven tests, benchmarks, fuzzing, "
        "subtests), Effective Go patterns, and Go 1.22-1.23 release features."
    ),
    "java-expert": (
        "Expert Java programming knowledge covering Java 21+ features. "
        "Key topics: virtual threads (Project Loom, Thread.ofVirtual, "
        "Executors.newVirtualThreadPerTaskExecutor), pattern matching for switch "
        "(type patterns, record patterns, guarded patterns, exhaustiveness), "
        "records (compact constructors, local records, record patterns), sealed classes "
        "(permits clause, exhaustive switch), Foreign Function & Memory API "
        "(MemorySegment, Arena, Linker, MethodHandle), ZGC (generational ZGC, "
        "low-latency GC tuning), structured concurrency (StructuredTaskScope, "
        "subtask management), scoped values (ScopedValue, thread-local replacement), "
        "sequenced collections, text blocks, local variable type inference (var), "
        "and Java Language Specification updates."
    ),
    "csharp-expert": (
        "Expert C# programming knowledge covering C# 13 and .NET 9 features. "
        "Key topics: primary constructors (class and struct primary constructors, "
        "parameter capture, base constructor calls), collection expressions "
        "(spread operator, target-typed collections), interceptors (source generators, "
        "AOT optimization), Native AOT compilation (trimming, deployment), "
        "pattern matching (property patterns, list patterns, extended patterns, "
        "positional patterns), records (record class, record struct, with expressions), "
        "nullable reference types (null safety, annotations, warnings), "
        "async/await (Task, ValueTask, async streams, cancellation), "
        "LINQ (query expressions, method syntax, deferred execution), "
        "generics (constraints, where clause, covariance/contravariance), "
        "dependency injection, minimal APIs, and .NET 9 performance improvements."
    ),
    "opencypher-expert": (
        "Expert knowledge for writing OpenCypher graph queries, specifically targeting "
        "the Kuzu embedded graph database. Key topics: Cypher syntax and clauses "
        "(MATCH, WHERE, RETURN, WITH, UNWIND, ORDER BY, LIMIT, SKIP, UNION), "
        "pattern matching (node patterns, relationship patterns, variable-length paths), "
        "shortest path algorithms (single, all, weighted), path semantics (WALK, TRAIL, "
        "ACYCLIC), data definition (CREATE NODE TABLE, CREATE REL TABLE, ALTER, DROP), "
        "data manipulation (CREATE, MERGE, SET, DELETE, DETACH DELETE), data types "
        "(SERIAL, UUID, STRUCT, LIST, ARRAY, INTERVAL, BLOB), functions and expressions "
        "(aggregation with COUNT/SUM/AVG/COLLECT, text functions, list functions, "
        "pattern-matching with regexp, mathematical functions), subqueries (COUNT, EXISTS), "
        "import/export (COPY FROM CSV/Parquet, LOAD FROM, EXPORT DATABASE), extensions "
        "(vector search with HNSW index, full-text search with BM25, graph algorithms "
        "like PageRank), prepared statements, implicit GROUP BY behavior, Kuzu Python API, "
        "query optimization (indexes, parameterized queries, PROFILE, avoiding cartesian "
        "products, WITH clause for breaking down complex queries), and graph data modeling "
        "best practices for property graphs."
    ),
    "mcp-protocol": (
        "The Model Context Protocol (MCP) is an open standard for connecting LLMs to "
        "external tools, data sources, and services. Key topics: MCP specification "
        "(JSON-RPC 2.0 based), server development (Python SDK, TypeScript SDK), tool "
        "definitions (executable functions for AI), resource handlers (data exposure via "
        "URIs), prompt templates (reusable LLM interaction patterns), sampling (server- "
        "initiated completions), transport setup (stdio, Streamable HTTP, SSE), lifecycle "
        "management (initialization, capability negotiation, shutdown), security best "
        "practices (input validation, authorization), and client features (roots, elicitation)."
    ),
    "claude-agent-sdk": (
        "The Claude Agent SDK is Anthropic's open-source framework for building autonomous "
        "AI agents in Python and TypeScript. Key topics: agent loop, built-in tools (file "
        "operations, code execution, web search), MCP integration for custom tools, subagent "
        "orchestration (filesystem-based, programmatic, built-in), session management "
        "(resume, fork), hooks for tool events, permissions (fine-grained agent capabilities), "
        "ClaudeSDKClient vs query() API, custom tools as in-process MCP servers, streaming "
        "responses, prompt caching, configuration (setting sources), agent skills, slash "
        "commands, plugins, and authentication (API key, Bedrock, Vertex, Azure AI Foundry)."
    ),
    "github-copilot-sdk": (
        "GitHub Copilot Extensions SDK enables building extensions that expand Copilot Chat "
        "functionality. Key topics: Copilot Extensions architecture (agents, skillsets), "
        "MCP server integration (local and remote), VS Code chat participants, preview SDK "
        "(request verification, response formatting), building Copilot agents (server-side), "
        "VS Code Copilot extension configuration, GitHub MCP server setup, enterprise MCP "
        "policies, Copilot coding agent, repository indexing, custom instructions, GitHub "
        "Marketplace integration, and migration from GitHub App extensions to MCP servers."
    ),
    "microsoft-agent-framework": (
        "Microsoft Agent Framework is the unified SDK for building, orchestrating, and "
        "deploying AI agents and multi-agent workflows, converging AutoGen and Semantic "
        "Kernel. Key topics: ChatAgent abstractions, @ai_function decorator, graph-based "
        "Workflow APIs, orchestration patterns (sequential, concurrent, handoff, group chat, "
        "magentic), state management (checkpointing, long-running processes), tool integration, "
        "model clients, custom agents, migration from AutoGen and Semantic Kernel, Azure AI "
        "Foundry deployment, Agent2Agent (A2A) protocol, MCP integration, and Process "
        "Framework for deterministic business workflows."
    ),
    "workiq-mcp": (
        "Microsoft Work IQ is a CLI and MCP server for connecting AI assistants to M365 "
        "Copilot data. Key topics: CLI mode (workiq ask command), MCP server mode "
        "(integration with GitHub Copilot, Claude Desktop), Microsoft Graph API (emails, "
        "meetings, files, Teams messages), workplace insights, people-related information, "
        "meeting transcript retrieval, SharePoint document access, npm installation, admin "
        "consent and RBAC, GitHub Copilot CLI plugin setup, Work IQ vs Fabric IQ vs Foundry "
        "IQ, adaptive intelligence with Dataverse, and security/privacy considerations."
    ),
    "langchain-expert": (
        "LangChain is the leading framework for building agents and LLM-powered applications. "
        "Key topics: agents (ReAct, OpenAI Functions, structured tool calling), LCEL (LangChain "
        "Expression Language, pipe operator chains), RAG pipelines (document loaders, text "
        "splitters, embeddings, vector stores, retrievers), chat models and prompts, output "
        "parsers, memory systems, callbacks, tool calling, structured output, streaming, "
        "LangGraph (stateful graph-based agent orchestration, checkpoints, human-in-the-loop), "
        "LangSmith (tracing, evaluation, monitoring, observability), middleware and guardrails, "
        "1000+ integrations, and LangServe deployment."
    ),
    "llamaindex-expert": (
        "LlamaIndex is a data framework for RAG and agent applications. Key topics: "
        "Documents and Nodes (data primitives), indexing (VectorStoreIndex, SummaryIndex, "
        "TreeIndex, KeywordTableIndex), embeddings, query engines, retrievers, response "
        "synthesizers, node parsers and text splitters, AgentWorkflow (multi-agent "
        "orchestration, task handoffs), Workflows (event-driven step-based execution), "
        "agentic document workflows (ADW), LlamaParse (document parsing for complex PDFs), "
        "LlamaCloud, 300+ integration packages, evaluation modules, and production "
        "optimization (chunking strategies, retrieval tuning, observability)."
    ),
    "semantic-kernel": (
        "Microsoft Semantic Kernel is an AI orchestration SDK for C#, Python, and Java. "
        "Key topics: Kernel object (dependency injection container), plugins (native code, "
        "OpenAPI, MCP server), functions and function calling, planners (deprecated Stepwise/ "
        "Handlebars replaced by auto function calling), AI services (chat completion, text "
        "generation), prompts and prompt templates, vector store connectors (Azure AI Search, "
        "Chroma, Pinecone), text search, agent orchestration (sequential, concurrent, handoff, "
        "group chat), process framework (local and cloud runtime), enterprise readiness "
        "(filters, telemetry, middleware), and integration with Azure OpenAI."
    ),
    "autogen-expert": (
        "Microsoft AutoGen is a multi-agent AI framework for building conversational and "
        "event-driven agent systems. Key topics: AgentChat API (high-level, preset behaviors), "
        "Core API (event-driven, message passing), ConversableAgent, AssistantAgent, "
        "UserProxyAgent, GroupChat (speaker selection, resume), SelectorGroupChat, teams, "
        "code executors (Docker, local), MagenticOne multi-agent system, tools and custom "
        "functions, state management, AutoGen Studio (no-code UI), Extensions API (LLM "
        "clients, code execution), v0.4 redesign (async messaging, cross-language), and "
        "migration path to Microsoft Agent Framework."
    ),
    "crew-ai-expert": (
        "CrewAI is the leading open-source multi-agent orchestration framework. Key topics: "
        "agents (role-based design, manager/worker/researcher), tasks (descriptions, guardrails, "
        "async execution), crews (sequential and hierarchical processes, kickoff methods), "
        "flows (event-driven workflows, state management), tools (100+ built-in, custom tools, "
        "MCP integration), knowledge (agentic RAG), memory (short-term, long-term, entity, "
        "contextual, LanceDB-backed), planning agent, reasoning, training and testing, CLI, "
        "event listeners, production architecture, and observability (Langfuse, Datadog, MLflow)."
    ),
    "model-context-protocol": (
        "Deep dive into the MCP specification covering the complete protocol. Key topics: "
        "JSON-RPC 2.0 transport, specification versions (June 2025, November 2025), server "
        "primitives (tools, resources, prompts), client features (roots, sampling, elicitation), "
        "lifecycle management (initialization, capability negotiation, shutdown), transports "
        "(stdio, Streamable HTTP, SSE), authorization (OAuth Resource Servers, RFC 8707), "
        "Tasks primitive (async long-running operations), Python SDK, TypeScript SDK, security "
        "best practices, MCP Registry, .well-known discovery, and industry adoption (OpenAI, "
        "Google, Microsoft, 97M+ monthly SDK downloads)."
    ),
    "azure-ai-foundry": (
        "Azure AI Foundry (now Microsoft Foundry) is a unified platform for enterprise AI "
        "operations. Key topics: model catalog (1900+ models from OpenAI, Meta, Mistral, "
        "Anthropic), prompt flow (LLM app development, standard and chat flows, deployment "
        "as endpoints), fine-tuning (supervised SFT, reinforcement RFT, serverless and "
        "managed compute), deployments (standard, serverless API, managed compute), Foundry "
        "Agent Service (multi-agent orchestration, knowledge integration), evaluations "
        "(agent evaluation SDK, continuous monitoring), responsible AI (content safety, "
        "discover-protect-govern framework), RBAC, private link networking, and SDK "
        "integration (Python, C#, TypeScript, Java)."
    ),
    "kubernetes-networking": (
        "Kubernetes networking covers the full networking stack for container orchestration. "
        "Key topics: CNI plugins (Cilium with eBPF, Calico, Flannel), Services (ClusterIP, "
        "NodePort, LoadBalancer, ExternalName), EndpointSlices, DNS (CoreDNS, service "
        "discovery), ingress controllers (NGINX, HAProxy, Traefik), Gateway API (HTTPRoute, "
        "GRPCRoute, TLSRoute, GatewayClass, flexible conformance), network policies "
        "(ingress/egress rules, namespace isolation, L3/L4 filtering), service mesh (Istio "
        "ambient mode, Linkerd, Cilium service mesh), topology-aware routing, dual-stack "
        "networking (IPv4/IPv6), and kube-proxy replacement with eBPF."
    ),
    "opentelemetry-expert": (
        "OpenTelemetry is the CNCF observability framework for generating, collecting, and "
        "exporting telemetry data. Key topics: SDK instrumentation (Python, JavaScript, Go, "
        "Java - TracerProvider, MeterProvider, LoggerProvider), collector pipeline "
        "(receivers, processors, exporters, connectors, extensions), OTLP protocol "
        "(gRPC and HTTP/protobuf transports), semantic conventions (HTTP, database, "
        "messaging, RPC attributes), context propagation (W3C TraceContext, baggage), "
        "auto-instrumentation (zero-code, monkey patching, Kubernetes operator), "
        "exporter configuration (Jaeger, Prometheus, Zipkin, vendor backends), "
        "collector configuration best practices (batching, memory limits, filtering), "
        "and distributed tracing concepts (spans, traces, sampling)."
    ),
    "github-actions-advanced": (
        "Advanced GitHub Actions covers sophisticated CI/CD patterns and security. Key "
        "topics: reusable workflows (workflow_call trigger, inputs, outputs, secrets "
        "inheritance, nesting up to 10 levels), composite actions (step-level reuse, "
        "action.yml metadata), OIDC authentication (id-token permission, JWT claims, "
        "cloud provider federation for AWS/Azure/GCP, custom sub claims), environments "
        "(protection rules, required reviewers, deployment branches, environment secrets), "
        "matrix strategies (dynamic matrices, include/exclude, fail-fast, max-parallel), "
        "caching (actions/cache, dependency caching), artifacts (upload/download, retention), "
        "concurrency groups, workflow commands (set-output, add-mask, group), contexts and "
        "expressions, secrets management, self-hosted runners, and security hardening "
        "(pinning actions to SHA, GITHUB_TOKEN permissions, fork PR restrictions)."
    ),
    "vercel-ai-sdk": (
        "The Vercel AI SDK is a TypeScript toolkit for building AI-powered applications. "
        "Key topics: generateText and streamText for text generation, generateObject and "
        "streamObject for structured data, tool calling (single-step and multi-step with "
        "stopWhen), agents, AI SDK UI for chatbots and completions, provider integrations "
        "(OpenAI, Anthropic, Google, AWS Bedrock, Azure), middleware, RAG patterns, "
        "testing utilities, Generative UI with AI RSC, prompt engineering, streaming "
        "protocols, and lifecycle callbacks for observability."
    ),
    "anthropic-api-expert": (
        "The Anthropic Claude API provides access to Claude language models. Key topics: "
        "Messages API (create, stream, count tokens), server-sent events streaming, tool "
        "use and function calling, computer use tool for desktop automation, vision for "
        "image understanding, prompt caching (ephemeral 5-min and 1-hour TTL), extended "
        "thinking with thinking_delta events, structured output, Message Batches API for "
        "50% cost reduction, PDF support, citations, MCP integration, prompt engineering "
        "best practices, model selection (Opus, Sonnet, Haiku), rate limits, error "
        "handling, and Python/TypeScript SDK usage."
    ),
    "openai-api-expert": (
        "The OpenAI API provides access to GPT and reasoning models. Key topics: Chat "
        "Completions API, Responses API (recommended for new integrations), function "
        "calling with strict mode and structured outputs, embeddings (text-embedding-3 "
        "models with configurable dimensions), fine-tuning (supervised, DPO, reinforcement), "
        "Batch API for 50% cost reduction, vision capabilities, reasoning models (o3, o3-pro), "
        "Assistants API (deprecated, migrating to Responses), prompt engineering, safety "
        "best practices, latency optimization, and production deployment patterns."
    ),
    "huggingface-transformers": (
        "Hugging Face Transformers is a library for state-of-the-art pretrained models. "
        "Key topics: Pipeline API for inference (text generation, classification, QA, "
        "summarization, translation, image tasks, audio), tokenizers (AutoTokenizer, "
        "fast vs slow), Trainer API for fine-tuning with mixed precision and distributed "
        "training, PEFT (LoRA, IA3, AdaLoRA for parameter-efficient fine-tuning), "
        "quantization (bitsandbytes 4/8-bit, GPTQ, AWQ, HQQ), generation strategies "
        "(beam search, sampling, contrastive), model sharing on Hub, custom models, "
        "data collators, and performance optimization for GPU training."
    ),
    "dspy-expert": (
        "DSPy is a framework for programming (not prompting) language models. Key topics: "
        "signatures (input/output schemas replacing prompts), modules (ChainOfThought, "
        "ReAct, ProgramOfThought, Predict, RLM for recursive exploration, "
        "MultiChainComparison), optimizers (BootstrapFewShot for few-shot learning, "
        "MIPROv2 for prompt optimization, BootstrapFinetune, BetterTogether for "
        "composing optimizers), assertions and suggestions (dspy.Suggest, dspy.Refine), "
        "evaluation with custom metrics, retrieval models (ColBERTv2, ChromaRM), "
        "language model configuration via LiteLLM, and agent development patterns."
    ),
    "vscode-extensions": (
        "VS Code extension development using the Extension API. Key topics: extension "
        "anatomy (package.json manifest, activation events, contribution points), commands "
        "and keybindings, tree views (TreeDataProvider, TreeView), webviews (WebviewPanel, "
        "WebviewView, security with asWebviewUri), Language Server Protocol (LSP) for "
        "language features, custom editors, notebook API, debugger extensions (Debug Adapter "
        "Protocol), task providers, SCM providers, testing extensions (@vscode/test-electron), "
        "web extensions (@vscode/test-web), publishing to Marketplace (vsce), extension "
        "bundling (webpack/esbuild), UX guidelines, and remote development support."
    ),
    "docker-expert": (
        "Docker containerization platform. Key topics: Dockerfile reference (FROM, RUN, "
        "COPY, ENTRYPOINT, CMD, EXPOSE, VOLUME, USER, WORKDIR, ARG, ENV, HEALTHCHECK), "
        "multi-stage builds (COPY --from, named stages), Docker Compose v5 (Go SDK, "
        "compose.yaml, services, networks, volumes, depends_on, profiles), Docker Build "
        "(BuildKit, Bake, build cache, build secrets), networking (bridge, overlay, host, "
        "macvlan), volumes and bind mounts, security (non-root users, Docker Scout, "
        "content trust, secret management), image optimization, CLI reference, and "
        "language-specific containerization (Python, Node.js, Go, Java)."
    ),
    "terraform-expert": (
        "Terraform infrastructure as code by HashiCorp. Key topics: HCL configuration "
        "language (syntax, expressions, functions, dynamic blocks), providers (configuration, "
        "requirements, aliases, source addresses), modules (local, registry, composition, "
        "input variables, output values), state management (backends: local, remote, S3, "
        "Azure Blob; workspaces; state locking; remote state data source), CLI commands "
        "(init, plan, apply, destroy, import, workspace, state), HCP Terraform (Cloud) "
        "workspaces, resources and data sources, provisioners, lifecycle meta-arguments "
        "(create_before_destroy, prevent_destroy, ignore_changes), and deployment patterns."
    ),
    "react-expert": (
        "React 19+ with modern patterns and Server Components. Key topics: Server "
        "Components and Server Functions ('use server' directive), Actions with "
        "useActionState and useOptimistic for form handling, the use hook (reading "
        "promises and context in conditionals/loops), hooks (useState, useEffect, "
        "useCallback, useMemo, useRef, useReducer, useContext, useTransition, "
        "useDeferredValue, useId, useEffectEvent), Suspense boundaries for async UI, "
        "React DOM form integration, memo and lazy for performance, createContext, "
        "startTransition, rules of hooks, component composition, and error boundaries."
    ),
    "nextjs-expert": (
        "Next.js 15+ with App Router and Turbopack. Key topics: App Router (file-based "
        "routing with layouts, pages, loading, error, not-found conventions), Server "
        "Components and Server Actions ('use server'), Turbopack (default bundler, "
        "filesystem caching), data fetching (fetch with caching/revalidation, React "
        "cache, server components), ISR (Incremental Static Regeneration, revalidatePath, "
        "revalidateTag), middleware (authentication, redirects, headers), caching "
        "(Router Cache, Full Route Cache, Data Cache), route handlers, parallel routes, "
        "route groups, dynamic routes, environment variables, and deployment strategies."
    ),
}

# Difficulty distribution: ~40% easy, 40% medium, 20% hard
DIFFICULTY_DISTRIBUTION = [
    ("easy", 20),
    ("medium", 20),
    ("hard", 10),
]


def get_domain_name(pack_name: str) -> str:
    """Convert pack name to a clean domain identifier."""
    return pack_name.replace("-", "_").lower()


def sample_db_context(db_path: Path, max_articles: int = 20) -> str:
    """Sample article titles and content snippets from a pack database.

    Args:
        db_path: Path to the Kuzu pack database
        max_articles: Maximum number of articles to sample

    Returns:
        Formatted context string with article titles and snippets, or empty string on failure
    """
    try:
        import kuzu

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        result = conn.execute(f"MATCH (a:Article) RETURN a.title AS title LIMIT {max_articles}")
        df = result.get_as_df()
        if df.empty:
            logger.warning(f"No articles found in {db_path}")
            return ""

        titles = df["title"].tolist()

        result = conn.execute(
            "MATCH (a:Article)-[:HAS_SECTION]->(s:Section) "
            f"RETURN a.title AS title, s.content AS content LIMIT {max_articles}"
        )
        sections_df = result.get_as_df()

        context_parts = [f"Pack contains {len(titles)} articles including:", ""]
        for title in titles[:15]:
            context_parts.append(f"- {title}")

        if not sections_df.empty:
            context_parts.append("\nSample content snippets:")
            seen_titles: set[str] = set()
            for _, row in sections_df.iterrows():
                if row["title"] not in seen_titles and len(seen_titles) < 5:
                    snippet = str(row["content"])[:200].replace("\n", " ")
                    context_parts.append(f"\n[{row['title']}]: {snippet}...")
                    seen_titles.add(row["title"])

        return "\n".join(context_parts)

    except Exception as e:
        logger.warning(f"Could not query database {db_path}: {e}")
        return ""


def build_generation_prompt(
    pack_name: str,
    domain_description: str,
    db_context: str,
    difficulty: str,
    count: int,
    id_prefix: str,
    id_start: int,
) -> str:
    """Build the Claude prompt for generating evaluation questions."""
    domain_name = get_domain_name(pack_name)

    db_section = f"\n\nPACK DATABASE CONTEXT:\n{db_context}\n" if db_context else ""

    difficulty_guidance = {
        "easy": (
            "Easy questions test basic factual knowledge: definitions, key concepts, "
            "simple procedures. A junior practitioner should answer confidently."
        ),
        "medium": (
            "Medium questions require understanding of how things work, trade-offs, "
            "configuration details, or combining multiple concepts."
        ),
        "hard": (
            "Hard questions test deep expertise: edge cases, performance implications, "
            "security considerations, architecture decisions, or complex troubleshooting."
        ),
    }

    return f"""Generate exactly {count} {difficulty} evaluation questions for a knowledge pack about: {domain_description}
{db_section}
DIFFICULTY: {difficulty} — {difficulty_guidance[difficulty]}

OUTPUT FORMAT: Return a JSON array. Each element must have these exact fields:
- "id": string like "{id_prefix}_{id_start:03d}", "{id_prefix}_{id_start + 1:03d}", etc.
- "domain": "{domain_name}"
- "difficulty": "{difficulty}"
- "question": the question text (specific, testable, domain-relevant)
- "ground_truth": concise factual answer (1-3 sentences, technically accurate)
- "source": a short identifier for the relevant concept/feature (e.g., "authentication")

REQUIREMENTS:
- Questions must test REAL knowledge about {pack_name}, not generic concepts
- Questions must be diverse: cover different features, use cases, configurations
- ground_truth answers must be technically accurate and complete
- No duplicate or trivially similar questions
- Return ONLY the JSON array, no explanation

JSON array:"""


def parse_questions_from_response(
    response_text: str,
    expected_count: int,
    pack_name: str,
) -> list[dict]:
    """Parse and validate questions from Claude's response.

    Extracts the JSON array from the response text and validates each question
    has the required fields with valid values.
    """
    text = response_text.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array found in response: {text[:200]}")

    questions = json.loads(text[start:end])
    if not isinstance(questions, list):
        raise ValueError(f"Expected list, got {type(questions)}")

    domain_name = get_domain_name(pack_name)
    required_fields = {"id", "domain", "difficulty", "question", "ground_truth", "source"}
    valid_difficulties = {"easy", "medium", "hard"}

    validated = []
    for i, q in enumerate(questions):
        missing = required_fields - set(q.keys())
        if missing:
            logger.warning(f"Question {i} missing fields {missing}, skipping")
            continue
        if q["difficulty"] not in valid_difficulties:
            logger.warning(f"Question {i} invalid difficulty {q['difficulty']!r}, fixing to medium")
            q["difficulty"] = "medium"
        q["domain"] = domain_name
        validated.append(q)

    if len(validated) < expected_count * 0.8:
        logger.warning(f"Only {len(validated)}/{expected_count} valid questions parsed")

    return validated


def generate_questions_for_difficulty(
    client: anthropic.Anthropic,
    pack_name: str,
    domain_description: str,
    db_context: str,
    difficulty: str,
    count: int,
    id_prefix: str,
    id_start: int,
) -> list[dict]:
    """Call Claude to generate questions for one difficulty level."""
    prompt = build_generation_prompt(
        pack_name=pack_name,
        domain_description=domain_description,
        db_context=db_context,
        difficulty=difficulty,
        count=count,
        id_prefix=id_prefix,
        id_start=id_start,
    )

    logger.info(f"Generating {count} {difficulty} questions for {pack_name}...")

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text if response.content else ""
    questions = parse_questions_from_response(text, count, pack_name)
    logger.info(f"Generated {len(questions)} {difficulty} questions")
    return questions


def generate_eval_questions(
    pack_name: str,
    db_path: Path | None,
    output_dir: Path,
    total_count: int = DEFAULT_COUNT,
) -> list[dict]:
    """Generate all evaluation questions for a pack and save to output_dir.

    Args:
        pack_name: Pack name (e.g., 'azure-lighthouse')
        db_path: Optional Kuzu database path for context sampling
        output_dir: Directory to write questions.json and questions.jsonl
        total_count: Total questions to generate (default 50)

    Returns:
        List of generated question dicts
    """
    client = anthropic.Anthropic()

    domain_description = DOMAIN_DESCRIPTIONS.get(
        pack_name,
        f"Expert knowledge about {pack_name.replace('-', ' ').title()}",
    )

    db_context = ""
    if db_path and db_path.exists():
        logger.info(f"Sampling context from database: {db_path}")
        db_context = sample_db_context(db_path)
        if db_context:
            logger.info(f"Got DB context ({len(db_context)} chars)")
    else:
        logger.info(f"No database available, using domain knowledge for {pack_name}")

    # Scale difficulty counts to total_count
    base_total = sum(n for _, n in DIFFICULTY_DISTRIBUTION)
    difficulty_counts: dict[str, int] = {
        d: max(1, round(n * total_count / base_total)) for d, n in DIFFICULTY_DISTRIBUTION
    }
    # Fix rounding to hit exact total
    diff = total_count - sum(difficulty_counts.values())
    if diff != 0:
        difficulty_counts["medium"] += diff

    # Build 2-char ID prefix from pack name
    words = [w for w in pack_name.split("-") if w]
    id_prefix = "".join(w[0] for w in words)[:2].lower()
    if len(id_prefix) < 2:
        id_prefix = (id_prefix + pack_name[:2])[:2]

    all_questions: list[dict] = []
    id_counter = 1

    for difficulty, count in difficulty_counts.items():
        batch = generate_questions_for_difficulty(
            client=client,
            pack_name=pack_name,
            domain_description=domain_description,
            db_context=db_context,
            difficulty=difficulty,
            count=count,
            id_prefix=id_prefix,
            id_start=id_counter,
        )
        for q in batch:
            q["id"] = f"{id_prefix}_{id_counter:03d}"
            id_counter += 1
        all_questions.extend(batch)

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for q in all_questions:
        key = q["question"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(q)

    logger.info(f"Total unique questions: {len(unique)}")

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "questions.json"
    with open(json_path, "w") as f:
        json.dump(unique, f, indent=2)
        f.write("\n")
    logger.info(f"Saved JSON array: {json_path}")

    jsonl_path = output_dir / "questions.jsonl"
    with open(jsonl_path, "w") as f:
        for q in unique:
            f.write(json.dumps(q) + "\n")
    logger.info(f"Saved JSONL: {jsonl_path}")

    return unique


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate evaluation Q&A pairs for a knowledge pack using Claude"
    )
    parser.add_argument("--pack", required=True, help="Pack name (e.g., azure-lighthouse)")
    parser.add_argument("--db", help="Path to pack database (auto-detected if omitted)")
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Total questions to generate (default: {DEFAULT_COUNT})",
    )
    parser.add_argument("--output", help="Output directory (default: data/packs/{pack}/eval/)")
    args = parser.parse_args()

    if not re.match(r"^[a-zA-Z0-9_-]+$", args.pack):
        parser.error(
            f"Invalid pack name: {args.pack}. Must contain only letters, digits, hyphens, and underscores."
        )

    pack_name = args.pack

    db_path: Path | None = None
    if args.db:
        db_path = Path(args.db)
    else:
        auto_db = Path(f"data/packs/{pack_name}/pack.db")
        if auto_db.exists():
            db_path = auto_db
            logger.info(f"Auto-detected database: {db_path}")

    output_dir = Path(args.output) if args.output else Path(f"data/packs/{pack_name}/eval")

    try:
        questions = generate_eval_questions(
            pack_name=pack_name,
            db_path=db_path,
            output_dir=output_dir,
            total_count=args.count,
        )
        print(f"\nGenerated {len(questions)} evaluation questions for '{pack_name}'")
        print(f"  JSON:  {output_dir / 'questions.json'}")
        print(f"  JSONL: {output_dir / 'questions.jsonl'}")
    except anthropic.AuthenticationError:
        logger.error("ANTHROPIC_API_KEY is not set or invalid")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
