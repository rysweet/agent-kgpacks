# Azure Security and Management Packs

Documentation for the four knowledge packs covering Azure management and Microsoft security products:

- [azure-lighthouse](#azure-lighthouse) — Delegated resource management and MSSP scenarios
- [fabric-graphql-expert](#fabric-graphql-expert) — Microsoft Fabric GraphQL API and data integration
- [security-copilot](#security-copilot) — Microsoft Security Copilot usage and integration
- [sentinel-graph](#sentinel-graph) — Microsoft Sentinel queries, workbooks, and threat detection

---

## azure-lighthouse

**Pack name:** `azure-lighthouse`
**Build script:** `scripts/build_azure_lighthouse_pack.py`
**Pack directory:** `data/packs/azure-lighthouse/`
**Domain identifier:** `azure_lighthouse`

### What It Covers

Expert knowledge of Azure Lighthouse: the Azure service that enables cross-tenant, delegated management of Azure resources at scale.

| Topic | Coverage |
|-------|----------|
| Delegated resource management | Lighthouse architecture, ARM delegate assignments, scope limits |
| Cross-tenant management | Multi-tenant identity, scope inheritance, PIM integration |
| Managed Services offers | Azure Marketplace publishing, offer lifecycle |
| Policy at scale | Azure Policy initiatives deployed across delegated scopes |
| Monitoring and alerting | Azure Monitor, Activity Log, Defender for Cloud integration |
| MSSP scenarios | Managed Security Service Provider deployment patterns |
| Security best practices | Principle of least privilege, JIT access, Defender integration |

### Running the Build

```bash
# Full build (~50+ URLs, 3-5 hours, ~$10-15 at Haiku rates)
echo "y" | uv run python scripts/build_azure_lighthouse_pack.py

# Test build (5 URLs, ~5-10 minutes)
uv run python scripts/build_azure_lighthouse_pack.py --test-mode
```

### Pack Stats (Reference Build)

| Metric | Value |
|--------|-------|
| Articles | ~50 |
| Entities | ~600 |
| Entity relationships | ~350 |
| Database size | ~2 MB |

Actual stats vary with URL list changes. Consult `data/packs/azure-lighthouse/manifest.json` for the most recent build.

### Source URLs

Primary sources from `data/packs/azure-lighthouse/urls.txt`:

- `https://learn.microsoft.com/en-us/azure/lighthouse/` — Official Azure Lighthouse documentation
- `https://learn.microsoft.com/en-us/azure/lighthouse/concepts/` — Architecture and concepts
- `https://learn.microsoft.com/en-us/azure/lighthouse/how-to/` — Operational guides

---

## fabric-graphql-expert

**Pack name:** `fabric-graphql-expert`
**Build script:** `scripts/build_fabric_graphql_expert_pack.py`
**Pack directory:** `data/packs/fabric-graphql-expert/`
**Domain identifier:** `fabric_graphql`

### What It Covers

Expert knowledge of Microsoft Fabric's GraphQL API layer, which exposes Fabric data items (Lakehouses, Warehouses, KQL databases) as queryable GraphQL endpoints.

| Topic | Coverage |
|-------|----------|
| GraphQL API basics | Schema design, queries, mutations, subscriptions in Fabric |
| Data item exposure | Connecting Lakehouse, Warehouse, and KQL databases |
| Authentication | Entra ID (AAD) OAuth 2.0 flows for API access |
| Schema introspection | Discovering types, fields, and relationships via `__schema` |
| Pagination | Cursor-based pagination patterns for large datasets |
| Performance | Query complexity limits, batching, caching strategies |
| Client SDKs | Python, TypeScript, and Power BI integration |

### Running the Build

```bash
# Full build
echo "y" | uv run python scripts/build_fabric_graphql_expert_pack.py

# Test build
uv run python scripts/build_fabric_graphql_expert_pack.py --test-mode
```

### Source URLs

Primary sources from `data/packs/fabric-graphql-expert/urls.txt`:

- `https://learn.microsoft.com/en-us/fabric/data-engineering/api-graphql-overview` — Official GraphQL API overview
- `https://learn.microsoft.com/en-us/fabric/data-engineering/get-started-api-graphql` — Getting started guide

---

## security-copilot

**Pack name:** `security-copilot`
**Build script:** `scripts/build_security_copilot_pack.py`
**Pack directory:** `data/packs/security-copilot/`
**Domain identifier:** `security_copilot`

### What It Covers

Expert knowledge of Microsoft Security Copilot: the AI-powered security product that enables analysts to investigate incidents, summarise threats, and generate remediation guidance using natural language.

| Topic | Coverage |
|-------|----------|
| Promptbooks | Building, sharing, and running reusable prompt sequences |
| Plugin integration | Connecting Security Copilot to Defender, Sentinel, Intune, Entra |
| Standalone vs embedded | Session types, embedding in Defender XDR and Intune portals |
| Capacity management | Provisioning SCUs, cost controls, usage monitoring |
| API access | REST API for programmatic interaction with Security Copilot |
| RBAC | Owner, Contributor, and Reader role assignments |
| Responsible AI | Audit logging, data handling, opt-out controls |

### Running the Build

```bash
# Full build
echo "y" | uv run python scripts/build_security_copilot_pack.py

# Test build
uv run python scripts/build_security_copilot_pack.py --test-mode
```

### Source URLs

Primary sources from `data/packs/security-copilot/urls.txt`:

- `https://learn.microsoft.com/en-us/copilot/security/` — Official Microsoft Security Copilot documentation
- `https://learn.microsoft.com/en-us/copilot/security/get-started-security-copilot` — Getting started

---

## sentinel-graph

**Pack name:** `sentinel-graph`
**Build script:** `scripts/build_sentinel_graph_pack.py`
**Pack directory:** `data/packs/sentinel-graph/`
**Domain identifier:** `microsoft_sentinel`

### What It Covers

Expert knowledge of Microsoft Sentinel: the cloud-native SIEM and SOAR platform for threat detection, investigation, and response.

| Topic | Coverage |
|-------|----------|
| KQL queries | Sentinel-specific KQL patterns for log analysis and hunting |
| Analytic rules | Scheduled, NRT, Fusion, ML, and Anomaly rule types |
| Workbooks | Building interactive dashboards and investigation views |
| Playbooks | Logic Apps-based SOAR automation for incident response |
| Data connectors | Microsoft, partner, and CEF/Syslog connector configuration |
| UEBA | User and Entity Behaviour Analytics, anomaly scores |
| Threat intelligence | TI feeds, indicators, and watchlists |
| Incident management | Triage, assignment, evidence, and closure workflows |
| MITRE ATT&CK | Mapping detection coverage to MITRE techniques |

### Running the Build

```bash
# Full build
echo "y" | uv run python scripts/build_sentinel_graph_pack.py

# Test build
uv run python scripts/build_sentinel_graph_pack.py --test-mode
```

### Source URLs

Primary sources from `data/packs/sentinel-graph/urls.txt`:

- `https://learn.microsoft.com/en-us/azure/sentinel/` — Official Microsoft Sentinel documentation
- `https://learn.microsoft.com/en-us/azure/sentinel/detect-threats-built-in` — Built-in threat detection

---

## Shared Build Script Contract

All four build scripts follow the same structure and must satisfy the same requirements. These are enforced by the test suite in `tests/scripts/test_new_pack_build_scripts.py`.

### Required Functions

| Function | Purpose |
|----------|---------|
| `process_url(url, conn, web_source, embedder, extractor)` | Fetch one URL, extract entities/relationships/facts, store in graph |
| `create_manifest(db_path, manifest_path, articles, entities, relationships)` | Write `manifest.json` with graph stats and metadata |
| `build_pack(test_mode=False)` | Orchestrate the full build: load URLs, init DB, loop over URLs, write manifest |
| `main()` | Parse CLI args, call `build_pack()`, handle `KeyboardInterrupt` |

### Exception Contract for `process_url()`

`process_url()` catches only two specific exception types — network and JSON parse failures. All other exceptions propagate and abort the build:

```python
except (requests.RequestException, json.JSONDecodeError) as e:
    logger.error(f"Failed to process {url}: {e}")
    return False
```

This is intentional: Kuzu errors, embedding failures, and programming bugs terminate the build with a full traceback, preventing silent partial writes.

### DB_PATH Safety Guard

Before calling `shutil.rmtree()`, each script validates that `DB_PATH` points inside `data/packs/`:

```python
if not str(DB_PATH).startswith("data/packs/"):
    raise ValueError(f"Unsafe DB_PATH: {DB_PATH}")
```

This guard prevents accidental broad deletion if `DB_PATH` is ever misconfigured or set to a path outside the expected pack directory tree.

### URL Loading

All four scripts import `load_urls` from `wikigr.packs.utils`:

```python
from wikigr.packs.utils import load_urls  # noqa: E402

urls = load_urls(URLS_FILE, limit=limit)  # limit=5 in test mode
```

`load_urls` enforces HTTPS-only at parse time — any `http://` line in `urls.txt` is silently dropped before reaching the HTTP client.

---

## Log Files

Each build script writes to a dedicated log file in `logs/`:

| Script | Log File |
|--------|---------|
| `build_azure_lighthouse_pack.py` | `logs/build_azure_lighthouse_pack.log` |
| `build_fabric_graphql_expert_pack.py` | `logs/build_fabric_graphql_expert_pack.log` |
| `build_security_copilot_pack.py` | `logs/build_security_copilot_pack.log` |
| `build_sentinel_graph_pack.py` | `logs/build_sentinel_graph_pack.log` |

The `logs/` directory is created automatically by each script before the `FileHandler` is attached. All log files include timestamps and are safe to `tail -f` during a running build.

---

## Manifest Format

After a successful build, each pack contains a `manifest.json`:

```json
{
  "name": "azure-lighthouse",
  "version": "1.0.0",
  "description": "Expert knowledge of Azure Lighthouse covering ...",
  "graph_stats": {
    "articles": 50,
    "entities": 600,
    "relationships": 350,
    "size_mb": 4.21
  },
  "eval_scores": null,
  "source_urls": [
    "https://learn.microsoft.com/en-us/azure/lighthouse/overview",
    "..."
  ],
  "created": "2026-03-03T08:14:42.279543Z",
  "license": "MIT"
}
```

`eval_scores` is `null` until the evaluation suite is run against the pack. See [Run Evaluations](../howto/run-evaluations.md) for instructions.

---

## Related Documentation

- [How to Build a Pack](../howto/build-a-pack.md) — End-to-end build guide with DB_PATH guard and exception requirements
- [Pack Utilities API Reference](../reference/pack-utils.md) — `load_urls` function documentation
- [urls.txt Format and Conventions](../reference/urls-txt-format.md) — URL file format rules
- [Handle Exceptions from WikiGR Components](../howto/handle-exceptions.md) — Exception contract for `process_url()`
- [Pack Manifest Reference](../reference/pack-manifest.md) — Full manifest schema documentation
- [Run Evaluations](../howto/run-evaluations.md) — Evaluating pack quality with the eval suite
