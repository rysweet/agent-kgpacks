# Microsoft Sentinel Knowledge Pack — Claude Code Skill

**Version**: 1.0.0
**Pack Name**: sentinel-graph
**Auto-load**: Yes

## Skill Description

Expert knowledge of Microsoft Sentinel covering SIEM architecture and workspace design, data connectors, analytics and detection rules (scheduled, NRT, fusion), incident management, threat hunting, SOAR automation (playbooks, automation rules), threat intelligence, UEBA, KQL queries, content hub, and multi-tenant/MSSP operations. Provides authoritative answers with source citations from official Microsoft Learn documentation.

## Invocation Triggers

This skill is automatically invoked when the user asks questions about:

### Overview & Setup
- What Microsoft Sentinel is, how it differs from other SIEMs
- Log Analytics workspace requirements for Sentinel
- Deployment planning and architecture
- Sizing and cost estimation
- RBAC roles in Sentinel (reader, responder, contributor)
- Best practices for running Sentinel

### Data Connectors
- Connecting data sources to Microsoft Sentinel
- Azure native connectors: Azure AD, Office 365, Azure Activity
- Microsoft security connectors: Defender for Cloud, Defender for Endpoint
- Syslog and CEF connectors for Linux and network appliances
- Custom data connector development
- Data connector reference and connector catalog

### Analytics & Detection
- Built-in analytics rules and Microsoft security alert rules
- Creating scheduled analytics rules with KQL
- Near real-time (NRT) analytics rules
- Fusion detection for multi-stage attacks
- Threat intelligence-based detection rules
- Analytics rule templates from content hub

### Incident Management
- Incident investigation workflow
- Working with the incident timeline
- UEBA enrichment in incident details
- Collaborative incident response
- Incident comments, tasks, and closure

### Threat Hunting
- Pro-active threat hunting with KQL
- Using hunt queries and bookmarks
- Jupyter notebook integration for advanced hunting
- Machine learning-based hunting queries

### SOAR & Automation
- Logic Apps-based playbooks for automated response
- Creating and deploying playbooks
- Automation rules for incident-level automation
- Triggering playbooks from alerts and incidents
- Enrichment, notification, and remediation playbook patterns

### Threat Intelligence
- Connecting STIX/TAXII threat intelligence feeds
- Uploading indicators via file or API
- Threat intelligence analytics rules (IOC matching)
- Visualizing threat intelligence in workbooks

### KQL Queries
- Writing KQL queries for Sentinel
- Common Sentinel KQL patterns
- Sample queries from the documentation
- Kusto query language concepts in Sentinel context

### UEBA
- User and Entity Behavior Analytics in Sentinel
- Anomaly rules and ML-based detection
- UEBA enrichments for entities

### Multi-tenant & MSSP
- Managing Sentinel across multiple workspaces
- Service provider access to customer Sentinel workspaces
- Azure Lighthouse integration for MSSP scenarios

## Keywords

```
Microsoft Sentinel, Azure Sentinel, SIEM, SOAR,
data connector, analytics rule, incident, alert, threat hunting,
playbook, Logic App, automation rule, KQL, Kusto,
threat intelligence, STIX, TAXII, IOC, indicator,
UEBA, entity behavior, anomaly, fusion, NRT rule,
workbook, content hub, Sentinel solution,
multi-tenant, MSSP, Log Analytics workspace,
Defender for Endpoint, Defender for Cloud, Azure AD
```

## Usage Examples

```
User: "How do I connect Azure Active Directory to Microsoft Sentinel?"
→ Loads sentinel-graph pack, explains AAD connector configuration with sources

User: "What is the difference between an analytics rule and an automation rule?"
→ Explains detection vs. automation, with examples of each

User: "How do I create a near real-time (NRT) analytics rule?"
→ Provides step-by-step NRT rule creation guidance

User: "How can I automate incident response in Sentinel?"
→ Explains playbooks, automation rules, and when to use each

User: "How do I hunt for lateral movement in Sentinel?"
→ Provides KQL hunting queries and bookmarking workflow

User: "How do I manage multiple customers' Sentinel workspaces as an MSSP?"
→ Explains Azure Lighthouse integration and multi-workspace management

User: "What is UEBA and how does it enrich incidents?"
→ Explains User and Entity Behavior Analytics with enrichment examples
```

## Integration

### With KG Agent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/sentinel-graph/pack.db",
    use_enhancements=True,
)
result = agent.query("How do I create a Sentinel playbook that auto-closes false positive alerts?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

### With Pack Manager

```python
from wikigr.packs import PackManager

manager = PackManager()
pack = manager.get_pack("sentinel-graph")
# Claude will use this pack automatically for Microsoft Sentinel questions
```

## Response Format

Responses include:

1. **Direct Answer**: Clear explanation of the concept or procedure
2. **Steps/Process**: Numbered steps for setup and configuration tasks
3. **KQL Examples**: Query snippets where relevant
4. **Best Practices**: Operational and security recommendations
5. **Source Citations**: Links to official Microsoft Learn pages

## Quality Assurance

- **Accuracy**: Sourced entirely from official Microsoft Learn documentation
- **Currency**: Content reflects Microsoft Sentinel as of March 2026
- **Depth**: Covers the full Sentinel feature set from data ingestion to response automation

## Limitations

- **Portal UI**: Step-by-step portal navigation may change; prefer API/template guidance where possible
- **Pricing**: Sentinel cost varies by data volume and workspace; pricing pages may have changed
- **Third-party Connectors**: Coverage focused on Microsoft-maintained connectors; third-party connectors may have separate documentation
- **KQL Syntax**: KQL examples reflect documentation samples; test all queries in your workspace

## Performance

- **Response Time**: < 2s with cache
- **Context Window**: Retrieves top 10 most relevant entities
- **Graph Depth**: Traverses 2 levels of relationships

## Related Packs

- **security-copilot**: AI-powered security analysis (Security Copilot has a Sentinel plugin)
- **azure-lighthouse**: Azure cross-tenant management (used for MSSP Sentinel operations)
- **dotnet-expert**: .NET development (for building Sentinel integrations)

## Metadata

```json
{
  "name": "sentinel-graph",
  "version": "1.0.0",
  "build_date": "2026-03-03",
  "source_count": 57,
  "domains": ["microsoft_sentinel"],
  "category": "Microsoft Sentinel",
  "priority": 3,
  "status": "production"
}
```
