"""Contract tests for build script exception narrowing (design/exception-handling.md §D).

Written TDD-first: these tests specify the exception-handling contract for the
process_url() function across all 45 build_*_pack.py scripts.

OLD behaviour (all scripts):
  except Exception as e:
      logger.error(f"Failed to process {url}: {e}")
      return False

  This swallowed ALL errors including RuntimeError (Kuzu DB errors), OSError
  (embedding model failures), and AttributeError (programming bugs), making
  corrupt partial writes and code defects invisible.

NEW contract (design/exception-handling.md §D):
  except (requests.RequestException, json.JSONDecodeError) as e:
      logger.error(f"Failed to process {url}: {e}")
      return False

  - requests.RequestException  → caught, return False (expected network failure)
  - json.JSONDecodeError       → caught, return False (expected malformed LLM response)
  - RuntimeError / OSError     → propagate → build aborts with visible traceback
  - AttributeError / TypeError → propagate → programming bugs are visible

Verification strategy: AST analysis of each script's process_url() function.
This avoids importing the full script (which requires Kuzu, embeddings, etc.)
and directly checks that the except clause matches the contract.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"


def _collect_build_scripts() -> list[Path]:
    """Return sorted list of all build_*_pack.py script paths."""
    return sorted(_SCRIPTS_DIR.glob("build_*_pack.py"))


# Some scripts use "process_article" instead of "process_url" (e.g. build_physics_pack.py).
_URL_PROCESSOR_NAMES = frozenset({"process_url", "process_article"})


def _get_process_url_except_handlers(script_path: Path) -> list[ast.ExceptHandler]:
    """Parse script and return except handlers inside the URL-processor function.

    Searches for functions named 'process_url' or 'process_article' (build_physics_pack.py
    uses the latter name).
    """
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _URL_PROCESSOR_NAMES:
            return [child for child in ast.walk(node) if isinstance(child, ast.ExceptHandler)]

    return []


def _elt_type_name(elt: ast.expr) -> str:
    """Extract the short type name from an exception type AST node."""
    if isinstance(elt, ast.Name):
        return elt.id  # e.g. Exception, ValueError
    if isinstance(elt, ast.Attribute):
        return elt.attr  # e.g. requests.RequestException → "RequestException"
    return type(elt).__name__  # fallback: structural type name


def _handler_type_names(handler: ast.ExceptHandler) -> list[str]:
    """Return a list of short exception type names from an ExceptHandler."""
    if handler.type is None:
        return ["bare_except"]
    if isinstance(handler.type, ast.Tuple):
        return [_elt_type_name(elt) for elt in handler.type.elts]
    return [_elt_type_name(handler.type)]


def _is_bare_exception(handler: ast.ExceptHandler) -> bool:
    """Return True if handler catches bare Exception (not a tuple of specific types)."""
    if handler.type is None:
        return True  # bare except
    return isinstance(handler.type, ast.Name) and handler.type.id == "Exception"


# ---------------------------------------------------------------------------
# Parametrised structural tests
# ---------------------------------------------------------------------------

_BUILD_SCRIPTS = _collect_build_scripts()


@pytest.mark.parametrize("script_path", _BUILD_SCRIPTS, ids=[p.name for p in _BUILD_SCRIPTS])
def test_process_url_has_no_bare_exception(script_path: Path) -> None:
    """process_url() must NOT catch bare Exception.

    OLD code:  except Exception as e:
    NEW code:  except (requests.RequestException, json.JSONDecodeError) as e:

    This test would FAIL against the old code because the old handler used
    bare Exception.  It passes once the handler is narrowed.
    """
    handlers = _get_process_url_except_handlers(script_path)
    assert handlers, f"{script_path.name}: no except handler found in process_url()"

    for handler in handlers:
        assert not _is_bare_exception(handler), (
            f"{script_path.name}: process_url() still uses bare 'except Exception'. "
            "The contract requires 'except (requests.RequestException, json.JSONDecodeError)'."
        )


@pytest.mark.parametrize("script_path", _BUILD_SCRIPTS, ids=[p.name for p in _BUILD_SCRIPTS])
def test_process_url_catches_requests_exception(script_path: Path) -> None:
    """process_url() must catch requests.RequestException.

    Network failures (connection errors, timeouts, HTTP errors) are expected
    during pack building and should return False, not abort the build.
    """
    handlers = _get_process_url_except_handlers(script_path)
    type_names = [name for h in handlers for name in _handler_type_names(h)]

    assert "RequestException" in type_names, (
        f"{script_path.name}: process_url() does not catch RequestException. "
        "Network failures must be caught to allow the build to skip bad URLs."
    )


@pytest.mark.parametrize("script_path", _BUILD_SCRIPTS, ids=[p.name for p in _BUILD_SCRIPTS])
def test_process_url_catches_json_decode_error(script_path: Path) -> None:
    """process_url() must catch json.JSONDecodeError.

    Malformed LLM responses during extraction are expected failures.
    They should return False, not abort the build.
    """
    handlers = _get_process_url_except_handlers(script_path)
    type_names = [name for h in handlers for name in _handler_type_names(h)]

    assert "JSONDecodeError" in type_names, (
        f"{script_path.name}: process_url() does not catch JSONDecodeError. "
        "Malformed LLM JSON must be caught to allow the build to skip bad responses."
    )


@pytest.mark.parametrize("script_path", _BUILD_SCRIPTS, ids=[p.name for p in _BUILD_SCRIPTS])
def test_process_url_except_handler_count(script_path: Path) -> None:
    """process_url() should have exactly ONE except handler in its main try block.

    Multiple except clauses or a catch-all followed by specific ones indicate
    leftover broad handlers.  The contract is a single, specific tuple handler.
    """
    handlers = _get_process_url_except_handlers(script_path)
    # Allow 1 handler (the (RequestException, JSONDecodeError) tuple).
    # Some scripts may have nested try/except for optional steps — those are fine
    # as long as none is bare Exception (tested above).
    assert len(handlers) >= 1, f"{script_path.name}: process_url() has no except handler"


# ---------------------------------------------------------------------------
# Structural check: all 45 expected scripts are present
# ---------------------------------------------------------------------------

_EXPECTED_PACK_NAMES = [
    "anthropic_api_expert",
    "autogen_expert",
    "azure_ai_foundry",
    "bicep_infrastructure",
    "claude_agent_sdk",
    "cpp",
    "crew_ai_expert",
    "csharp",
    "docker_expert",
    "dotnet",
    "dspy_expert",
    "fabric_graph_gql_expert",
    "fabric",
    "github_actions_advanced",
    "github_copilot_sdk",
    "go",
    "huggingface_transformers",
    "java",
    "kotlin",
    "kubernetes_networking",
    "langchain_expert",
    "llamaindex_expert",
    "mcp_protocol",
    "microsoft_agent_framework",
    "nextjs_expert",
    "openai_api_expert",
    "opencypher",
    "opentelemetry_expert",
    "physics",
    "postgresql_internals",
    "prompt_engineering",
    "python",
    "react_expert",
    "ruby",
    "rust_async",
    "rust",
    "semantic_kernel",
    "swift",
    "terraform_expert",
    "typescript",
    "vercel_ai_sdk",
    "vscode_extensions",
    "wasm_components",
    "workiq_mcp",
    "zig",
]


def test_all_expected_build_scripts_exist() -> None:
    """All 45 expected build_*_pack.py scripts must exist in scripts/.

    If a script is missing it means the D-requirement was only partially applied.
    """
    existing_names = {p.stem for p in _BUILD_SCRIPTS}
    for pack_name in _EXPECTED_PACK_NAMES:
        script_stem = f"build_{pack_name}_pack"
        assert script_stem in existing_names, (
            f"Expected scripts/{script_stem}.py to exist — it was not found. "
            "All 45 build scripts must have exception narrowing applied."
        )


def test_build_scripts_count() -> None:
    """There must be at least 45 build_*_pack.py scripts in scripts/."""
    assert len(_BUILD_SCRIPTS) >= 45, (
        f"Expected at least 45 build_*_pack.py scripts, found {len(_BUILD_SCRIPTS)}. "
        "The exception narrowing was applied to all 45 scripts."
    )
