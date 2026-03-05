# Microsoft Sentinel Knowledge Pack

**Version**: 1.0.0
**Build Date**: 2026-03-03
**Status**: Production Ready

Expert knowledge of Microsoft Sentinel covering SIEM architecture, data connectors, analytics and detection rules, incident management, threat hunting, SOAR automation, threat intelligence, UEBA, KQL queries, and multi-tenant/MSSP operations.

## Overview

This knowledge pack provides comprehensive coverage of Microsoft Sentinel — Microsoft's cloud-native SIEM (Security Information and Event Management) and SOAR (Security Orchestration, Automation and Response) solution. Content is sourced exclusively from official Microsoft Learn documentation under `learn.microsoft.com/en-us/azure/sentinel/`.

The pack is designed to help security analysts, SOC engineers, security architects, and MSSP operators build, tune, and operate Microsoft Sentinel environments effectively.

## Coverage

### Overview & Architecture (10%)
- **Sentinel Overview**: What Sentinel is, value proposition, pricing model
- **Prerequisites**: Workspace requirements, Log Analytics workspace setup
- **Deployment Overview**: Planning, sizing, and architecture decisions
- **Roles & Permissions**: RBAC roles for Sentinel, reader vs responder vs contributor
- **Best Practices**: Operational best practices for running Sentinel

### Data Connectors (20%)
- **Connector Reference**: Full list of available connectors and their status
- **Azure Native Connectors**: Azure Active Directory, Azure Activity, Office 365
- **Microsoft Security Connectors**: Defender for Cloud, Defender for Endpoint
- **Syslog & CEF**: Linux syslog connector, CEF (Common Event Format) over Syslog
- **Custom Connectors**: Building custom data connectors with the connector framework

### Analytics & Detection (20%)
- **Built-in Analytics Rules**: Using Microsoft security detection templates
- **Creating Analytics Rules**: Scheduled, NRT (near real-time), and fusion rules
- **KQL for Analytics**: Kusto Query Language overview in Sentinel context
- **Threat Intelligence Rules**: Integrating TI indicators into detection rules
- **Content Hub Rules**: Installing analytics rules from the content hub

### Incident Management (15%)
- **Investigating Cases**: The incident investigation workflow
- **UEBA in Incidents**: User and Entity Behavior Analytics enrichment
- **Hunting in Incidents**: Pivoting from incidents to threat hunting
- **Incident Investigation**: Collaborative incident response features

### Threat Hunting (10%)
- **Hunting Overview**: Pro-active threat hunting in Sentinel
- **Bookmarks**: Saving interesting query results during hunts
- **Notebooks**: Jupyter notebook integration for advanced hunting
- **Hunting with Notebooks**: Running ML-powered hunts

### SOAR & Automation (15%)
- **Automation Overview**: How automation works in Sentinel
- **Playbooks**: Logic Apps-based automated response playbooks
- **Creating Playbooks**: Building playbooks for common scenarios
- **Automation Rules**: Incident-level automation rules
- **Triggering Automation**: How incidents and alerts trigger automation

### Threat Intelligence (5%)
- **Understanding TI**: STIX/TAXII, TI platforms, indicators of compromise
- **Importing TI**: Connecting TAXII feeds and uploading indicator files
- **TI Analytics Rules**: Using indicators in detection

### Advanced Topics (5%)
- **UEBA**: Entity behavior analytics, anomaly scoring
- **Multi-tenant & MSSP**: Extending Sentinel across workspaces and tenants
- **Content Hub**: Installing solutions and content packs
- **SOC ML Anomalies**: Machine learning-based anomaly detection
- **Migration**: Migrating from legacy SIEMs to Sentinel

## Sources

### Microsoft Learn — Microsoft Sentinel (57 URLs)

All content is sourced from `learn.microsoft.com/en-us/azure/sentinel/`.

