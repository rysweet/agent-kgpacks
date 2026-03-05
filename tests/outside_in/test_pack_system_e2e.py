"""Outside-in end-to-end tests for the knowledge pack system.

Tests the complete user-facing workflows from the outside:
1. Pack building (test mode)
2. Extension loading (LadybugDB)
3. KG Agent queries
4. Skill installation
5. Eval harness
6. Rebuild script
7. /kg-pack skill structure

These tests invoke CLI scripts as subprocesses and verify:
- Exit codes
- Output content
- File creation
- Data integrity
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
PACKS_DIR = PROJECT_ROOT / "data" / "packs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


def run_script(args: list[str], timeout: int = 120, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a script and return the result."""
    full_env = {**os.environ, "TOKENIZERS_PARALLELISM": "false", "LOKY_MAX_CPU_COUNT": "1"}
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
        env=full_env,
    )


# ============================================================================
# 1. LadybugDB import and extension loading
# ============================================================================


class TestLadybugDBIntegration:
    """Verify LadybugDB replaces Kuzu correctly."""

    def test_real_ladybug_importable(self):
        """The real_ladybug package should be installed and importable."""
        result = run_script(["-c", "import real_ladybug; print(real_ladybug.version)"])
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "0.15" in result.stdout, f"Unexpected version: {result.stdout}"

    def test_kuzu_alias_works(self):
        """import real_ladybug as kuzu should work and provide Database/Connection."""
        result = run_script([
            "-c",
            "import real_ladybug as kuzu; "
            "db = kuzu.Database(); conn = kuzu.Connection(db); "
            "print('OK')",
        ])
        assert result.returncode == 0, f"Alias failed: {result.stderr}"
        assert "OK" in result.stdout

    def test_extension_loading(self):
        """VECTOR and FTS extensions should load on a fresh connection."""
        result = run_script([
            "-c",
            "import real_ladybug as kuzu; "
            "db = kuzu.Database(); conn = kuzu.Connection(db); "
            "conn.execute('INSTALL VECTOR; LOAD EXTENSION VECTOR;'); "
            "conn.execute('INSTALL FTS; LOAD EXTENSION FTS;'); "
            "print('EXTENSIONS_OK')",
        ])
        assert result.returncode == 0, f"Extension loading failed: {result.stderr}"
        assert "EXTENSIONS_OK" in result.stdout

    def test_load_extensions_helper(self):
        """The load_extensions() helper from schema module should work."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from bootstrap.schema.ryugraph_schema import load_extensions; "
            "import real_ladybug as kuzu; "
            "db = kuzu.Database(); conn = kuzu.Connection(db); "
            "load_extensions(conn); print('HELPER_OK')",
        ])
        assert result.returncode == 0, f"Helper failed: {result.stderr}"
        assert "HELPER_OK" in result.stdout


# ============================================================================
# 2. Pack build (test mode)
# ============================================================================


class TestPackBuild:
    """Verify pack building works in test mode."""

    @pytest.fixture(autouse=True)
    def setup_test_pack(self, tmp_path):
        """Create a temporary pack directory for testing."""
        self.test_pack_dir = tmp_path / "test-pack"
        self.test_pack_dir.mkdir()
        yield
        # Cleanup handled by tmp_path

    def test_ladybugdb_pack_build_test_mode(self):
        """Build ladybugdb-expert pack in test mode (5 URLs)."""
        # Remove existing pack.db to force fresh build
        db_path = PACKS_DIR / "ladybugdb-expert" / "pack.db"
        if db_path.exists():
            if db_path.is_dir():
                shutil.rmtree(db_path)
            else:
                db_path.unlink()

        result = run_script(
            [str(SCRIPTS_DIR / "build_ladybugdb_expert_pack.py"), "--test-mode"],
            timeout=300,
        )
        assert result.returncode == 0, f"Build failed: {result.stderr[-500:]}"

        # Verify pack.db was created
        assert db_path.exists(), "pack.db not created"

        # Verify manifest was created
        manifest_path = PACKS_DIR / "ladybugdb-expert" / "manifest.json"
        assert manifest_path.exists(), "manifest.json not created"
        manifest = json.loads(manifest_path.read_text())
        assert manifest["name"] == "ladybugdb-expert"
        assert manifest["graph_stats"]["articles"] > 0

    def test_build_script_has_load_extensions(self):
        """All build scripts should import and call load_extensions."""
        for script in SCRIPTS_DIR.glob("build_*_pack.py"):
            if script.name == "build_pack_from_issue.py":
                continue
            content = script.read_text()
            assert "load_extensions" in content, (
                f"{script.name} missing load_extensions import"
            )

    def test_build_script_has_catch_all_handler(self):
        """All build scripts should have catch-all exception handler in process_url."""
        for script in SCRIPTS_DIR.glob("build_*_pack.py"):
            if script.name in ("build_pack_from_issue.py", "rebuild_all_packs.py"):
                continue
            content = script.read_text()
            # Should have both specific and catch-all handlers
            assert "except (requests.RequestException" in content, (
                f"{script.name} missing specific exception handler"
            )
            assert 'logger.warning(f"Skipping' in content, (
                f"{script.name} missing catch-all exception handler"
            )


# ============================================================================
# 3. KG Agent queries
# ============================================================================


class TestKGAgentQueries:
    """Verify KG Agent can query pack databases."""

    @pytest.fixture(autouse=True)
    def ensure_ladybugdb_pack(self):
        """Ensure ladybugdb-expert pack.db exists."""
        db_path = PACKS_DIR / "ladybugdb-expert" / "pack.db"
        if not db_path.exists():
            pytest.skip("ladybugdb-expert pack.db not built")

    def test_kg_agent_query_returns_answer(self):
        """KG Agent should return an answer with sources."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from wikigr.agent.kg_agent import KnowledgeGraphAgent; "
            "agent = KnowledgeGraphAgent("
            "  db_path='data/packs/ladybugdb-expert/pack.db', "
            "  read_only=True, use_enhancements=False); "
            "r = agent.query('What is LadybugDB?', max_results=2); "
            "print('ANSWER:', bool(r.get('answer'))); "
            "print('SOURCES:', len(r.get('sources', []))); "
            "agent.conn.close()",
        ], timeout=60)
        assert result.returncode == 0, f"Query failed: {result.stderr[-500:]}"
        assert "ANSWER: True" in result.stdout
        assert "SOURCES:" in result.stdout

    def test_kg_agent_vector_search_works(self):
        """Vector search should return results from the pack."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from wikigr.agent.kg_agent import KnowledgeGraphAgent; "
            "agent = KnowledgeGraphAgent("
            "  db_path='data/packs/ladybugdb-expert/pack.db', "
            "  read_only=True, use_enhancements=False); "
            "r = agent.query('How do I create a vector index?', max_results=3); "
            "sources = r.get('sources', []); "
            "print(f'FOUND:{len(sources)}'); "
            "agent.conn.close()",
        ], timeout=60)
        assert result.returncode == 0, f"Vector search failed: {result.stderr[-500:]}"
        assert "FOUND:" in result.stdout
        count = int(result.stdout.split("FOUND:")[1].strip().split("\n")[0])
        assert count > 0, "Vector search returned no results"


# ============================================================================
# 4. Skill installation
# ============================================================================


class TestSkillInstallation:
    """Verify skill installation generates valid SKILL.md files."""

    @pytest.fixture(autouse=True)
    def setup_skills(self, tmp_path):
        """Use a temp directory to avoid polluting .claude/skills."""
        self.skills_dir = tmp_path / "skills"
        self.skills_dir.mkdir()
        yield

    def test_install_script_dry_run(self):
        """install_pack_skills.py --dry-run should list all packs without writing."""
        result = run_script(
            [str(SCRIPTS_DIR / "install_pack_skills.py"), "--dry-run"],
        )
        assert result.returncode == 0, f"Dry run failed: {result.stderr}"
        assert "DRY RUN" in result.stdout
        assert "Would install:" in result.stdout or "Would create:" in result.stdout

    def test_install_script_creates_skills(self):
        """install_pack_skills.py should create SKILL.md for all packs."""
        result = run_script(
            [str(SCRIPTS_DIR / "install_pack_skills.py")],
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"
        assert "Installed:" in result.stdout

        # Check that at least some skills were created
        skills_dir = PROJECT_ROOT / ".claude" / "skills"
        if skills_dir.exists():
            skill_count = sum(1 for d in skills_dir.iterdir() if (d / "SKILL.md").exists())
            assert skill_count > 0, "No skills created"

    def test_generated_skill_has_valid_frontmatter(self):
        """Generated SKILL.md should have valid YAML frontmatter."""
        import yaml

        result = run_script([
            "-c",
            "import sys, json; sys.path.insert(0, '.'); "
            "from scripts.install_pack_skills import load_manifest, generate_skill_md; "
            "from pathlib import Path; "
            "pack_dir = Path('data/packs/ladybugdb-expert'); "
            "manifest = load_manifest(pack_dir); "
            "content = generate_skill_md('ladybugdb-expert', manifest, pack_dir); "
            "print(content)",
        ])
        assert result.returncode == 0, f"Generation failed: {result.stderr}"

        content = result.stdout
        assert content.startswith("---"), "Missing YAML frontmatter"
        parts = content.split("---", 2)
        assert len(parts) >= 3, "Invalid frontmatter structure"

        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "ladybugdb-expert"
        assert "description" in fm
        assert fm.get("user-invocable") is False

    def test_skill_contains_pack_db_path(self):
        """Generated skill should contain the absolute path to pack.db."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from scripts.install_pack_skills import load_manifest, generate_skill_md; "
            "from pathlib import Path; "
            "pack_dir = Path('data/packs/ladybugdb-expert'); "
            "manifest = load_manifest(pack_dir); "
            "content = generate_skill_md('ladybugdb-expert', manifest, pack_dir); "
            "print(content)",
        ])
        assert result.returncode == 0
        assert "pack.db" in result.stdout
        assert "KnowledgeGraphAgent" in result.stdout


