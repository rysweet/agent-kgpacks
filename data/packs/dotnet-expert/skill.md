# .NET Expert Knowledge Pack - Claude Code Skill

**Version**: 1.0.0
**Pack Name**: dotnet-expert
**Auto-load**: Yes

## Skill Description

Expert-level .NET knowledge covering C#, ASP.NET Core, Entity Framework Core, .NET Aspire, and modern architecture patterns. Provides authoritative answers with source citations from official Microsoft Learn documentation and expert community resources.

## Invocation Triggers

This skill is automatically invoked when the user asks questions about:

### C# Language
- C# syntax, features, and best practices
- Async/await and Task-based async pattern
- LINQ queries and expressions
- Generics, delegates, events
- Pattern matching and modern language features
- Memory management and garbage collection
- Performance optimization techniques

### ASP.NET Core
- Web API development (Minimal APIs, controllers)
- Middleware and request pipeline
- Dependency injection and configuration
- Authentication and authorization
- SignalR real-time communication
- gRPC services
- Blazor web applications
- Performance and caching strategies

### Entity Framework Core
- Database modeling and migrations
- Querying with LINQ
- Change tracking and unit of work
- Relationships and navigation properties
- Performance optimization
- Advanced features (temporal tables, owned entities)

### .NET Aspire
- Cloud-native application development
- Service discovery and orchestration
- Component integrations
- Telemetry and observability
- Azure Container Apps deployment

### Architecture & Patterns
- Clean Architecture and Vertical Slice Architecture
- CQRS and Event Sourcing
- Domain-Driven Design (DDD)
- Microservices patterns (Saga, Outbox)
- Repository and Specification patterns
- Result pattern for error handling
- Resilience patterns (Circuit Breaker, Retry)

## Keywords

```
.NET, C#, ASP.NET, ASP.NET Core, Entity Framework, EF Core, .NET Aspire,
async, await, LINQ, Task, MVC, Razor, Blazor, SignalR, gRPC,
Minimal API, Web API, middleware, dependency injection, DI,
DbContext, migrations, Clean Architecture, CQRS, DDD,
microservices, architecture patterns, resilience
```

## Usage Examples

```
User: "What are the benefits of Minimal APIs in ASP.NET Core?"
→ Loads dotnet-expert pack, provides comprehensive answer with sources

User: "How do I implement CQRS with MediatR in .NET?"
→ Provides architecture pattern guidance with code examples

User: "What's the difference between IEnumerable and IQueryable?"
→ Explains LINQ concepts with performance implications

User: "How do you configure service discovery in .NET Aspire?"
→ Provides Aspire-specific guidance with examples
```

## Integration

### With KG Agent

```python
from wikigr.agent.kg_agent import KGAgent

agent = KGAgent(db_path="data/packs/dotnet-expert/pack.db")
result = agent.query("How do you implement rate limiting in ASP.NET Core 7?")

print(result.answer)  # Comprehensive answer
print(result.sources)  # List of source URLs
```

### With Pack Manager

```python
from wikigr.packs import PackManager

manager = PackManager()
pack = manager.get_pack("dotnet-expert")

# Automatic skill registration
# Claude will use this pack for .NET questions
```

## Response Format

Responses include:

1. **Direct Answer**: Clear, concise explanation
2. **Code Examples**: Where applicable
3. **Best Practices**: Industry-standard recommendations
4. **Source Citations**: Links to official documentation
5. **Related Topics**: For deeper exploration

## Quality Assurance

- **Accuracy**: Sourced from official Microsoft Learn documentation
- **Currency**: Covers .NET 8/9/10, C# 12/13/14, ASP.NET Core 10
- **Expertise**: Includes community best practices from recognized experts
- **Evaluation**: Validated against 200 evaluation questions

## Limitations

- **Scope**: Focuses on .NET ecosystem (not Java, Python, etc.)
- **Version**: Primarily covers modern .NET (Core 6+)
- **Depth**: General knowledge pack, not specialized tooling
- **External Services**: Azure-focused for cloud, limited AWS/GCP

## Performance

- **Response Time**: < 2s with cache
- **Context Window**: Retrieves top 10 most relevant entities
- **Graph Depth**: Traverses 2 levels of relationships
- **Cache Hit Rate**: ~60% for common questions

## Maintenance

- **Update Frequency**: Quarterly or with major .NET releases
- **Source Validation**: URLs checked monthly
- **Content Refresh**: Re-crawl on official documentation updates

## Related Packs

- **fabric-graph-gql-expert**: Microsoft Fabric and GraphQL
- **azure-lighthouse**: Azure management and governance
- **security-copilot**: Security best practices

## Metadata

```json
{
  "name": "dotnet-expert",
  "version": "1.0.0",
  "build_date": "2026-02-26",
  "source_count": 250,
  "question_count": 200,
  "domains": ["csharp", "aspnet", "entity_framework", "aspire", "patterns"],
  "priority": 2,
  "status": "production"
}
```
