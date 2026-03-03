"""TDD tests for the 4 new pack build scripts.

Packs under test:
  - build_azure_lighthouse_pack.py      (domain="azure_lighthouse")
  - build_fabric_graphql_expert_pack.py (domain="fabric_graphql")
  - build_security_copilot_pack.py      (domain="security_copilot")
  - build_sentinel_graph_pack.py        (domain="microsoft_sentinel")

Written TDD-first: tests specify EXPECTED behaviour.

Test failure matrix
-------------------
ALL tests in this file PASS (implementation is complete including SEC-01 and SEC-06).

Pack-level tests that require a build to be run (pack.db, manifest.json) are in:
  tests/packs/test_new_pack_files.py

Design references:
  - design/exception-handling.md §D  (exception narrowing)
  - security_considerations SEC-01   (https-only URL filter — APPLIED)
  - security_considerations SEC-06   (DB_PATH guard before shutil.rmtree — APPLIED)
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"

_NEW_PACKS: dict[str, dict] = {
    "build_azure_lighthouse_pack.py": {
        "pack_dir": "data/packs/azure-lighthouse",
        "domain": "azure_lighthouse",
        "manifest_name": "azure-lighthouse",
        "category": "Azure Lighthouse",
        "log_file": "logs/build_azure_lighthouse_pack.log",
    },
    "build_fabric_graphql_expert_pack.py": {
        "pack_dir": "data/packs/fabric-graphql-expert",
        "domain": "fabric_graphql",
        "manifest_name": "fabric-graphql-expert",
        "category": "Microsoft Fabric GraphQL",
        "log_file": "logs/build_fabric_graphql_expert_pack.log",
    },
    "build_security_copilot_pack.py": {
        "pack_dir": "data/packs/security-copilot",
        "domain": "security_copilot",
        "manifest_name": "security-copilot",
        "category": "Microsoft Security Copilot",
        "log_file": "logs/build_security_copilot_pack.log",
    },
    "build_sentinel_graph_pack.py": {
        "pack_dir": "data/packs/sentinel-graph",
        "domain": "microsoft_sentinel",
        "manifest_name": "sentinel-graph",
        "category": "Microsoft Sentinel",
        "log_file": "logs/build_sentinel_graph_pack.log",
    },
}

_NEW_SCRIPT_PATHS = [(name, _SCRIPTS_DIR / name) for name in _NEW_PACKS]

# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


@cache
def _read_source(script_path: Path) -> str:
    """Return source text for a script (cached — each script is read once)."""
    return script_path.read_text(encoding="utf-8")


@cache
def _parse(script_path: Path) -> ast.Module:
    """Return the AST for a script, raising SyntaxError on invalid code."""
    return ast.parse(_read_source(script_path), filename=str(script_path))


def _get_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    """Return the top-level function definition with the given name."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _find_string_constants(tree: ast.AST) -> list[str]:
    """Return all string literal values in the subtree."""
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _find_startswith_call_args(func_node: ast.FunctionDef) -> list[str]:
    """Return string arguments of all .startswith() calls inside a function."""
    args: list[str] = []
    for node in ast.walk(func_node):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "startswith"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            args.append(node.args[0].value)
    return args


def _find_http_filter_strings(func_node: ast.FunctionDef) -> list[str]:
    """Return .startswith() arguments that look like URL scheme filters."""
    return [s for s in _find_startswith_call_args(func_node) if s.startswith("http")]


def _has_assert_with_text(tree: ast.AST, text: str) -> bool:
    """Return True if any Assert node's test contains the given text as a literal."""
    source_fragment = ast.unparse(tree)
    # Look for the pattern in the unparsed source, accounting for minor formatting
    return text in source_fragment


def _get_except_handler_type_names(handler: ast.ExceptHandler) -> list[str]:
    """Return short exception type names from an ExceptHandler."""
    if handler.type is None:
        return ["bare_except"]
    if isinstance(handler.type, ast.Tuple):
        names = []
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name):
                names.append(elt.id)
            elif isinstance(elt, ast.Attribute):
                names.append(elt.attr)
        return names
    if isinstance(handler.type, ast.Name):
        return [handler.type.id]
    if isinstance(handler.type, ast.Attribute):
        return [handler.type.attr]
    return []


