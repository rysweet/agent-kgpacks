# Azure Lighthouse Knowledge Pack — Claude Code Skill

**Version**: 1.0.0
**Pack Name**: azure-lighthouse
**Auto-load**: Yes

## Skill Description

Expert knowledge of Azure Lighthouse covering delegated resource management, cross-tenant management, managed services offers, Azure Marketplace publishing, policy and governance at scale, monitoring, security best practices, and MSSP scenarios. Provides authoritative answers with source citations from official Microsoft Learn documentation.

## Invocation Triggers

This skill is automatically invoked when the user asks questions about:

### Azure Lighthouse Core
- Azure Lighthouse overview, architecture, and concepts
- Delegated resource management
- Cross-tenant management experiences
- Managed services offers and plans
- Azure Marketplace publishing for managed services
- ISV scenarios and enterprise multi-tenant management

### Onboarding & Delegation
- Onboarding customers to Azure Lighthouse
- Creating and deploying ARM templates for delegation
- Eligible authorizations and JIT (just-in-time) access
- Modifying or removing delegations
- Management group onboarding

### RBAC & Security
- Role assignments for cross-tenant management
- Which Azure built-in roles are supported
- Recommended security practices for service providers
- Service provider activity monitoring
- CSP (Cloud Solution Provider) + Lighthouse integration
- Tenant, user, and role concepts

### Governance & Policy
- Applying Azure Policy across delegated subscriptions
- Policy remediation at scale
- Azure Arc + Lighthouse for hybrid infrastructure
- Monitoring across tenants with Azure Monitor
- Delegation change activity logs

### Operations & Integrations
- Microsoft Sentinel workspace management across tenants
- Microsoft Defender for Cloud cross-tenant management
- Azure DevOps integration with delegated subscriptions
- Partner Earned Credit (PEC) eligibility
- Terraform and REST API for Lighthouse

## Keywords

```
Azure Lighthouse, delegated resource management, cross-tenant, managed services,
MSSP, service provider, Azure Marketplace, managed services offer,
delegation, eligible authorization, JIT access, Azure RBAC,
policy at scale, Azure Monitor, multi-tenant, Azure Arc,
Microsoft Sentinel, Defender, partner earned credit, PEC,
onboarding, ARM template, Bicep, tenant management
```

## Usage Examples

```
User: "What is Azure Lighthouse delegated resource management?"
→ Loads azure-lighthouse pack, explains the core delegation model with sources

User: "How do I onboard a customer to Azure Lighthouse?"
→ Provides step-by-step ARM template deployment instructions

User: "What RBAC roles can service providers use in Azure Lighthouse?"
→ Lists supported built-in roles and constraints for cross-tenant access

User: "How does Azure Lighthouse compare to Azure Managed Applications?"
→ Explains the key differences and when to use each approach

User: "How do I apply Azure Policy across my delegated subscriptions?"
→ Explains policy at scale and remediation task requirements

User: "How can I monitor what my service provider is doing in my Azure subscription?"
→ Explains Azure Activity Log and service provider activity view
```

## Integration

### With KG Agent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/azure-lighthouse/pack.db",
    use_enhancements=True,
)
result = agent.query("How do I create eligible authorizations for JIT access?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

### With Pack Manager

```python
from wikigr.packs import PackManager

manager = PackManager()
pack = manager.get_pack("azure-lighthouse")
# Claude will use this pack automatically for Azure Lighthouse questions
```

## Response Format

Responses include:

1. **Direct Answer**: Clear explanation of the concept or procedure
2. **Steps/Process**: Numbered steps where a procedure is described
3. **ARM/Bicep Snippets**: Where template content is relevant
4. **Best Practices**: Security and operational recommendations
5. **Source Citations**: Links to official Microsoft Learn pages
6. **Related Topics**: For further reading

## Quality Assurance

- **Accuracy**: Sourced entirely from official Microsoft Learn documentation
- **Currency**: Content reflects Azure Lighthouse as of March 2026
- **Scope**: Covers all major Lighthouse workflows from onboarding to operations

## Limitations

- **Scope**: Focuses on Azure Lighthouse; does not cover all Azure governance topics
- **Version**: Reflects documentation as of the build date (March 2026)
- **Pricing**: Does not include Azure Marketplace offer pricing details
- **Portal UI**: Step-by-step portal navigation may change; prefer ARM/Bicep guidance

## Performance

- **Response Time**: < 2s with cache
- **Context Window**: Retrieves top 10 most relevant entities
- **Graph Depth**: Traverses 2 levels of relationships

## Related Packs

- **sentinel-graph**: Microsoft Sentinel SIEM/SOAR operations
- **security-copilot**: AI-powered security analysis and incident response
- **dotnet-expert**: .NET development

## Metadata

```json
{
  "name": "azure-lighthouse",
  "version": "1.0.0",
  "build_date": "2026-03-03",
  "source_count": 57,
  "domains": ["azure_lighthouse"],
  "category": "Azure Lighthouse",
  "priority": 3,
  "status": "production"
}
```