# ============================================================================
# 5. Eval harness
# ============================================================================


class TestEvalHarness:
    """Verify the skill delivery evaluation harness works."""

    def test_eval_models_importable(self):
        """Eval data models should be importable."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from wikigr.packs.eval.skill_models import CodingTask, TaskResult, SkillDeliveryResult; "
            "from wikigr.packs.eval.skill_validators import validate_task_output; "
            "from wikigr.packs.eval.skill_evaluators import compute_composite_score; "
            "print('IMPORTS_OK')",
        ])
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "IMPORTS_OK" in result.stdout

    def test_tasks_jsonl_valid(self):
        """All tasks.jsonl files should contain valid JSON with required fields."""
        required_fields = {"id", "pack_name", "task_type", "difficulty", "prompt",
                           "ground_truth_code", "ground_truth_description", "validation"}
        for tasks_file in PACKS_DIR.glob("*/eval/tasks.jsonl"):
            with open(tasks_file) as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    task = json.loads(line)
                    missing = required_fields - set(task.keys())
                    assert not missing, (
                        f"{tasks_file}:{i} missing fields: {missing}"
                    )
                    assert task["task_type"] in ("code_gen", "debug", "config", "explain", "refactor"), (
                        f"{tasks_file}:{i} invalid task_type: {task['task_type']}"
                    )
                    assert task["difficulty"] in ("easy", "medium", "hard"), (
                        f"{tasks_file}:{i} invalid difficulty: {task['difficulty']}"
                    )

    def test_validator_extracts_code_blocks(self):
        """Validator should correctly extract fenced code blocks."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from wikigr.packs.eval.skill_validators import extract_code_blocks; "
            "output = '```python\\nx = 1\\n```\\ntext\\n```rust\\nfn main() {}\\n```'; "
            "blocks = extract_code_blocks(output); "
            "print(f'BLOCKS:{len(blocks)}'); "
            "print(f'FIRST:{blocks[0].strip()}')",
        ])
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "BLOCKS:2" in result.stdout
        assert "FIRST:x = 1" in result.stdout

    def test_validator_checks_syntax(self):
        """Validator should detect Python syntax errors in code blocks."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from wikigr.packs.eval.skill_validators import check_syntax; "
            "valid, errors = check_syntax('python', '```python\\nx = 1\\n```'); "
            "print(f'VALID:{valid}'); "
            "valid2, errors2 = check_syntax('python', '```python\\ndef f(\\n```'); "
            "print(f'INVALID:{not valid2}, ERRORS:{len(errors2)}')",
        ])
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "VALID:True" in result.stdout
        assert "INVALID:True" in result.stdout

    def test_composite_score_calculation(self):
        """Composite score should combine judge + validation correctly."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from wikigr.packs.eval.skill_models import TaskResult, ValidationResult; "
            "from wikigr.packs.eval.skill_evaluators import compute_composite_score; "
            "v = ValidationResult(True, [], {'a': True}, {}, {'fn': True}, None, None); "
            "r = TaskResult('t1', 'baseline', 'output', judge_score=8, validation=v); "
            "score = compute_composite_score(r); "
            "print(f'SCORE:{score}'); "
            "assert 0.0 <= score <= 1.0, f'Score out of range: {score}'",
        ])
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "SCORE:" in result.stdout
        score = float(result.stdout.split("SCORE:")[1].strip())
        assert 0.5 < score < 1.0, f"Unexpected score: {score}"


