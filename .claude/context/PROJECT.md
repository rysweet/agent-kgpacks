# Project Context

**This file provides project-specific context to Claude Code agents.**

When amplihack is installed in your project, customize this file to describe YOUR project. This helps agents understand what you're building and provide better assistance.

## Quick Start

Replace the sections below with information about your project.

---

## Project: wikigr

## Overview

A semantic search and graph traversal system for Wikipedia articles using embedded graph database (Kuzu) and vector search (HNSW). - **Semantic Search**: Find articles by meaning using vector embeddings

## Architecture

### Key Components

- **bootstrap/src/wikipedia/**: Wikipedia API client with rate limiting, retry logic, and batch fetching
- **bootstrap/src/embeddings/**: Embedding generation using paraphrase-MiniLM-L3-v2 (384 dimensions)
- **bootstrap/src/database/**: Database loader integrating fetch, parse, embed, and store pipeline
- **bootstrap/src/expansion/**: Orchestrator, work queue, link discovery, and article processor for automated graph expansion
- **bootstrap/src/query/**: Semantic search and graph traversal query functions
- **worktrees/feat-visualization-pwa/backend/**: FastAPI backend for visualization PWA

### Technology Stack

- **Language**: Python 3.10+
- **Framework**: FastAPI (backend API)
- **Database**: Kuzu 0.11.3 (embedded graph database with HNSW vector index)

## Development Guidelines

### Code Organization

- `bootstrap/src/` - Core library modules (wikipedia, embeddings, database, query, expansion)
- `bootstrap/schema/` - Kuzu database schema definitions
- `bootstrap/scripts/` - Utility and optimization scripts
- `bootstrap/tests/` - Integration and validation tests
- `worktrees/feat-visualization-pwa/` - Visualization PWA with FastAPI backend

### Key Patterns

- Bricks & Studs: Self-contained modules with clear `__init__.py` exports via `__all__`
- Pipeline: Fetch -> Parse -> Embed -> Load -> Expand
- Work queue with claim/heartbeat/reclaim for distributed processing
- State machine for article expansion: discovered -> claimed -> loaded/failed

### Testing Strategy

- Unit tests per module in `bootstrap/src/*/tests/`
- Integration tests via `bootstrap/quickstart.py` (3-article end-to-end validation)
- pytest with coverage reporting (minimum 70%)

## Domain Knowledge

### Business Context

Educational project building a semantic search and graph traversal system over Wikipedia articles. Users explore knowledge connections through vector similarity and link relationships.

### Key Terminology

- **Expansion**: Automatic discovery and loading of linked articles from seeds
- **HNSW**: Hierarchical Navigable Small World index for approximate nearest neighbor vector search
- **Depth**: How many link hops from the original seed articles (0 = seed, 1 = direct link, 2 = two hops)

## Common Tasks

### Development Workflow

1. `pip install -r requirements.txt` to install dependencies
2. `python bootstrap/quickstart.py` to validate setup
3. `ruff check` and `ruff format` for linting/formatting, `pyright` for type checking
4. `pytest bootstrap/tests/` for test suite

### Deployment Process

Embedded database; no server deployment needed for core functionality. The visualization PWA backend runs via `uvicorn`.

## Important Notes

- Kuzu is an embedded database, so no external DB server is required
- Wikipedia API has rate limits; the client enforces 100ms between requests
- Embeddings use paraphrase-MiniLM-L3-v2 (384 dimensions, cosine similarity)

---

## About This File

This file is installed by amplihack to provide project-specific context to AI agents.

**For more about amplihack itself**, see PROJECT_AMPLIHACK.md in this directory.

**Tip**: Keep this file updated as your project evolves. Accurate context leads to better AI assistance.
