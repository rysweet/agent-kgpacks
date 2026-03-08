.PHONY: install install-dev test lint format typecheck docs docs-serve build clean help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install core dependencies
	uv sync

install-dev: ## Install all dependencies (dev + build + backend)
	uv sync --extra dev --extra build --extra backend --extra test
	uv run pre-commit install

test: ## Run all tests with coverage
	uv run pytest

test-fast: ## Run tests without slow/integration markers
	uv run pytest -m "not slow and not integration"

test-agent: ## Run agent tests only
	uv run pytest tests/agent/

test-cli: ## Run CLI tests only
	uv run pytest tests/cli/

test-backend: ## Run backend API tests only
	uv run pytest tests/backend/

lint: ## Run ruff linter
	uv run ruff check .

format: ## Format code with ruff
	uv run ruff format .

typecheck: ## Run pyright type checker
	uv run pyright

check: lint typecheck ## Run all checks (lint + typecheck)

fix: ## Auto-fix linting issues
	uv run ruff check --fix .
	uv run ruff format .

docs: ## Build documentation site
	uv run mkdocs build

docs-serve: ## Serve documentation locally
	uv run mkdocs serve

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

build-pack: ## Build a pack (usage: make build-pack PACK=python-expert)
	uv run python scripts/build_$(subst -,_,$(PACK))_pack.py

eval-pack: ## Evaluate a pack (usage: make eval-pack PACK=python-expert)
	uv run python scripts/eval_single_pack.py --pack $(PACK)

catalog: ## Generate pack catalog
	uv run python scripts/generate_catalog.py

mcp: ## Start MCP server
	uv run python mcp_server.py

clean: ## Remove build artifacts and caches
	rm -rf site/ dist/ build/ *.egg-info
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	rm -f .coverage