def _is_bare_exception(handler: ast.ExceptHandler) -> bool:
    """Return True if handler catches bare Exception."""
    if handler.type is None:
        return True
    return isinstance(handler.type, ast.Name) and handler.type.id == "Exception"


# ---------------------------------------------------------------------------
# Parametrised fixtures
# ---------------------------------------------------------------------------

_URL_PROCESSOR_NAMES = frozenset({"process_url", "process_article"})


@pytest.fixture(params=_NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def script_and_spec(request):
    """Yield (script_name, script_path, spec_dict) for each new script."""
    name, path = request.param
    return name, path, _NEW_PACKS[name]


# ---------------------------------------------------------------------------
# Structural existence tests  (PASS initially)
# ---------------------------------------------------------------------------


def test_all_four_new_scripts_exist() -> None:
    """All 4 new build scripts must exist in scripts/.

    This documents the expected inventory after step 5-8 of the implementation
    plan are complete.  PASSES immediately since scripts were already created.
    """
    for script_name in _NEW_PACKS:
        script_path = _SCRIPTS_DIR / script_name
        assert (
            script_path.exists()
        ), f"scripts/{script_name} is missing. Expected all 4 new pack scripts to exist."
        assert script_path.is_file(), f"scripts/{script_name} is not a regular file."


# ---------------------------------------------------------------------------
# Syntax tests  (PASS initially)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_script_syntax_valid(name: str, path: Path) -> None:
    """Each new script must be syntactically valid Python.

    ast.parse() raises SyntaxError on malformed scripts.
    """
    try:
        _parse(path)
    except SyntaxError as exc:
        pytest.fail(f"{name}: SyntaxError — {exc}")


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_shebang_line(name: str, path: Path) -> None:
    """Each script must begin with the standard Python shebang."""
    first_line = _read_source(path).splitlines()[0]
    assert (
        first_line == "#!/usr/bin/env python3"
    ), f"{name}: missing or wrong shebang. Expected '#!/usr/bin/env python3', got {first_line!r}"


# ---------------------------------------------------------------------------
# Constants tests  (PASS initially)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_pack_dir_constant(name: str, path: Path) -> None:
    """PACK_DIR must point to the correct pack directory for each script."""
    expected = _NEW_PACKS[name]["pack_dir"]
    tree = _parse(path)
    strings = _find_string_constants(tree)
    assert expected in strings, (
        f"{name}: expected PACK_DIR to reference '{expected}' but it was not found "
        f"as a string constant. Check the PACK_DIR = Path(...) assignment."
    )


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_db_path_constant(name: str, path: Path) -> None:
    """DB_PATH must be derived from PACK_DIR and named 'pack.db'."""
    source = _read_source(path)
    assert (
        "pack.db" in source
    ), f"{name}: 'pack.db' not found in source. DB_PATH must be set to PACK_DIR / 'pack.db'."


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_manifest_path_constant(name: str, path: Path) -> None:
    """MANIFEST_PATH must be set to PACK_DIR / 'manifest.json'."""
    source = _read_source(path)
    assert "manifest.json" in source, (
        f"{name}: 'manifest.json' not found in source. "
        "MANIFEST_PATH must be set to PACK_DIR / 'manifest.json'."
    )


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_log_file_name_matches_script(name: str, path: Path) -> None:
    """The FileHandler log path must match the script name pattern.

    Convention: build_FOO_pack.py → logs/build_FOO_pack.log
    """
    expected_log = _NEW_PACKS[name]["log_file"]
    source = _read_source(path)
    assert expected_log in source, (
        f"{name}: expected log file path '{expected_log}' not found in source. "
        "The FileHandler log path must match the script name."
    )


# ---------------------------------------------------------------------------
# Required functions  (PASS initially)
# ---------------------------------------------------------------------------


_REQUIRED_FUNCTIONS = ["process_url", "create_manifest", "build_pack", "main"]


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
@pytest.mark.parametrize("func_name", _REQUIRED_FUNCTIONS)
def test_required_functions_exist(name: str, path: Path, func_name: str) -> None:
    """Each script must define the required functions matching build_go_pack.py contract."""
    tree = _parse(path)
    function_names = {
        node.name for node in ast.iter_child_nodes(tree) if isinstance(node, ast.FunctionDef)
    }
    assert func_name in function_names, (
        f"{name}: required function '{func_name}' not found. "
        "All 4 new scripts must follow the build_go_pack.py function contract."
    )


# ---------------------------------------------------------------------------
# Domain string tests  (PASS initially)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_domain_string_in_extractor_call(name: str, path: Path) -> None:
    """The domain= argument passed to extract_from_article() must match the pack spec.

    Each pack must pass its correct domain string so the LLM extractor
    targets the right knowledge domain.
    """
    expected_domain = _NEW_PACKS[name]["domain"]
    source = _read_source(path)
    # Look for domain="<value>" or domain='<value>' assignment
    pattern = re.compile(r'domain\s*=\s*["\']([^"\']+)["\']')
    matches = pattern.findall(source)
    assert expected_domain in matches, (
        f"{name}: domain string '{expected_domain}' not found in extractor call. "
        f"Found domain values: {matches}. "
        "The domain= argument to extract_from_article() must be set correctly."
    )


# ---------------------------------------------------------------------------
# Manifest content tests  (PASS initially)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_manifest_pack_name(name: str, path: Path) -> None:
    """The manifest 'name' key must match the pack directory name."""
    expected_name = _NEW_PACKS[name]["manifest_name"]
    source = _read_source(path)
    # The name appears in the manifest dict literal as "name": "pack-name"
    assert f'"name": "{expected_name}"' in source or f"'name': '{expected_name}'" in source, (
        f"{name}: manifest name '{expected_name}' not found in create_manifest(). "
        "The 'name' key in the manifest dict must match the pack directory name."
    )


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_manifest_category(name: str, path: Path) -> None:
    """The 'category' passed to Article creation must match the pack spec."""
    expected_category = _NEW_PACKS[name]["category"]
    source = _read_source(path)
    assert expected_category in source, (
        f"{name}: category '{expected_category}' not found in source. "
        "The category string is used in the Cypher CREATE statement for Article nodes."
    )


# ---------------------------------------------------------------------------
# Exception narrowing tests  (PASS initially — already implemented)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_exception_narrowing_no_bare_except(name: str, path: Path) -> None:
    """process_url() must NOT catch bare Exception.

    OLD: except Exception as e:   # swallowed all errors
    NEW: except (requests.RequestException, json.JSONDecodeError) as e:
    """
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _URL_PROCESSOR_NAMES:
            handlers = [c for c in ast.walk(node) if isinstance(c, ast.ExceptHandler)]
            assert handlers, f"{name}: no except handler found in process_url()"
            for handler in handlers:
                assert not _is_bare_exception(handler), (
                    f"{name}: process_url() uses bare 'except Exception'. "
                    "Contract requires 'except (requests.RequestException, json.JSONDecodeError)'."
                )
            return
    pytest.fail(f"{name}: process_url() function not found")


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_exception_catches_requests_exception(name: str, path: Path) -> None:
    """process_url() must catch requests.RequestException for network failures."""
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _URL_PROCESSOR_NAMES:
            handlers = [c for c in ast.walk(node) if isinstance(c, ast.ExceptHandler)]
            type_names = [name_s for h in handlers for name_s in _get_except_handler_type_names(h)]
            assert "RequestException" in type_names, (
                f"{name}: process_url() does not catch RequestException. "
                "Network failures must be caught to skip bad URLs without aborting the build."
            )
            return
    pytest.fail(f"{name}: process_url() function not found")


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_exception_catches_json_decode_error(name: str, path: Path) -> None:
    """process_url() must catch json.JSONDecodeError for malformed LLM responses."""
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _URL_PROCESSOR_NAMES:
            handlers = [c for c in ast.walk(node) if isinstance(c, ast.ExceptHandler)]
            type_names = [name_s for h in handlers for name_s in _get_except_handler_type_names(h)]
            assert "JSONDecodeError" in type_names, (
                f"{name}: process_url() does not catch JSONDecodeError. "
                "Malformed LLM JSON must be caught to skip bad responses."
            )
            return
    pytest.fail(f"{name}: process_url() function not found")


# ---------------------------------------------------------------------------
# build_pack() structure tests  (PASS initially)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_test_mode_limit_is_five(name: str, path: Path) -> None:
    """build_pack() must set limit=5 in test_mode to cap processing at 5 URLs."""
    source = _read_source(path)
    # Pattern: limit = 5 if test_mode else None
    assert "5 if test_mode" in source or "limit=5" in source, (
        f"{name}: test_mode URL limit of 5 not found. "
        "build_pack() must limit to 5 URLs in test_mode per the --test-mode contract."
    )


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_build_pack_has_test_mode_parameter(name: str, path: Path) -> None:
    """build_pack() must accept a test_mode: bool = False parameter."""
    tree = _parse(path)
    func = _get_function(tree, "build_pack")
    assert func is not None, f"{name}: build_pack() function not found"
    arg_names = [arg.arg for arg in func.args.args]
    assert "test_mode" in arg_names, (
        f"{name}: build_pack() does not have 'test_mode' parameter. "
        "All build scripts must support --test-mode for quick verification."
    )


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_main_creates_logs_directory(name: str, path: Path) -> None:
    """main() must create the logs/ directory before FileHandler is activated."""
    source = _read_source(path)
    # The main() function should call Path("logs").mkdir(exist_ok=True)
    assert 'Path("logs").mkdir(exist_ok=True)' in source, (
        f"{name}: main() does not create logs/ directory. "
        "main() must call Path('logs').mkdir(exist_ok=True) before starting the build."
    )


# ---------------------------------------------------------------------------
# SEC-01: HTTPS-only filter  (applied — all 4 scripts use startswith("https://"))
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_load_urls_filter_is_https_only(name: str, path: Path) -> None:
    """load_urls() must filter URLs with startswith("https://") not startswith("http").

    SEC-01 [MANDATORY, APPLIED]:
    All 4 scripts use: line.strip().startswith("https://") <- HTTPS-only enforcement

    Security rationale: If urls.txt is ever edited to include http:// URLs
    (e.g. from copy-paste errors), the current filter silently accepts them.
    The WebContentSource SSRF guard enforces HTTPS at fetch time, but defense
    in depth requires the filter to also enforce it.
    """
    tree = _parse(path)
    load_urls_func = _get_function(tree, "load_urls")
    if load_urls_func is None:
        # load_urls is imported from wikigr.packs.utils — filter check delegated to utils tests
        pytest.skip(f"{name}: load_urls() is imported, not locally defined — skipping filter check")

    http_filters = _find_http_filter_strings(load_urls_func)
    assert http_filters, (
        f'{name}: no startswith("http...") filter found in load_urls(). '
        'The URL filter must use startswith("https://").'
    )

    for filter_str in http_filters:
        assert filter_str == "https://", (
            f"{name}: load_urls() uses startswith({filter_str!r}) which allows plain HTTP URLs. "
            "SEC-01 requires changing this to startswith('https://') to enforce HTTPS-only. "
            "This test will PASS once SEC-01 is applied."
        )


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_load_urls_rejects_http_url_in_urls_txt(name: str, path: Path) -> None:
    """load_urls() behavior contract: an http:// URL must be excluded from results.

    This is a behavioral specification test. It checks the source filter string
    rather than executing the function (which requires kuzu/embeddings imports).

    If the script imports load_urls from wikigr.packs.utils, the filter is
    defined there — skip this check (covered by test_load_urls_utils.py).
    """
    source = _read_source(path)
    if "from wikigr.packs.utils import load_urls" in source:
        pytest.skip(
            f"{name}: load_urls() is imported from wikigr.packs.utils — filter check delegated to utils tests"
        )
    # The filter must use "https://" not just "http"
    # Check via regex: find startswith("http...") in a comprehension context
    pattern = re.compile(r'startswith\(["\']https://["\']\)')
    matches = pattern.findall(source)
    assert matches, (
        f'{name}: load_urls() does not contain startswith("https://"). '
        "An http:// URL in urls.txt would be incorrectly accepted by the current filter. "
        'SEC-01: change startswith("http") → startswith("https://").'
    )


# ---------------------------------------------------------------------------
# SEC-06: DB_PATH safety guard (ValueError) before shutil.rmtree  (applied — all 4 scripts)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_build_pack_has_db_path_safety_guard(name: str, path: Path) -> None:
    """build_pack() must guard DB_PATH is inside data/packs/ before shutil.rmtree.

    SEC-06 [MANDATORY]:
    Scripts must use a path-safe guard before shutil.rmtree.  Acceptable forms:

        # Preferred (H-01 fix): resolve() handles symlinks and path traversal
        if not DB_PATH.resolve().is_relative_to(Path("data/packs").resolve()):
            raise ValueError(...)

        # Legacy (still acceptable for hardcoded DB_PATH):
        if not str(DB_PATH).startswith("data/packs/"):
            raise ValueError(...)

    The guard must appear in the source before any shutil.rmtree call.
    """
    source = _read_source(path)

    # Check that shutil.rmtree is present (the guard must precede a real rmtree)
    assert "shutil.rmtree" in source, (
        f"{name}: shutil.rmtree not found. "
        "build_pack() should use shutil.rmtree to delete the existing database."
    )

    # Check for the safety guard in any acceptable form (raise ValueError, not assert)
    has_guard = (
        'str(DB_PATH).startswith("data/packs/")' in source
        or "str(DB_PATH).startswith('data/packs/')" in source
        or "DB_PATH.resolve().is_relative_to(Path(" in source
        or 'DB_PATH.resolve().is_relative_to(Path("data/packs")' in source
    )
    assert has_guard, (
        f"{name}: missing DB_PATH safety guard before shutil.rmtree. "
        "SEC-06 requires one of:\n"
        "    if not DB_PATH.resolve().is_relative_to(Path('data/packs').resolve()):\n"
        '        raise ValueError(f"Unsafe DB_PATH: {DB_PATH}")\n'
        "before every shutil.rmtree call in build_pack().\n"
        "This prevents accidental deletion of data outside data/packs/."
    )


@pytest.mark.parametrize("name,path", _NEW_SCRIPT_PATHS, ids=[n for n, _ in _NEW_SCRIPT_PATHS])
def test_db_path_assertion_precedes_rmtree_in_source(name: str, path: Path) -> None:
    """The DB_PATH safety guard must appear BEFORE the first shutil.rmtree in the source.

    Ordering matters: the guard must execute before the destructive operation.

    All 4 scripts have the guard before rmtree so this test passes.
    """
    source = _read_source(path)
    rmtree_pos = source.find("shutil.rmtree")
    if rmtree_pos == -1:
        pytest.skip(f"{name}: no shutil.rmtree found (skipping ordering check)")

    # Find the safety guard — accept resolve()-based or legacy startswith() pattern
    guard_pos = source.find("DB_PATH.resolve().is_relative_to(Path(")
    if guard_pos == -1:
        guard_pos = source.find('str(DB_PATH).startswith("data/packs/")')
    if guard_pos == -1:
        guard_pos = source.find("str(DB_PATH).startswith('data/packs/')")

    assert guard_pos != -1, (
        f"{name}: DB_PATH safety guard not found anywhere in source. "
        "SEC-06 requires the guard to exist before shutil.rmtree."
    )
    assert guard_pos < rmtree_pos, (
        f"{name}: DB_PATH safety guard (pos={guard_pos}) appears AFTER "
        f"shutil.rmtree (pos={rmtree_pos}). "
        "The guard must precede the rmtree call to provide protection."
    )


# ---------------------------------------------------------------------------
# Registration in exception narrowing test  (PASS check: new scripts counted)
# ---------------------------------------------------------------------------


def test_new_scripts_included_in_build_scripts_count() -> None:
    """The 4 new scripts must be included in the total build script count.

    The existing test_build_scripts_count asserts >= 45 scripts.
    Adding 4 new scripts should bring the count to >= 49.

    This documents the expected count after all 4 scripts are created.
    """
    all_build_scripts = sorted(_SCRIPTS_DIR.glob("build_*_pack.py"))
    count = len(all_build_scripts)
    assert count >= 49, (
        f"Expected at least 49 build_*_pack.py scripts (45 existing + 4 new), "
        f"found {count}. The 4 new scripts may not have been created yet."
    )


def test_new_pack_names_in_build_scripts() -> None:
    """Each of the 4 new pack script stems must exist in the scripts directory."""
    expected_stems = {
        "build_azure_lighthouse_pack",
        "build_fabric_graphql_expert_pack",
        "build_security_copilot_pack",
        "build_sentinel_graph_pack",
    }
    existing_stems = {p.stem for p in _SCRIPTS_DIR.glob("build_*_pack.py")}
    missing = expected_stems - existing_stems
    assert not missing, (
        f"Missing build scripts: {sorted(missing)}. "
        "All 4 new pack build scripts must exist in scripts/."
    )