# ============================================================================
# 6. /kg-pack skill structure
# ============================================================================


class TestKGPackSkill:
    """Verify the /kg-pack skill is properly structured."""

    def test_distributable_skill_exists(self):
        """skills/kg-pack/SKILL.md should exist in the repo."""
        skill_path = PROJECT_ROOT / "skills" / "kg-pack" / "SKILL.md"
        assert skill_path.exists(), "Distributable /kg-pack skill not found"

    def test_skill_has_valid_frontmatter(self):
        """SKILL.md should have valid YAML frontmatter with required fields."""
        import yaml

        skill_path = PROJECT_ROOT / "skills" / "kg-pack" / "SKILL.md"
        content = skill_path.read_text()

        assert content.startswith("---"), "Missing YAML frontmatter"
        parts = content.split("---", 2)
        fm = yaml.safe_load(parts[1])

        assert fm["name"] == "kg-pack"
        assert "description" in fm
        assert fm.get("user-invocable") is True

    def test_skill_documents_all_commands(self):
        """SKILL.md should document all required subcommands."""
        skill_path = PROJECT_ROOT / "skills" / "kg-pack" / "SKILL.md"
        content = skill_path.read_text().lower()

        required_commands = ["list", "install", "build", "query", "update", "info", "uninstall"]
        for cmd in required_commands:
            assert cmd in content, f"Command '{cmd}' not documented in SKILL.md"

    def test_skill_has_setup_instructions(self):
        """SKILL.md should include setup/clone instructions."""
        skill_path = PROJECT_ROOT / "skills" / "kg-pack" / "SKILL.md"
        content = skill_path.read_text()

        assert "git clone" in content, "Missing clone instructions"
        assert "uv sync" in content, "Missing uv sync instruction"

    def test_skills_readme_exists(self):
        """skills/README.md should exist with pack listing."""
        readme = PROJECT_ROOT / "skills" / "README.md"
        assert readme.exists(), "skills/README.md not found"
        content = readme.read_text()
        assert "rust" in content.lower()
        assert "kg-pack" in content.lower()


