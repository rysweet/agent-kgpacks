# WikiGR Documentation

Complete documentation for building knowledge graphs from Wikipedia and web content, plus reusable knowledge packs for domain expertise.

## Getting Started

New to WikiGR? Start here:

- [Getting Started with Web Content Sources](./tutorials/web-sources-getting-started.md) - Learn how to build knowledge graphs from web URLs with LLM extraction and link crawling

## Design Documents

- [Knowledge Packs Design](./design/knowledge-packs.md) - Reusable graph-enhanced agent skills for domain expertise
- [CLI Pack Commands](./CLI_PACK_COMMANDS.md) - Complete reference for pack management commands

## Knowledge Packs

Pre-built domain-specific knowledge graphs:

- [Physics-Expert Pack](./packs/physics-expert/README.md) - 5,247 articles covering classical mechanics, quantum mechanics, thermodynamics, and relativity
  - [Evaluation Results](./packs/physics-expert/EVALUATION.md) - 84.7% accuracy vs 71.5% web search baseline
- [How to Create Your Own Pack](./packs/HOW_TO_CREATE_YOUR_OWN.md) - Step-by-step guide for building custom knowledge packs

## How-To Guides

Task-oriented guides for specific problems:

- [Multi-Query Retrieval and Content Quality Scoring](./howto/retrieval-enhancements.md) - Enable multi-query fan-out (+15–25% recall) and stub filtering via `enable_multi_query` and quality threshold
- [Phase 1 Pack Enhancements](./howto/phase1-enhancements.md) - Use retrieval enhancements to improve pack accuracy from 50% to 70-75%
- [Vector Search as Primary Retrieval](./howto/vector-search-primary-retrieval.md) - Phase 3 retrieval pipeline with vector-first search, sparse graph detection, and A/B testing flags
- [Generating Evaluation Questions](./howto/generating-evaluation-questions.md) - Generate Q&A pairs for new packs and run all-packs accuracy evaluation
- [Improving .NET Pack Content Quality](./howto/dotnet-content-quality.md) - Audit article content, fix hallucinated URLs, set minimum content threshold
- [How to Configure LLM Extraction](./howto/configure-llm-extraction.md) - Control entity and relationship extraction parameters
- [How to Filter Link Crawling](./howto/filter-link-crawling.md) - Control which links are followed during BFS crawling

## API Reference

Complete technical reference for classes and commands:

- [Retrieval Enhancements API](./reference/retrieval-enhancements.md) - `_multi_query_retrieve`, `_score_section_quality`, `enable_multi_query`, `CONTENT_QUALITY_THRESHOLD`
- [Phase 1 Enhancements API](./reference/phase1-enhancements.md) - GraphReranker, MultiDocSynthesizer, FewShotManager complete reference
  - [GraphReranker Module](./reference/module-docs/graph-reranker.md) - Graph-based reranking with PageRank
  - [MultiDocSynthesizer Module](./reference/module-docs/multidoc-synthesizer.md) - Multi-document retrieval and synthesis
  - [FewShotManager Module](./reference/module-docs/few-shot-manager.md) - Few-shot example injection
- [Web Content Source API](./reference/web-content-source.md) - `WebContentSource` class and CLI commands
- [ArticleProcessor API](./reference/article-processor.md) - Shared extraction pipeline for all content sources

## Concepts and Architecture

Understanding how WikiGR works internally:

- [Multi-Query Retrieval and Quality Scoring Design](./concepts/retrieval-enhancements-design.md) - Design rationale for Issue 211 Improvements 4 and 5
- [Phase 1 Enhancements Design](./concepts/phase1-enhancements-design.md) - Design rationale and architecture for retrieval enhancements
- [ContentSource Architecture](./concepts/content-source-design.md) - Protocol-based design for source-agnostic knowledge graph construction
- [BFS Link Expansion Algorithm](./concepts/bfs-link-expansion.md) - How WikiGR crawls web content using breadth-first search

## Feature Overview

### Web Content Sources

Build knowledge graphs from web URLs with full feature parity to Wikipedia sources:

- **LLM Extraction**: GPT-4 powered entity and relationship extraction
- **Link Expansion**: BFS crawling with configurable depth and breadth
- **Incremental Updates**: Add new content without rebuilding entire graph
- **Flexible Filtering**: Control link following with domain and pattern filters

### Knowledge Packs

Reusable graph-enhanced agent skills that surpass training data and web search:

- **Bundled Distribution**: Graph DB + Skill + Retrieval + Evaluation
- **3-Baseline Evaluation**: Prove packs beat training and web search
- **Skills Integration**: Auto-discovered as Claude Code skills
- **CLI Management**: 8 commands for pack lifecycle (create, install, eval, etc.)

### Supported Content Sources

| Source | Status | Documentation |
|--------|--------|---------------|
| Wikipedia | ✓ Production | [Wikipedia API docs](./reference/wikipedia-source.md) *(planned)* |
| Web (HTTP/HTTPS) | ✓ Production | [Web Content Source API](./reference/web-content-source.md) |
| Local Files | ⏳ Planned | - |
| GitHub Wiki | ⏳ Planned | - |

### Shared Features Across All Sources

All content sources use the same extraction pipeline via `ArticleProcessor`:

- **Entity Extraction**: Identify named entities (people, organizations, technologies, concepts)
- **Relationship Extraction**: Discover semantic relationships between entities
- **Vector Embeddings**: Generate embeddings for semantic search
- **Graph Construction**: Create nodes and edges in Kuzu database

## Quick Reference

### Create Knowledge Graph from Web

```bash
# Single page
wikigr create --source=web --url="https://example.com/article" --db-path=output.db

# With link expansion
wikigr create \
  --source=web \
  --url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks" \
  --max-depth=2 \
  --max-links=50 \
  --db-path=azure_aks.db
```

### Create and Use Knowledge Packs

```bash
# Create pack
wikigr pack create --name physics-expert \
  --source wikipedia --topics physics.txt \
  --target 5000

# Install and use
wikigr pack install physics-expert.tar.gz
wikigr pack eval physics-expert  # Proves it surpasses training data
```

## Documentation Organization

This documentation follows the [Diataxis framework](https://diataxis.fr/):

- **Tutorials**: Learning-oriented, step-by-step lessons
- **How-To Guides**: Task-oriented, solve specific problems
- **Reference**: Information-oriented, technical specifications
- **Concepts**: Understanding-oriented, explain design and rationale

## Related Resources

- [Project README](../README.md) - Project overview and setup
- [WikiGR GitHub Repository](https://github.com/rysweet/wikigr)
- [Kuzu Database Documentation](https://kuzudb.com/docs/)
