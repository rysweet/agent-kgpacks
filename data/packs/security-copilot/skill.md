# Microsoft Security Copilot Knowledge Pack — Claude Code Skill

**Version**: 1.0.0
**Pack Name**: security-copilot
**Auto-load**: Yes

## Skill Description

Expert knowledge of Microsoft Security Copilot covering AI-powered security analysis, threat intelligence enrichment, incident response automation, the plugin ecosystem, promptbooks, embedded experiences in Microsoft security products, capacity administration, and the Security Copilot API. Provides authoritative answers with source citations from official Microsoft Learn documentation.

## Invocation Triggers

This skill is automatically invoked when the user asks questions about:

### Getting Started & Core Usage
- What Microsoft Security Copilot is, how it works
- Setting up and provisioning Security Copilot
- Working with sessions in Security Copilot
- How to prompt Security Copilot effectively
- Prompting tips and best practices
- Conducting investigations in Security Copilot
- Uploading files for analysis

### Plugins & Integrations
- Available plugins for Security Copilot
- Enabling and managing plugins
- Microsoft Defender XDR plugin capabilities
- Microsoft Sentinel plugin capabilities
- Microsoft Intune plugin for device security
- Microsoft Entra plugin for identity security
- Microsoft Purview plugin for data security
- Defender Threat Intelligence (MDTI) plugin
- Defender EASM plugin for attack surface management
- Network Analyzer plugin
- Building custom API plugins, GPT plugins, KQL plugins

### Promptbooks
- What promptbooks are and how to use them
- Creating custom promptbooks
- Built-in promptbook library and use cases
- Running promptbooks for common security scenarios

### Embedded Experiences
- Security Copilot embedded in Microsoft Sentinel
- Security Copilot in Microsoft Defender XDR
- Security Copilot in Microsoft Intune
- Security Copilot in Microsoft Entra
- Defender Threat Intelligence AI enrichment

### Administration & Capacity
- Security Compute Units (SCUs) — what they are, pricing, provisioning
- Configuring and scaling SCU capacity
- Managing roles and access (analyst vs. owner vs. contributor)
- Monitoring usage and consumption
- Multi-tenant Security Copilot deployment

### Security, Compliance & API
- Data privacy and security in Security Copilot
- Responsible AI and limitations
- Audit logging for Security Copilot actions
- Programmatic access via the Security Copilot API
- Session API and promptbook API

## Keywords

```
Microsoft Security Copilot, Security Copilot, AI security,
promptbook, SCU, Security Compute Unit, plugin, Copilot session,
threat intelligence, incident response, security investigation,
Defender XDR, Microsoft Sentinel, Intune, Entra, Purview,
MDTI, EASM, custom plugin, KQL plugin, GPT plugin, API plugin,
embedded experience, security AI, SOC, analyst, MSSP
```

## Usage Examples

```
User: "What is Microsoft Security Copilot and how does it work?"
→ Loads security-copilot pack, explains AI-powered security analysis with sources

User: "How do I create a custom promptbook in Security Copilot?"
→ Provides step-by-step promptbook creation guidance

User: "What is a Security Compute Unit (SCU)?"
→ Explains SCU pricing model, provisioning, and capacity planning

User: "How does the Sentinel plugin work in Security Copilot?"
→ Explains Sentinel embedded experience and plugin capabilities

User: "How do I build a custom API plugin for Security Copilot?"
→ Provides plugin development guidance with schema and manifest details

User: "What data does Security Copilot store and for how long?"
→ Explains privacy policy, data retention, and residency options
```

## Integration

### With KG Agent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/security-copilot/pack.db",
    use_enhancements=True,
)
result = agent.query("How do I triage a security alert using Security Copilot?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

### With Pack Manager

```python
from wikigr.packs import PackManager

manager = PackManager()
pack = manager.get_pack("security-copilot")
# Claude will use this pack automatically for Security Copilot questions
```

## Response Format

Responses include:

1. **Direct Answer**: Clear explanation of the concept or feature
2. **Steps/Process**: Numbered steps for procedural questions
3. **Plugin/Feature Reference**: Which plugin or capability applies
4. **Best Practices**: Operational guidance from Microsoft
5. **Source Citations**: Links to official Microsoft Learn pages

## Quality Assurance

- **Accuracy**: Sourced entirely from official Microsoft Learn documentation
- **Currency**: Content reflects Security Copilot as of March 2026
- **Scope**: Covers full product lifecycle from setup to advanced customization

## Limitations

- **Pricing**: Exact SCU pricing may change; refer to Microsoft pricing pages for current rates
- **GA vs Preview**: Some features may be in preview; the pack reflects documentation state at build time
- **Region Availability**: Data residency options vary by region
- **Plugin Capabilities**: Individual plugin capabilities depend on the underlying product's plan

## Performance

- **Response Time**: < 2s with cache
- **Context Window**: Retrieves top 10 most relevant entities
- **Graph Depth**: Traverses 2 levels of relationships

## Related Packs

- **sentinel-graph**: Microsoft Sentinel SIEM/SOAR (Security Copilot has a Sentinel plugin)
- **azure-lighthouse**: Azure cross-tenant management (MSSP Sentinel + Copilot)
- **dotnet-expert**: .NET development

## Metadata

```json
{
  "name": "security-copilot",
  "version": "1.0.0",
  "build_date": "2026-03-03",
  "source_count": 58,
  "domains": ["security_copilot"],
  "category": "Microsoft Security Copilot",
  "priority": 3,
  "status": "production"
}
```