**Key areas covered**:
- Overview, prerequisites, deployment, roles, best practices (5 URLs)
- Getting started: quickstart, visibility, detection, investigation (4 URLs)
- Data connectors: reference, Azure native, Microsoft security, syslog/CEF, custom (10 URLs)
- Analytics and detection: built-in, custom, NRT, KQL, TI rules, content hub (5 URLs)
- Incident management and investigation (4 URLs)
- Threat hunting: overview, bookmarks, notebooks (4 URLs)
- SOAR and automation: automation, playbooks, automation rules (5 URLs)
- Threat intelligence: understanding, importing, rules (3 URLs)
- Workbooks and dashboards (2 URLs)
- Content hub and solutions (3 URLs)
- UEBA: analytics, enrichments (2 URLs)
- Multi-tenant and MSSP (2 URLs)
- KQL and queries (3 URLs)
- Security operations: best practices, SOC ML, schema reference (3 URLs)
- What's new, migration (2 URLs)

## Statistics

- **Total URLs**: 57 (from `urls.txt`)
- **Expected Article Count**: 45-55 after deduplication
- **Estimated Database Size**: ~35-100 MB
- **Evaluation Questions**: See `eval/` directory

## Installation

### From Distribution Archive

```bash
wikigr pack install sentinel-graph-1.0.0.tar.gz
```

### From URL

```bash
wikigr pack install https://example.com/packs/sentinel-graph-1.0.0.tar.gz
```

### Verify Installation

```bash
wikigr pack list
wikigr pack info sentinel-graph
```

## Usage

### CLI Query

```bash
wikigr query --pack sentinel-graph "How do I connect Azure Active Directory to Microsoft Sentinel?"
wikigr query --pack sentinel-graph "What is the difference between analytics rules and automation rules?"
wikigr query --pack sentinel-graph "How do I build a Sentinel playbook to auto-close false positive incidents?"
wikigr query --pack sentinel-graph "What KQL do I use to hunt for lateral movement?"
wikigr query --pack sentinel-graph "How do I manage Sentinel across multiple tenants?"
```

### Python API

```python
from wikigr.packs import PackManager
from wikigr.agent.kg_agent import KGAgent

manager = PackManager()
pack = manager.get_pack("sentinel-graph")

agent = KGAgent(db_path=pack.db_path)
result = agent.query("How do I create a near real-time (NRT) analytics rule in Sentinel?")
print(result.answer)
print(result.sources)
```

### Direct KG Agent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/sentinel-graph/pack.db",
    use_enhancements=True,
)
result = agent.query("How does UEBA work in Microsoft Sentinel?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

### Claude Code Skill

```
User: "How do I connect my Palo Alto firewall to Microsoft Sentinel?"
Claude: *loads sentinel-graph pack and provides connector setup guidance*
```

## Build Instructions

See [BUILD.md](BUILD.md) for complete build instructions.

Quick start:

```bash
# Test build (5 URLs, ~5-10 minutes)
uv run python scripts/build_sentinel_graph_pack.py --test-mode

# Full build (57 URLs, ~3-5 hours)
uv run python scripts/build_sentinel_graph_pack.py
```

## Evaluation

```bash
# Quick check
uv run python scripts/eval_single_pack.py sentinel-graph --sample 5

# Full evaluation
uv run python scripts/eval_single_pack.py sentinel-graph
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
- LadybugDB 0.15.0+
- 512 MB RAM minimum
- 500 MB disk space

## License

- **Content**: Microsoft Learn documentation (CC BY 4.0)
- **Code**: MIT License
- **Trademarks**: Microsoft Sentinel is a trademark of Microsoft

## Related Packs

- **security-copilot**: AI-powered security analysis (Security Copilot has a Sentinel plugin)
- **azure-lighthouse**: Azure cross-tenant management (used for MSSP Sentinel management)
- **dotnet-expert**: .NET development

## Changelog

### Version 1.0.0 (2026-03-03)
- Initial release
- 57 URLs from Microsoft Learn Microsoft Sentinel documentation
- Coverage: SIEM architecture, data connectors, analytics, incidents, hunting, SOAR, TI, UEBA, multi-tenant