# ============================================================================
# 7. Documentation consistency
# ============================================================================


class TestDocumentation:
    """Verify documentation references LadybugDB consistently."""

    def test_no_import_kuzu_in_python_files(self):
        """No Python file should have bare 'import kuzu' (should be 'import real_ladybug as kuzu')."""
        for py_file in PROJECT_ROOT.rglob("*.py"):
            if ".venv" in str(py_file) or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped == "import kuzu" or stripped.startswith("import kuzu "):
                    pytest.fail(f"{py_file}:{i} has bare 'import kuzu' — should be 'import real_ladybug as kuzu'")

    def test_pyproject_references_real_ladybug(self):
        """pyproject.toml should reference real_ladybug, not kuzu."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "real_ladybug" in content, "pyproject.toml missing real_ladybug dependency"
        # The keyword field may still say "kuzu" for SEO — that's OK
        # But the dependency should not
        for line in content.splitlines():
            if line.strip().startswith('"kuzu>=') or line.strip().startswith("'kuzu>="):
                pytest.fail(f"pyproject.toml still has kuzu dependency: {line.strip()}")

    def test_requirements_txt_references_real_ladybug(self):
        """requirements.txt files should reference real_ladybug."""
        for req_file in [PROJECT_ROOT / "requirements.txt", PROJECT_ROOT / "backend" / "requirements.txt"]:
            if not req_file.exists():
                continue
            content = req_file.read_text()
            assert "kuzu==" not in content, f"{req_file} still references kuzu"


# ============================================================================
# 8. Rebuild script
# ============================================================================


class TestRebuildScript:
    """Verify rebuild_all_packs.py exists and is structured correctly."""

    def test_rebuild_script_exists(self):
        """rebuild_all_packs.py should exist."""
        assert (SCRIPTS_DIR / "rebuild_all_packs.py").exists()

    def test_rebuild_script_importable(self):
        """rebuild_all_packs.py should be importable without errors."""
        result = run_script([
            "-c",
            "import sys; sys.path.insert(0, '.'); "
            "from scripts.rebuild_all_packs import find_build_scripts, rebuild_pack; "
            "scripts = find_build_scripts(); "
            "print(f'SCRIPTS:{len(scripts)}')",
        ])
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        count = int(result.stdout.split("SCRIPTS:")[1].strip())
        assert count >= 48, f"Expected >= 48 build scripts, found {count}"
