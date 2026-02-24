# WikiGR Documentation

Complete documentation for building knowledge graphs from Wikipedia and web content.

## Getting Started

New to WikiGR? Start here:

- [Getting Started with Web Content Sources](./tutorials/web-sources-getting-started.md) - Learn how to build knowledge graphs from web URLs with LLM extraction and link crawling

## How-To Guides

Task-oriented guides for specific problems:

- [How to Configure LLM Extraction](./howto/configure-llm-extraction.md) - Control entity and relationship extraction parameters
- [How to Filter Link Crawling](./howto/filter-link-crawling.md) - Control which links are followed during BFS crawling

## API Reference

Complete technical reference for classes and commands:

- [Web Content Source API](./reference/web-content-source.md) - `WebContentSource` class and CLI commands
- [ArticleProcessor API](./reference/article-processor.md) - Shared extraction pipeline for all content sources

## Concepts and Architecture

Understanding how WikiGR works internally:

- [ContentSource Architecture](./concepts/content-source-design.md) - Protocol-based design for source-agnostic knowledge graph construction
- [BFS Link Expansion Algorithm](./concepts/bfs-link-expansion.md) - How WikiGR crawls web content using breadth-first search

## Feature Overview

### Web Content Sources

Build knowledge graphs from web URLs with full feature parity to Wikipedia sources:

- **LLM Extraction**: GPT-4 powered entity and relationship extraction
- **Link Expansion**: BFS crawling with configurable depth and breadth
- **Incremental Updates**: Add new content without rebuilding entire graph
- **Flexible Filtering**: Control link following with domain and pattern filters

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

### Update Existing Graph

```bash
wikigr update \
  --source=web \
  --url="https://example.com/new-article" \
  --db-path=existing.db
```

### Configure LLM Extraction

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4-turbo-preview
export LLM_TEMPERATURE=0.0

wikigr create --source=web --url="..." --db-path=output.db
```

## Architecture Overview

```
┌─────────────────┐
│ Content Sources │
│ (Web, Wikipedia)│
└────────┬────────┘
         │ Article objects
         │
┌────────▼─────────────┐
│ ArticleProcessor     │
│ (LLM extraction)     │
└────────┬─────────────┘
         │ Entities, Relationships
         │
┌────────▼─────────────┐
│ Kuzu Database        │
│ (Knowledge Graph)    │
└──────────────────────┘
```

See [ContentSource Architecture](./concepts/content-source-design.md) for detailed design explanation.

## Documentation Organization

This documentation follows the [Diataxis framework](https://diataxis.fr/):

- **Tutorials**: Learning-oriented, step-by-step lessons
- **How-To Guides**: Task-oriented, solve specific problems
- **Reference**: Information-oriented, technical specifications
- **Concepts**: Understanding-oriented, explain design and rationale

## Contributing to Documentation

When adding documentation:

1. Place files in appropriate subdirectory (`tutorials/`, `howto/`, `reference/`, `concepts/`)
2. Link from this index or parent document
3. Use real, runnable examples (not "foo/bar" placeholders)
4. Follow one Diataxis type per document
5. Include descriptive headings for scanning

See `.claude/skills/documentation-writing/` for complete guidelines.

## Related Resources

- [Project README](../README.md) - Project overview and setup
- [WikiGR GitHub Repository](https://github.com/your-org/wikigr) *(update with real URL)*
- [Kuzu Database Documentation](https://kuzudb.com/docs/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
