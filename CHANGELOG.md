# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MCP server for GitHub Copilot and Claude Desktop integration (`mcp_server.py`)
- Pack catalog generation script (`scripts/generate_catalog.py`)
- Pack publishing script (`scripts/publish_packs.py`)
- One-liner installation script (`scripts/install.sh`)
- `CONTRIBUTING.md` with development guidelines
- `LICENSE` file (MIT)
- `CHANGELOG.md`
- `.editorconfig` for consistent formatting
- `Makefile` for common development tasks

### Changed
- UX overhaul for pack management workflows (#298)
- Improved backend chat API with streaming enhancements
- Registry API improvements for pack discovery

## [0.3.0] - 2026-03-01

### Added
- 49 knowledge packs covering languages, frameworks, AI/ML, infrastructure, and Azure services
- Cross-encoder reranking for improved retrieval accuracy
- BFS link expansion for comprehensive graph coverage
- Pack freshness checking workflow (`pack-freshness.yml`)
- Repo hygiene CI workflow (`repo-hygiene.yml`)
- 128+ unit tests with pytest coverage reporting
- Pre-commit hooks (ruff, pyright, custom validators)

### Changed
- Retrieval pipeline accuracy improved from 91.7% to 99%
- Evaluation framework with baseline vs pack comparison

## [0.2.0] - 2026-02-20

### Added
- FastAPI backend with hybrid search API
- React frontend for pack management
- CLI tool (`wikigr`) for pack building and querying
- Evaluation framework with per-pack scoring
- Documentation site (MkDocs Material theme)

### Changed
- Migrated to LadybugDB for graph storage
- BGE embeddings for vector search

## [0.1.1] - 2026-02-10

### Added
- Initial knowledge graph extraction pipeline
- Wikipedia content source integration
- Basic entity/relationship extraction via Claude Haiku
- Sentence-transformer embeddings
- Core bootstrap modules (extraction, embeddings, database, query)

[Unreleased]: https://github.com/rysweet/agent-kgpacks/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/rysweet/agent-kgpacks/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/rysweet/agent-kgpacks/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/rysweet/agent-kgpacks/releases/tag/v0.1.1
