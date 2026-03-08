# Contributing to Agent Knowledge Packs

Thank you for your interest in contributing to agent-kgpacks! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Git

### Getting Started

```bash
# Clone the repository
git clone https://github.com/rysweet/agent-kgpacks.git
cd agent-kgpacks

# Install dependencies (including dev extras)
uv sync --extra dev --extra build --extra backend

# Install pre-commit hooks
uv run pre-commit install

# Verify setup
uv run pytest --timeout=60
```

## Code Style

- **Formatter/Linter**: [Ruff](https://docs.astral.sh/ruff/) (line length 100, Python 3.12 target)
- **Type Checker**: [Pyright](https://github.com/microsoft/pyright) (basic mode)
- **Pre-commit**: Runs ruff, pyright, and standard hooks automatically on commit

Format and lint before committing:

```bash
uv run ruff format .
uv run ruff check --fix .
uv run pyright
```

## Testing

Tests use [pytest](https://docs.pytest.org/) with coverage reporting:

```bash
# Run all tests
uv run pytest

# Run specific test directory
uv run pytest tests/agent/

# Run with verbose output
uv run pytest -v --tb=short
```

Test directories:
- `bootstrap/src/*/tests/` — Core module unit tests
- `tests/agent/` — Knowledge graph agent tests
- `tests/cli/` — CLI command tests
- `tests/packs/` — Pack structure and evaluation tests
- `tests/backend/` — FastAPI endpoint tests
- `tests/scripts/` — Build/utility script tests
- `tests/outside_in/` — End-to-end integration tests

## Building Knowledge Packs

Each pack has a build script in `scripts/`:

```bash
# Build a single pack
uv run python scripts/build_python_pack.py

# Evaluate a pack
uv run python scripts/eval_single_pack.py --pack python-expert
```

See [docs/howto/build-a-pack.md](docs/howto/build-a-pack.md) for the full guide.

## Pull Request Process

1. **Branch from `main`** using the naming convention: `feat/issue-{number}-{description}` or `fix/issue-{number}-{description}`
2. **Keep PRs focused** — one feature or fix per PR; do not mix unrelated changes
3. **Write tests** for new functionality
4. **Run the full test suite** before submitting: `uv run pytest`
5. **Ensure CI passes** — lint, type checking, tests, and schema validation all run automatically
6. **Update documentation** if your change affects user-facing behavior

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new retrieval strategy for graph queries
fix: resolve embedding dimension mismatch in pack loading
docs: update quickstart guide with MCP server setup
test: add coverage for CLI pack install command
```

## Project Structure

```
agent-kgpacks/
├── bootstrap/src/     Core modules (extraction, embeddings, query, database)
├── wikigr/            Pack management, CLI, KG agent
├── backend/           FastAPI REST API
├── frontend/          React UI
├── scripts/           Pack build and evaluation scripts
├── data/packs/        Knowledge pack databases and manifests
├── docs/              Documentation (MkDocs source)
├── tests/             Test suites
└── mcp_server.py      Model Context Protocol server
```

## Reporting Issues

- Use [GitHub Issues](https://github.com/rysweet/agent-kgpacks/issues)
- Include steps to reproduce, expected vs actual behavior, and Python/OS version
- Label appropriately: `bug`, `enhancement`, `documentation`

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
