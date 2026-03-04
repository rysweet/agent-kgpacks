# Microsoft Security Copilot Knowledge Pack

**Version**: 1.0.0
**Build Date**: 2026-03-03
**Status**: Production Ready

Expert knowledge of Microsoft Security Copilot covering AI-powered security analysis, threat intelligence, incident response, plugin ecosystem, promptbooks, embedded experiences, and administration.

## Overview

This knowledge pack provides comprehensive coverage of Microsoft Security Copilot — Microsoft's generative AI security product that combines the power of large language models with security-specific skills and threat intelligence from Microsoft. Content is sourced exclusively from official Microsoft Learn documentation under `learn.microsoft.com/en-us/copilot/security/`.

The pack is designed to help security analysts, SOC teams, security architects, and IT administrators get the most out of Security Copilot's capabilities for threat investigation, incident response, and security operations.

## Coverage

### Core Concepts & Getting Started (20%)
- **Overview**: What Security Copilot is, key capabilities, licensing model
- **Getting Started**: Provisioning, first session setup, portal navigation
- **Sessions**: Working with Security Copilot sessions, session management
- **Prompting**: Natural language prompting, prompting tips and best practices
- **Investigations**: Conducting investigations using Security Copilot
- **File Upload**: Uploading files for analysis
- **FAQ and Privacy**: Common questions, data handling, privacy commitments

### Plugins & Integrations (25%)
- **Plugin Overview**: How plugins extend Security Copilot capabilities
- **Managing Plugins**: Enabling, disabling, and configuring plugins
- **Microsoft First-Party Plugins**:
  - Microsoft Defender XDR
  - Microsoft Sentinel
  - Microsoft Intune
  - Microsoft Entra
  - Microsoft Purview
  - Microsoft Defender Threat Intelligence (MDTI)
  - Microsoft Defender EASM
  - Network Analyzer
- **Custom Plugins**: Building API plugins, GPT plugins, KQL plugins

### Promptbooks (15%)
- **Using Promptbooks**: Running built-in and custom promptbooks
- **Creating Promptbooks**: Building and sharing custom promptbooks
- **Promptbook Library**: Available built-in promptbooks and their use cases

### Embedded Experiences (15%)
- **Embedded Experiences Overview**: Security Copilot within Microsoft products
- **Microsoft Sentinel**: Security Copilot embedded in Sentinel incidents
- **Microsoft Defender XDR**: Embedded in Defender XDR alerts and incidents
- **Microsoft Intune**: Device management AI assistance
- **Microsoft Entra**: Identity and access AI assistance
- **Defender Threat Intelligence**: AI-enriched threat reports

### Administration & Capacity (15%)
- **Provisioning SCUs**: Security Compute Units pricing and provisioning
- **Capacity Configuration**: Managing SCU capacity, scaling
- **Role Management**: Admin and analyst roles, RBAC
- **Usage Monitoring**: Tracking SCU consumption
- **Multi-tenant**: Operating Security Copilot across tenants

### Security, Compliance & API (10%)
- **Privacy & Data Security**: Data residency, retention, protection
- **Responsible AI**: AI principles, limitations, feedback
- **Audit & Logging**: Audit trail for Security Copilot actions
- **API Overview**: Programmatic access to Security Copilot
- **API Reference**: Session API, promptbook API endpoints

## Sources

### Microsoft Learn — Security Copilot (58 URLs)

All content is sourced from `learn.microsoft.com/en-us/copilot/security/`.

**Key areas covered**:
- Overview, getting started, quickstarts (5 URLs)
- Core concepts: sessions, investigations, prompting (5 URLs)
- Plugin management and first-party plugins (10 URLs)
- Custom plugins: API, GPT, KQL (4 URLs)
- Promptbooks: using, creating, library (3 URLs)
- Embedded experiences (6 URLs)
- Administration and capacity management (5 URLs)
- Security and compliance (3 URLs)
- Use cases and scenarios (5 URLs)
- API reference (3 URLs)
- What's new, release notes, troubleshooting, FAQ (6 URLs)
- Audit and logging, usage management (3 URLs)

## Statistics

- **Total URLs**: 58 (from `urls.txt`)
- **Expected Article Count**: 45-55 after deduplication
- **Estimated Database Size**: ~30-90 MB
- **Evaluation Questions**: See `eval/` directory

## Installation

### From Distribution Archive

```bash
wikigr pack install security-copilot-1.0.0.tar.gz
```

### From URL

```bash
wikigr pack install https://example.com/packs/security-copilot-1.0.0.tar.gz
```

### Verify Installation

```bash
wikigr pack list
wikigr pack info security-copilot
```

## Usage

### CLI Query

```bash
wikigr query --pack security-copilot "What is Microsoft Security Copilot?"
wikigr query --pack security-copilot "How do I create a custom promptbook?"
wikigr query --pack security-copilot "What plugins are available for Security Copilot?"
wikigr query --pack security-copilot "How do I provision Security Compute Units?"
```

### Python API

```python
from wikigr.packs import PackManager
from wikigr.agent.kg_agent import KGAgent

manager = PackManager()
pack = manager.get_pack("security-copilot")

agent = KGAgent(db_path=pack.db_path)
result = agent.query("How does Security Copilot integrate with Microsoft Sentinel?")
print(result.answer)
print(result.sources)
```

### Direct KG Agent

```python
from wikigr.agent.kg_agent import KnowledgeGraphAgent

agent = KnowledgeGraphAgent(
    db_path="data/packs/security-copilot/pack.db",
    use_enhancements=True,
)
result = agent.query("What are the best practices for prompting Security Copilot?")
print(result["answer"])
print(f"Sources: {result['sources']}")
```

### Claude Code Skill

```
User: "How do I triage alerts with Security Copilot?"
Claude: *loads security-copilot pack and provides answer with source citations*
```

## Build Instructions

See [BUILD.md](BUILD.md) for complete build instructions.

Quick start:

```bash
# Test build (5 URLs, ~5-10 minutes)
uv run python scripts/build_security_copilot_pack.py --test-mode

# Full build (58 URLs, ~3-5 hours)
uv run python scripts/build_security_copilot_pack.py
```

## Evaluation

```bash
# Quick check
uv run python scripts/eval_single_pack.py security-copilot --sample 5

# Full evaluation
uv run python scripts/eval_single_pack.py security-copilot
```

### Expected Performance

| Metric | Expected |
|--------|----------|
| Overall Accuracy | 75-85% |
| Easy Questions | 85-90% |
| Medium Questions | 75-83% |
| Hard Questions | 60-72% |

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
- **Trademarks**: Microsoft Security Copilot is a trademark of Microsoft

## Related Packs

- **sentinel-graph**: Microsoft Sentinel SIEM/SOAR (Security Copilot has a Sentinel plugin)
- **azure-lighthouse**: Azure cross-tenant management
- **dotnet-expert**: .NET development

## Changelog

### Version 1.0.0 (2026-03-03)
- Initial release
- 58 URLs from Microsoft Learn Security Copilot documentation
- Coverage: overview, plugins, promptbooks, embedded experiences, administration, API
