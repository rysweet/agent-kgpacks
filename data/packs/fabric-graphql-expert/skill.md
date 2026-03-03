# Microsoft Fabric GraphQL Expert Knowledge Pack — Claude Code Skill

**Version**: 1.0.0
**Pack Name**: fabric-graphql-expert
**Auto-load**: Yes

## Skill Description

Expert knowledge of Microsoft Fabric's API for GraphQL covering the GraphQL editor, schema introspection, authentication with Microsoft Entra ID, pagination, filtering, mutations, security, performance optimization, monitoring, and integration with Fabric data sources (Lakehouse, Warehouse, SQL database). Provides authoritative answers with source citations from official Microsoft Learn documentation.

## Invocation Triggers

This skill is automatically invoked when the user asks questions about:

### Fabric GraphQL API Core
- What the Microsoft Fabric GraphQL API is and what it supports
- Creating a GraphQL API item in a Fabric workspace
- Adding data sources (Lakehouse tables, Warehouse tables, SQL database) to a GraphQL API
- Using the built-in Fabric GraphQL editor
- Exploring the auto-generated GraphQL schema
- Exporting the GraphQL schema for client code generation
- Using the VS Code Fabric extension for GraphQL development
- Frequently asked questions about Fabric GraphQL

### GraphQL Technical Details
- Authenticating applications to the Fabric GraphQL endpoint (Entra ID, service principal, OAuth2)
- Implementing pagination in Fabric GraphQL queries
- Using filters and filter expressions in queries
- Creating GraphQL mutations to insert, update, or delete data
- Connecting .NET, JavaScript, Python, and other clients to Fabric GraphQL

### Security & Best Practices
- Row-level security and column-level security with GraphQL
- Workspace roles and permissions for GraphQL APIs
- Performance optimization for large queries
- Monitoring GraphQL API usage and error rates
- Troubleshooting common GraphQL errors

### Fabric Data Platform Context
- Microsoft Fabric overview and platform concepts
- Fabric Lakehouse and Delta tables
- Fabric Data Warehouse SQL endpoint
- Fabric SQL database
- OneLake as the unified storage layer
- Real-time Intelligence in Fabric

## Keywords

```
Microsoft Fabric, Fabric GraphQL, API for GraphQL,
GraphQL API, Fabric API, Lakehouse, Data Warehouse,
SQL database, OneLake, Fabric workspace,
GraphQL schema, introspection, mutation, query, filter,
pagination, cursor, Entra ID authentication, service principal,
OAuth2, token, GraphQL editor, schema view, VS Code,
GraphQL endpoint, data engineering, Fabric item
```

## Usage Examples

```
User: "How do I create a GraphQL API in Microsoft Fabric?"
→ Loads fabric-graphql-expert pack, walks through creating a GraphQL API item

User: "How does pagination work in Fabric GraphQL?"
→ Explains cursor-based and offset pagination with query examples

User: "How do I authenticate my .NET app to the Fabric GraphQL API?"
→ Provides Entra ID authentication flow with code examples

User: "Can I do write operations (mutations) through Fabric GraphQL?"
→ Explains mutation support, limitations, and examples

User: "How do I filter GraphQL results in Microsoft Fabric?"
→ Explains filter expressions, operators, and combined conditions

User: "How do I export the GraphQL schema from my Fabric API?"
→ Explains schema introspection and schema export for client generation
```

## Integration

### With KG Agent

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

### With Pack Manager

```python
from wikigr.packs import PackManager

manager = PackManager()
pack = manager.get_pack("fabric-graphql-expert")
# Claude will use this pack automatically for Fabric GraphQL questions
```

## Response Format

Responses include:

1. **Direct Answer**: Clear explanation of the concept or API behavior
2. **GraphQL Examples**: Query, mutation, or schema snippets where applicable
3. **Code Samples**: Authentication code and client integration examples
4. **Best Practices**: Performance and security recommendations
5. **Source Citations**: Links to official Microsoft Learn pages

## Quality Assurance

- **Accuracy**: Sourced from official Microsoft Learn documentation
- **Currency**: Content reflects Fabric GraphQL API as of March 2026
- **Scope**: Focused on the GraphQL API feature specifically (not general Fabric)

## Limitations

- **Feature Maturity**: Fabric GraphQL API is a newer feature; some advanced scenarios may lack full documentation coverage
- **URL Count**: This pack has 28 URLs (intentionally focused); not all edge cases are covered
- **Write Operations**: Mutation support may be limited; check latest documentation for current status
- **Pricing**: Fabric capacity pricing and GraphQL-specific billing are subject to change

## Performance

- **Response Time**: < 2s with cache
- **Context Window**: Retrieves top 10 most relevant entities
- **Graph Depth**: Traverses 2 levels of relationships

## Related Packs

- **dotnet-expert**: Building .NET clients for Fabric APIs (ASP.NET Core, HttpClient)
- **azure-lighthouse**: Azure governance for Fabric workspace management
- **sentinel-graph**: Graph-based knowledge retrieval patterns

## Metadata

```json
{
  "name": "fabric-graphql-expert",
  "version": "1.0.0",
  "build_date": "2026-03-03",
  "source_count": 28,
  "domains": ["fabric_graphql"],
  "category": "Microsoft Fabric GraphQL",
  "priority": 3,
  "status": "production"
}
```
