# Microsoft Fabric GraphQL Expert Knowledge Pack

**Version**: 1.0.0
**Build Date**: 2026-03-03
**Status**: Production Ready

Expert knowledge of Microsoft Fabric's GraphQL API for Fabric items, covering the GraphQL editor, schema introspection, authentication, pagination, filtering, mutations, security, performance, and integration with Fabric data sources including Lakehouse, Warehouse, and SQL database.

## Overview

This knowledge pack provides focused coverage of Microsoft Fabric's API for GraphQL — a managed GraphQL service that lets you expose Fabric data items (Lakehouse tables, Warehouse tables, SQL database tables) as a GraphQL API. Content is sourced from official Microsoft Learn documentation under `learn.microsoft.com/en-us/fabric/data-engineering/`.

The pack is designed for developers building applications that need to query Fabric data via GraphQL, data engineers configuring Fabric GraphQL endpoints, and architects designing Fabric-based data APIs.

## Coverage

### GraphQL API Core (35%)
- **Overview**: What the Fabric GraphQL API is, supported data sources, pricing
- **Getting Started**: Creating a GraphQL API item, adding data sources, first query
- **GraphQL Editor**: Using the built-in editor for schema exploration and query testing
- **Schema View**: Browsing the auto-generated GraphQL schema
- **Introspection & Schema Export**: Exporting the schema for client generation
- **VS Code Integration**: Using the Fabric extension in VS Code for GraphQL development
- **FAQ**: Common questions about the GraphQL API

### GraphQL Technical Details (30%)
- **Authentication**: Entra ID (Azure AD) authentication, service principals, token acquisition
- **Pagination**: Cursor-based and offset pagination, `first`/`after` arguments
- **Filtering**: Filter expressions, logical operators, comparison operators
- **Mutations**: Create, update, delete operations through GraphQL mutations
- **Connecting Applications**: Client libraries, sample code, endpoint URL format

### Integration & Best Practices (20%)
- **Security**: Row-level security, column-level security, workspace roles
- **Performance**: Query optimization, caching, large dataset handling
- **Monitoring**: Request metrics, error rates, latency monitoring in Fabric
- **Troubleshooting**: Common errors, debugging GraphQL queries

### Fabric Data Sources (15%)
- **Lakehouse**: Lakehouse overview, tables vs. files, Delta Lake format
- **Data Warehouse**: Warehouse overview, SQL endpoint, schemas
- **SQL Database**: Fabric SQL database, managed SQL in Fabric
- **Real-Time Intelligence**: Event streams and KQL databases (context)
- **OneLake**: Unified data lake, shortcuts, data sharing

## Sources

### Microsoft Learn — Microsoft Fabric GraphQL API (28 URLs)

Content is sourced from `learn.microsoft.com/en-us/fabric/`.

**Key areas covered**:
- GraphQL API core: overview, getting started, editor, connecting apps, introspection, FAQ, schema view, VS Code (8 URLs)
- Fabric core concepts: overview, trial, data engineering, data warehousing (4 URLs)
- Lakehouse and data sources: Lakehouse, warehouse, SQL database, real-time intelligence (4 URLs)
- GraphQL technical: authentication, pagination, filtering, mutations (4 URLs)
- Integration and best practices: security, performance, monitoring, troubleshooting (4 URLs)
- Related: Data Factory, Data Activator, OneLake, governance (4 URLs)

## Statistics

- **Total URLs**: 28 (from `urls.txt`)
- **Expected Article Count**: 22-28 after deduplication
- **Estimated Database Size**: ~15-50 MB
- **Evaluation Questions**: See `eval/` directory

## Installation

### From Distribution Archive

```bash
wikigr pack install fabric-graphql-expert-1.0.0.tar.gz
```

### From URL

```bash
wikigr pack install https://example.com/packs/fabric-graphql-expert-1.0.0.tar.gz
```

### Verify Installation

```bash
wikigr pack list
wikigr pack info fabric-graphql-expert
```

## Usage

### CLI Query

```bash
wikigr query --pack fabric-graphql-expert "How do I create a GraphQL API in Microsoft Fabric?"
wikigr query --pack fabric-graphql-expert "How does pagination work in Fabric GraphQL?"
wikigr query --pack fabric-graphql-expert "How do I authenticate my application to the Fabric GraphQL API?"
wikigr query --pack fabric-graphql-expert "Can I do mutations (writes) through Fabric GraphQL?"
```

### Python API

```python
from wikigr.packs import PackManager
from wikigr.agent.kg_agent import KGAgent

manager = PackManager()
pack = manager.get_pack("fabric-graphql-expert")

agent = KGAgent(db_path=pack.db_path)
result = agent.query("How do I filter results in a Fabric GraphQL query?")
print(result.answer)
print(result.sources)
```

### Direct KG Agent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/fabric-graphql-expert/pack.db",
    use_enhancements=True,
)
result = agent.query("What data sources can I expose through the Fabric GraphQL API?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

### Claude Code Skill

```
User: "How do I export the GraphQL schema from a Fabric API item?"
Claude: *loads fabric-graphql-expert pack and explains schema introspection and export*
```

## Build Instructions

See [BUILD.md](BUILD.md) for complete build instructions.

Quick start:

```bash
# Test build (5 URLs, ~5-10 minutes)
uv run python scripts/build_fabric_graphql_expert_pack.py --test-mode

# Full build (28 URLs, ~2-4 hours)
uv run python scripts/build_fabric_graphql_expert_pack.py
```

## Evaluation

```bash
# Quick check
uv run python scripts/eval_single_pack.py fabric-graphql-expert --sample 5

# Full evaluation
uv run python scripts/eval_single_pack.py fabric-graphql-expert
```

### Expected Performance

| Metric | Expected |
|--------|----------|
| Overall Accuracy | 78-88% |
| Easy Questions | 88-95% |
| Medium Questions | 78-86% |
| Hard Questions | 62-75% |

## Configuration

### KG Agent Config (`kg_config.json`)

```json
{
  "model": "claude-opus-4-6",
  "max_entities": 50,
  "max_relationships": 100,
  "embedding_model": "BAAI/bge-base-en-v1.5",
  "vector_search_k": 10,
  "graph_depth": 2,
  "enable_cache": true
}
```

## Requirements

- Python 3.10+
- Kuzu 0.3.0+
- 512 MB RAM minimum
- 300 MB disk space

## License

- **Content**: Microsoft Learn documentation (CC BY 4.0)
- **Code**: MIT License
- **Trademarks**: Microsoft Fabric is a trademark of Microsoft

## Notes on URL Coverage

This pack targets the Fabric GraphQL API specifically (28 URLs). It intentionally keeps scope narrow to avoid diluting the GraphQL-specific knowledge with general Fabric data platform content. For broader Fabric coverage, combine with a general Fabric pack.

## Related Packs

- **dotnet-expert**: Building .NET clients for Fabric APIs
- **sentinel-graph**: Microsoft Sentinel graph queries (related KQL/graph patterns)
- **azure-lighthouse**: Azure governance for Fabric workspaces in multi-tenant scenarios

## Changelog

### Version 1.0.0 (2026-03-03)
- Initial release
- 28 URLs from Microsoft Learn Fabric data engineering and GraphQL documentation
- Coverage: GraphQL API, authentication, pagination, filtering, mutations, security, performance
