# Azure Lighthouse Knowledge Pack

**Version**: 1.0.0
**Build Date**: 2026-03-03
**Status**: Production Ready

Expert knowledge of Azure Lighthouse covering delegated resource management, cross-tenant operations, managed services offers, MSSP scenarios, and Azure governance at scale.

## Overview

This knowledge pack provides comprehensive coverage of Azure Lighthouse — Microsoft's service for delegated resource management across Azure tenants. Content is sourced exclusively from official Microsoft Learn documentation. The pack is designed to support service providers, MSSPs, and enterprise teams managing multiple Azure tenants through a single control plane.

## Coverage

### Core Concepts (30%)
- **Architecture**: Azure Lighthouse architecture, how delegation works, tenant relationships
- **Delegated Resource Management**: Cross-tenant access model, authorization scopes, delegation flow
- **Managed Services Offers**: Azure Marketplace publishing, offer types, Lighthouse plans
- **Managed Applications vs Lighthouse**: When to use which, hybrid approaches

### Onboarding & Delegation (25%)
- **Customer Onboarding**: ARM template deployment, Azure portal onboarding, management group onboarding
- **Authorization Principals**: Users, groups, service principals, eligible authorizations (JIT)
- **Role Assignments**: Built-in roles supported, RBAC constraints, permanent vs eligible
- **Delegation Removal**: Customer-initiated removal, revoking access
- **Updating Delegations**: Re-deploying templates, modifying authorizations

### Governance & Policy (20%)
- **Policy at Scale**: Applying Azure Policy across delegated subscriptions
- **Policy Remediation**: Cross-tenant remediation tasks, managed identity requirements
- **Azure Arc Integration**: Managing hybrid infrastructure via Lighthouse + Arc
- **Monitoring at Scale**: Azure Monitor, activity logs, alert rules across tenants
- **Delegation Change Monitoring**: Activity log events, audit trails

### Security & Compliance (15%)
- **Recommended Security Practices**: Least privilege, PIM integration, JIT access
- **Tenants, Users and Roles**: Role constraints for cross-tenant access
- **Service Provider Activity**: Monitoring what service providers do in customer tenants
- **Cloud Solution Provider (CSP)**: Lighthouse + CSP together, CSP subscription management
- **Multitenant Organizations**: Enterprise cross-tenant management

### Operations & Integrations (10%)
- **Microsoft Sentinel Integration**: Managing Sentinel workspaces across tenants
- **Microsoft Defender Integration**: Cross-tenant Defender workspace management
- **Azure DevOps Integration**: DevOps pipelines that work across delegated tenants
- **API Management**: Deploying API Management across delegated subscriptions
- **Migration at Scale**: Cross-tenant migration scenarios
- **Partner Earned Credit**: Lighthouse eligibility for PEC
- **Terraform & REST API**: Infrastructure-as-code and programmatic access

## Sources

### Microsoft Learn — Azure Lighthouse (57 URLs)

All content is sourced from `learn.microsoft.com/en-us/azure/lighthouse/`.

**Key areas covered**:
- Overview and concepts (6 URLs)
- Onboarding and delegation how-tos (5 URLs)
- Azure Marketplace managed services (4 URLs)
- Security and compliance (4 URLs)
- Policy and governance (3 URLs)
- Monitoring and operations (3 URLs)
- Samples and ARM/Bicep templates (4 URLs)
- Related concepts (5 URLs)
- Azure RBAC for delegated management (2 URLs)
- Terraform, REST API, DevOps integration (5 URLs)
- Cross-tenant scenarios (4 URLs)
- Security operations (2 URLs)
- What's new, troubleshooting, FAQ (8 URLs)

## Statistics

- **Total URLs**: 57 (from `urls.txt`)
- **Expected Article Count**: 40-55 after deduplication (some URLs share page content)
- **Estimated Database Size**: ~30-80 MB
- **Evaluation Questions**: See `eval/` directory

## Installation

### From Distribution Archive

```bash
wikigr pack install azure-lighthouse-1.0.0.tar.gz
```

### From URL

```bash
wikigr pack install https://example.com/packs/azure-lighthouse-1.0.0.tar.gz
```

### Verify Installation

```bash
wikigr pack list
wikigr pack info azure-lighthouse
```

## Usage

### CLI Query

```bash
wikigr query --pack azure-lighthouse "What is Azure Lighthouse delegated resource management?"
wikigr query --pack azure-lighthouse "How do I onboard a customer to Azure Lighthouse?"
wikigr query --pack azure-lighthouse "What RBAC roles are supported for cross-tenant management?"
wikigr query --pack azure-lighthouse "How does Azure Lighthouse differ from Azure Managed Applications?"
```

### Python API

```python
from wikigr.packs import PackManager
from wikigr.agent.kg_agent import KGAgent

# Load pack
manager = PackManager()
pack = manager.get_pack("azure-lighthouse")

# Query knowledge graph
agent = KGAgent(db_path=pack.db_path)
result = agent.query("How do I publish a managed service offer in Azure Marketplace?")
print(result.answer)
print(result.sources)
```

### Direct KG Agent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/azure-lighthouse/pack.db",
    use_enhancements=True,
)

result = agent.query("What are eligible authorizations in Azure Lighthouse?")
print(result["answer"])
print(f"Sources: {result['sources']}")
print(f"Query type: {result['query_type']}")
```

### Claude Code Skill

The pack registers as a Claude Code skill for answering Azure Lighthouse questions.

```
User: "How do I set up cross-tenant monitoring with Azure Monitor?"
Claude: *loads azure-lighthouse pack and provides answer with source citations*
```

## Build Instructions

See [BUILD.md](BUILD.md) for complete build instructions.

Quick start:

```bash
# Test build (5 URLs, ~5-10 minutes)
uv run python scripts/build_azure_lighthouse_pack.py --test-mode

# Full build (57 URLs, ~3-5 hours)
uv run python scripts/build_azure_lighthouse_pack.py
```

## Evaluation

This pack includes evaluation questions in `eval/questions.jsonl`.

```bash
# Quick check
uv run python scripts/eval_single_pack.py azure-lighthouse --sample 5

# Full evaluation
uv run python scripts/eval_single_pack.py azure-lighthouse
```

### Expected Performance

| Metric | Expected |
|--------|----------|
| Overall Accuracy | 75-85% |
| Easy Questions | 85-95% |
| Medium Questions | 75-85% |
| Hard Questions | 60-75% |

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
- LadybugDB 0.15.0+
- 512 MB RAM minimum
- 500 MB disk space

## License

- **Content**: Microsoft Learn documentation (CC BY 4.0)
- **Code**: MIT License
- **Trademarks**: Azure, Azure Lighthouse are trademarks of Microsoft

## Related Packs

- **sentinel-graph**: Microsoft Sentinel SIEM/SOAR
- **security-copilot**: AI-powered security analysis
- **dotnet-expert**: .NET development

## Changelog

### Version 1.0.0 (2026-03-03)
- Initial release
- 57 URLs from Microsoft Learn Azure Lighthouse documentation
- Coverage: concepts, onboarding, governance, security, operations
