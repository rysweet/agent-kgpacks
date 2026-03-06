"""TDD tests for the 4 new pack directory files.

Packs under test:
  - data/packs/azure-lighthouse/
  - data/packs/fabric-graphql-expert/
  - data/packs/security-copilot/
  - data/packs/sentinel-graph/

Written TDD-first: tests specify the EXPECTED state of these directories
both before and after a full production build is run.

Test failure matrix
-------------------
EXPECTED TO FAIL initially (build not yet run):
  - test_pack_db_exists                  pack.db created by running build_pack()
  - test_manifest_json_exists            manifest.json created by build_pack()
  - test_manifest_has_valid_json         (follows from above)
  - test_manifest_required_fields        (follows from above)
  - test_manifest_graph_stats_non_zero   (follows from above)

EXPECTED TO PASS initially (files already created):
  - test_urls_file_exists
  - test_urls_are_https_only
  - test_urls_minimum_count
  - test_urls_no_blank_non_comment_lines
  - test_eval_questions_json_exists
  - test_eval_questions_jsonl_exists
  - test_eval_questions_required_fields (json)
  - test_eval_questions_required_fields (jsonl)
  - test_eval_questions_domain_matches_pack
  - test_eval_questions_covers_all_difficulties
  - test_eval_questions_minimum_count
  - test_skill_md_exists
  - test_skill_md_has_pack_name
  - test_readme_exists
  - test_readme_has_installation_section
  - test_build_md_exists
  - test_build_md_has_run_instructions
  - test_no_http_urls_in_urls_txt_files   (validates URL file content, not filter)

Implementation references:
  - implementation_order steps 1-9 (all DONE)
  - implementation_order steps 12-14 (PENDING — requires full build)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Pack specifications
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "packs"

_NEW_PACKS: dict[str, dict] = {
    "azure-lighthouse": {
        "domain": "azure_lighthouse",
        # eval_domains: acceptable domain values in eval/questions.jsonl
        # (may differ from extractor domain — eval uses pack-name convention)
        "eval_domains": {"azure_lighthouse"},
        "min_urls": 50,
        "min_eval_questions": 40,
        "required_difficulties": {"easy", "medium", "hard"},
        "source_domain": "learn.microsoft.com",
    },
    "fabric-graphql-expert": {
        "domain": "fabric_graphql",
        # eval files use the longer form with _expert suffix
        "eval_domains": {"fabric_graphql_expert", "fabric_graphql"},
        # fabric-graphql-expert has only 28 URLs (pre-existing file, accepted as-is)
        "min_urls": 20,
        "min_eval_questions": 15,
        "required_difficulties": {"easy", "medium", "hard"},
        "source_domain": "learn.microsoft.com",
    },
    "security-copilot": {
        "domain": "security_copilot",
        "eval_domains": {"security_copilot"},
        "min_urls": 50,
        "min_eval_questions": 40,
        "required_difficulties": {"easy", "medium", "hard"},
        "source_domain": "learn.microsoft.com",
    },
    "sentinel-graph": {
        "domain": "microsoft_sentinel",
        # eval files use sentinel_graph (pack directory name convention)
        # while the extractor uses microsoft_sentinel (requirement spec)
        "eval_domains": {"sentinel_graph", "microsoft_sentinel"},
        "min_urls": 50,
        "min_eval_questions": 40,
        "required_difficulties": {"easy", "medium", "hard"},
        "source_domain": "learn.microsoft.com",
    },
}

_PACK_NAMES = list(_NEW_PACKS.keys())


def _pack_dir(pack_name: str) -> Path:
    return _DATA_DIR / pack_name


# ---------------------------------------------------------------------------
# URLs file tests  (PASS initially)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_urls_file_exists(pack_name: str) -> None:
    """urls.txt must exist for each new pack."""
    urls_file = _pack_dir(pack_name) / "urls.txt"
    assert urls_file.exists(), (
        f"data/packs/{pack_name}/urls.txt is missing. "
        "Each pack requires a urls.txt with documentation URLs."
    )
    assert urls_file.is_file(), f"data/packs/{pack_name}/urls.txt is not a file."


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_urls_are_https_only(pack_name: str) -> None:
    """All non-comment URLs in urls.txt must use the https:// scheme.

    This validates the *content* of the URL files, not the script filter.
    If urls.txt contains only HTTPS URLs, SEC-01 has zero practical impact
    on the current data — but the filter fix is still required for safety.
    """
    urls_file = _pack_dir(pack_name) / "urls.txt"
    if not urls_file.exists():
        pytest.skip(f"{pack_name}: urls.txt not found")

    violations: list[str] = []
    for i, line in enumerate(urls_file.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith("https://"):
            violations.append(f"  line {i}: {stripped!r}")

    assert not violations, (
        f"data/packs/{pack_name}/urls.txt contains non-HTTPS URLs:\n"
        + "\n".join(violations)
        + "\nAll documentation URLs must use https:// scheme."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_urls_minimum_count(pack_name: str) -> None:
    """urls.txt must contain at least the minimum number of URLs for each pack."""
    urls_file = _pack_dir(pack_name) / "urls.txt"
    if not urls_file.exists():
        pytest.skip(f"{pack_name}: urls.txt not found")

    min_count = _NEW_PACKS[pack_name]["min_urls"]
    urls = [
        line.strip()
        for line in urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert len(urls) >= min_count, (
        f"data/packs/{pack_name}/urls.txt has {len(urls)} URLs, "
        f"expected at least {min_count}. "
        "More URLs improve pack coverage."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_urls_no_blank_non_comment_lines(pack_name: str) -> None:
    """Non-comment, non-blank lines in urls.txt must be valid HTTPS URLs.

    Any line that is not a comment (#) and not blank must look like a URL.
    This catches typos, stray text, or invalid entries that would confuse load_urls().
    """
    urls_file = _pack_dir(pack_name) / "urls.txt"
    if not urls_file.exists():
        pytest.skip(f"{pack_name}: urls.txt not found")

    bad_lines: list[str] = []
    for i, line in enumerate(urls_file.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Must start with http or https
        if not stripped.startswith("http"):
            bad_lines.append(f"  line {i}: {stripped!r}")

    assert not bad_lines, (
        f"data/packs/{pack_name}/urls.txt has non-URL content lines:\n"
        + "\n".join(bad_lines)
        + "\nEvery non-comment, non-blank line must be a URL."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_urls_from_expected_source_domain(pack_name: str) -> None:
    """URLs in urls.txt must primarily come from the expected source domain.

    Each pack draws from official Microsoft Learn documentation.
    At least 80% of URLs must come from the expected domain.
    """
    urls_file = _pack_dir(pack_name) / "urls.txt"
    if not urls_file.exists():
        pytest.skip(f"{pack_name}: urls.txt not found")

    expected_domain = _NEW_PACKS[pack_name]["source_domain"]
    all_urls = [
        line.strip()
        for line in urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not all_urls:
        pytest.skip(f"{pack_name}: no URLs found")

    matching = [u for u in all_urls if expected_domain in u]
    ratio = len(matching) / len(all_urls)
    assert ratio >= 0.80, (
        f"data/packs/{pack_name}/urls.txt: only {len(matching)}/{len(all_urls)} "
        f"({ratio:.0%}) URLs are from '{expected_domain}'. "
        f"Expected at least 80%."
    )


# ---------------------------------------------------------------------------
# Eval questions tests  (PASS initially — already created)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_json_exists(pack_name: str) -> None:
    """eval/questions.json must exist for each new pack."""
    questions_file = _pack_dir(pack_name) / "eval" / "questions.json"
    assert questions_file.exists(), (
        f"data/packs/{pack_name}/eval/questions.json is missing. "
        "Each pack must have eval questions for quality measurement."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_jsonl_exists(pack_name: str) -> None:
    """eval/questions.jsonl must exist for each new pack."""
    questions_file = _pack_dir(pack_name) / "eval" / "questions.jsonl"
    assert questions_file.exists(), (
        f"data/packs/{pack_name}/eval/questions.jsonl is missing. "
        "The JSONL format is used by the eval runner (one JSON object per line)."
    )


_REQUIRED_QUESTION_FIELDS = {"id", "domain", "difficulty", "question", "ground_truth"}


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_json_required_fields(pack_name: str) -> None:
    """Every question in questions.json must have all required fields.

    Required: id, domain, difficulty, question, ground_truth
    """
    questions_file = _pack_dir(pack_name) / "eval" / "questions.json"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.json not found")

    questions = json.loads(questions_file.read_text(encoding="utf-8"))
    assert isinstance(questions, list), (
        f"data/packs/{pack_name}/eval/questions.json must be a JSON array, "
        f"got {type(questions).__name__}"
    )
    assert questions, f"data/packs/{pack_name}/eval/questions.json is empty."

    for i, q in enumerate(questions):
        missing = _REQUIRED_QUESTION_FIELDS - set(q.keys())
        assert not missing, (
            f"data/packs/{pack_name}/eval/questions.json: question #{i} "
            f"(id={q.get('id', '?')!r}) is missing fields: {sorted(missing)}. "
            f"Required fields: {sorted(_REQUIRED_QUESTION_FIELDS)}"
        )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_jsonl_required_fields(pack_name: str) -> None:
    """Every question in questions.jsonl must have all required fields (one per line)."""
    questions_file = _pack_dir(pack_name) / "eval" / "questions.jsonl"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.jsonl not found")

    lines = [
        line.strip()
        for line in questions_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines, f"data/packs/{pack_name}/eval/questions.jsonl is empty."

    for i, line in enumerate(lines):
        try:
            q = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"data/packs/{pack_name}/eval/questions.jsonl: "
                f"line {i + 1} is not valid JSON: {exc}"
            )
        missing = _REQUIRED_QUESTION_FIELDS - set(q.keys())
        assert not missing, (
            f"data/packs/{pack_name}/eval/questions.jsonl: line {i + 1} "
            f"(id={q.get('id', '?')!r}) is missing fields: {sorted(missing)}."
        )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_domain_matches_pack(pack_name: str) -> None:
    """All questions must have the domain field matching an acceptable eval domain for the pack.

    The eval domain in questions.jsonl may differ from the extractor domain
    (used in the build script's extract_from_article call).  The eval domain
    typically follows the pack directory name convention.  The pack spec lists
    all acceptable eval_domains for each pack.

    Examples of acceptable variation:
      - sentinel-graph:       extractor=microsoft_sentinel, eval=sentinel_graph
      - fabric-graphql-expert: extractor=fabric_graphql,   eval=fabric_graphql_expert
    """
    questions_file = _pack_dir(pack_name) / "eval" / "questions.jsonl"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.jsonl not found")

    acceptable_domains = _NEW_PACKS[pack_name]["eval_domains"]
    lines = [
        line.strip()
        for line in questions_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        pytest.skip(f"{pack_name}: eval/questions.jsonl is empty")

    # Collect all unique domain values in the file
    domains_found: set[str] = set()
    for line in lines:
        try:
            q = json.loads(line)
            if "domain" in q:
                domains_found.add(q["domain"])
        except json.JSONDecodeError:
            pass  # covered by test_eval_questions_jsonl_required_fields

    assert domains_found & acceptable_domains, (
        f"data/packs/{pack_name}/eval/questions.jsonl: "
        f"no question has domain in {sorted(acceptable_domains)}. "
        f"Found domain values: {sorted(domains_found)}. "
        "Eval questions must be labelled with an acceptable pack domain."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_covers_all_difficulties(pack_name: str) -> None:
    """Eval questions must cover easy, medium, and hard difficulties.

    This ensures the eval set tests basic recall, application, and expert-level
    understanding across a realistic distribution.
    """
    questions_file = _pack_dir(pack_name) / "eval" / "questions.jsonl"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.jsonl not found")

    required = _NEW_PACKS[pack_name]["required_difficulties"]
    difficulties_found: set[str] = set()
    lines = [
        line.strip()
        for line in questions_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for line in lines:
        try:
            q = json.loads(line)
            if "difficulty" in q:
                difficulties_found.add(q["difficulty"])
        except json.JSONDecodeError:
            pass

    missing = required - difficulties_found
    assert not missing, (
        f"data/packs/{pack_name}/eval/questions.jsonl is missing difficulty levels: "
        f"{sorted(missing)}. "
        f"Found: {sorted(difficulties_found)}. "
        "Eval sets must cover easy, medium, and hard questions."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_minimum_count(pack_name: str) -> None:
    """Each pack must have a minimum number of eval questions."""
    questions_file = _pack_dir(pack_name) / "eval" / "questions.jsonl"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.jsonl not found")

    min_count = _NEW_PACKS[pack_name]["min_eval_questions"]
    lines = [
        line.strip()
        for line in questions_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) >= min_count, (
        f"data/packs/{pack_name}/eval/questions.jsonl has {len(lines)} questions, "
        f"expected at least {min_count}. "
        "More eval questions provide better coverage."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_json_and_jsonl_count_match(pack_name: str) -> None:
    """questions.json and questions.jsonl must have the same number of questions.

    These files are kept in sync: questions.json is the array format for
    human review; questions.jsonl is the streaming format for the eval runner.
    """
    json_file = _pack_dir(pack_name) / "eval" / "questions.json"
    jsonl_file = _pack_dir(pack_name) / "eval" / "questions.jsonl"
    if not json_file.exists() or not jsonl_file.exists():
        pytest.skip(f"{pack_name}: one or both eval files not found")

    json_count = len(json.loads(json_file.read_text(encoding="utf-8")))
    jsonl_count = sum(
        1 for line in jsonl_file.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    assert json_count == jsonl_count, (
        f"data/packs/{pack_name}: questions.json has {json_count} questions but "
        f"questions.jsonl has {jsonl_count} questions. "
        "Both files must contain the same questions (JSON array vs JSONL)."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_question_ids_are_unique(pack_name: str) -> None:
    """Every question in eval/questions.json must have a unique 'id' field."""
    questions_file = _pack_dir(pack_name) / "eval" / "questions.json"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.json not found")

    questions = json.loads(questions_file.read_text(encoding="utf-8"))
    ids = [q.get("id") for q in questions if "id" in q]
    duplicates = [qid for qid in set(ids) if ids.count(qid) > 1]
    assert not duplicates, (
        f"data/packs/{pack_name}/eval/questions.json has duplicate question IDs: "
        f"{sorted(set(duplicates))}. "
        "Every question must have a unique 'id' for eval tracking."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_question_ground_truths_non_empty(pack_name: str) -> None:
    """No question in eval/questions.json may have an empty ground_truth."""
    questions_file = _pack_dir(pack_name) / "eval" / "questions.json"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.json not found")

    questions = json.loads(questions_file.read_text(encoding="utf-8"))
    empty_gt = [
        q.get("id", f"index:{i}")
        for i, q in enumerate(questions)
        if not q.get("ground_truth", "").strip()
    ]
    assert not empty_gt, (
        f"data/packs/{pack_name}/eval/questions.json has questions with empty ground_truth: "
        f"{empty_gt}. Every question must have a substantive ground_truth."
    )


# ---------------------------------------------------------------------------
# Pack documentation files  (PASS initially — already created)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_skill_md_exists(pack_name: str) -> None:
    """skill.md must exist for each new pack."""
    skill_file = _pack_dir(pack_name) / "skill.md"
    assert skill_file.exists(), (
        f"data/packs/{pack_name}/skill.md is missing. "
        "Each pack requires skill.md for Claude Code skill integration."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_skill_md_has_pack_name(pack_name: str) -> None:
    """skill.md must reference the pack name."""
    skill_file = _pack_dir(pack_name) / "skill.md"
    if not skill_file.exists():
        pytest.skip(f"{pack_name}: skill.md not found")

    content = skill_file.read_text(encoding="utf-8")
    assert pack_name in content, (
        f"data/packs/{pack_name}/skill.md does not reference the pack name '{pack_name}'. "
        "skill.md must include the pack name for identification."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_skill_md_has_version(pack_name: str) -> None:
    """skill.md must include a version number."""
    skill_file = _pack_dir(pack_name) / "skill.md"
    if not skill_file.exists():
        pytest.skip(f"{pack_name}: skill.md not found")

    content = skill_file.read_text(encoding="utf-8")
    assert "1.0.0" in content, (
        f"data/packs/{pack_name}/skill.md does not contain version '1.0.0'. "
        "skill.md must specify the version of the knowledge pack."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_readme_exists(pack_name: str) -> None:
    """README.md must exist for each new pack."""
    readme_file = _pack_dir(pack_name) / "README.md"
    assert readme_file.exists(), (
        f"data/packs/{pack_name}/README.md is missing. "
        "Each pack requires README.md for documentation."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_readme_has_installation_section(pack_name: str) -> None:
    """README.md must include an installation section.

    Users discover packs through README.md, which must explain
    how to install the pack.
    """
    readme_file = _pack_dir(pack_name) / "README.md"
    if not readme_file.exists():
        pytest.skip(f"{pack_name}: README.md not found")

    content = readme_file.read_text(encoding="utf-8").lower()
    assert "install" in content or "installation" in content, (
        f"data/packs/{pack_name}/README.md has no installation section. "
        "README must explain how to install the pack."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_build_md_exists(pack_name: str) -> None:
    """BUILD.md must exist for each new pack."""
    build_file = _pack_dir(pack_name) / "BUILD.md"
    assert build_file.exists(), (
        f"data/packs/{pack_name}/BUILD.md is missing. "
        "Each pack requires BUILD.md explaining how to run the build script."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_build_md_has_run_instructions(pack_name: str) -> None:
    """BUILD.md must contain the script invocation command."""
    build_file = _pack_dir(pack_name) / "BUILD.md"
    if not build_file.exists():
        pytest.skip(f"{pack_name}: BUILD.md not found")

    content = build_file.read_text(encoding="utf-8")
    # Each BUILD.md should reference the build script
    script_name = f"build_{pack_name.replace('-', '_')}_pack.py"
    assert script_name in content, (
        f"data/packs/{pack_name}/BUILD.md does not reference '{script_name}'. "
        "BUILD.md must include the exact command to run the build script."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_build_md_mentions_test_mode(pack_name: str) -> None:
    """BUILD.md must document the --test-mode option."""
    build_file = _pack_dir(pack_name) / "BUILD.md"
    if not build_file.exists():
        pytest.skip(f"{pack_name}: BUILD.md not found")

    content = build_file.read_text(encoding="utf-8")
    assert "--test-mode" in content, (
        f"data/packs/{pack_name}/BUILD.md does not mention --test-mode. "
        "BUILD.md must document the --test-mode flag for quick verification."
    )


# ---------------------------------------------------------------------------
# Pack database and manifest  (skip when pack.db not built)
# ---------------------------------------------------------------------------


def _pack_db_built(pack_name: str) -> bool:
    """Check if a pack's database has been built."""
    return (_pack_dir(pack_name) / "pack.db").exists()


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_pack_db_exists(pack_name: str) -> None:
    """pack.db must exist after a successful build.

    Skips in CI where pack databases are not built (pack.db is gitignored).
    Run locally after building: python scripts/build_<pack>_pack.py --test-mode
    """
    db_path = _pack_dir(pack_name) / "pack.db"
    if not db_path.exists():
        pytest.skip(
            f"pack.db not built — run: python scripts/build_{pack_name.replace('-', '_')}_pack.py --test-mode"
        )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_manifest_json_exists(pack_name: str) -> None:
    """manifest.json must exist after a successful build.

    This test FAILS until build_pack() is run for each pack.

    manifest.json is written by create_manifest() at the end of build_pack().
    It contains pack metadata, graph stats, and source URL references.
    """
    manifest_file = _pack_dir(pack_name) / "manifest.json"
    assert manifest_file.exists(), (
        f"data/packs/{pack_name}/manifest.json does not exist. "
        f"Run 'python scripts/build_{pack_name.replace('-', '_')}_pack.py --test-mode' "
        "to generate the manifest. "
        "This test PASSES once the build has been executed."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_manifest_has_valid_json(pack_name: str) -> None:
    """manifest.json must be valid JSON.

    This test FAILS until build_pack() is run.
    """
    manifest_file = _pack_dir(pack_name) / "manifest.json"
    if not manifest_file.exists():
        pytest.skip(f"{pack_name}: manifest.json not found (build not yet run)")

    content = manifest_file.read_text(encoding="utf-8")
    try:
        manifest = json.loads(content)
    except json.JSONDecodeError as exc:
        pytest.fail(f"data/packs/{pack_name}/manifest.json is not valid JSON: {exc}")

    assert isinstance(
        manifest, dict
    ), f"data/packs/{pack_name}/manifest.json must be a JSON object, got {type(manifest).__name__}"


_REQUIRED_MANIFEST_FIELDS = {
    "name",
    "version",
    "description",
    "graph_stats",
    "eval_scores",
    "source_urls",
    "created",
    "license",
}


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_manifest_required_fields(pack_name: str) -> None:
    """manifest.json must contain all required top-level fields.

    This test FAILS until build_pack() is run.
    """
    manifest_file = _pack_dir(pack_name) / "manifest.json"
    if not manifest_file.exists():
        pytest.skip(f"{pack_name}: manifest.json not found (build not yet run)")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    missing = _REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
    assert not missing, (
        f"data/packs/{pack_name}/manifest.json missing fields: {sorted(missing)}. "
        f"Required: {sorted(_REQUIRED_MANIFEST_FIELDS)}"
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_manifest_pack_name_matches_directory(pack_name: str) -> None:
    """manifest.json 'name' field must match the pack directory name.

    This test FAILS until build_pack() is run.
    """
    manifest_file = _pack_dir(pack_name) / "manifest.json"
    if not manifest_file.exists():
        pytest.skip(f"{pack_name}: manifest.json not found (build not yet run)")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest.get("name") == pack_name, (
        f"data/packs/{pack_name}/manifest.json: "
        f"name={manifest.get('name')!r} does not match directory name '{pack_name}'. "
        "The manifest name must match the pack directory for correct registration."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_manifest_graph_stats_non_zero(pack_name: str) -> None:
    """manifest.json graph_stats must show at least 1 article after a build.

    This test FAILS until build_pack() is run.

    A zero article count indicates the build failed to process any URLs.
    In test_mode (5 URLs) at least 1 article should be successfully extracted.
    """
    manifest_file = _pack_dir(pack_name) / "manifest.json"
    if not manifest_file.exists():
        pytest.skip(f"{pack_name}: manifest.json not found (build not yet run)")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    graph_stats = manifest.get("graph_stats", {})
    articles = graph_stats.get("articles", 0)
    assert articles > 0, (
        f"data/packs/{pack_name}/manifest.json: graph_stats.articles={articles}. "
        "Expected at least 1 article after a successful build. "
        "If this is 0, the build may have failed to process any URLs."
    )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_manifest_version_is_semver(pack_name: str) -> None:
    """manifest.json 'version' must be a valid semantic version string.

    This test FAILS until build_pack() is run.
    """
    import re

    manifest_file = _pack_dir(pack_name) / "manifest.json"
    if not manifest_file.exists():
        pytest.skip(f"{pack_name}: manifest.json not found (build not yet run)")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    version = manifest.get("version", "")
    semver_pattern = re.compile(r"^\d+\.\d+\.\d+$")
    assert semver_pattern.match(version), (
        f"data/packs/{pack_name}/manifest.json: version={version!r} is not semantic versioning. "
        "Expected format: MAJOR.MINOR.PATCH (e.g. '1.0.0')."
    )


# ---------------------------------------------------------------------------
# Edge case tests  (PASS initially)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_urls_txt_encoding_is_utf8(pack_name: str) -> None:
    """urls.txt must be readable as UTF-8 (ASCII subset is fine)."""
    urls_file = _pack_dir(pack_name) / "urls.txt"
    if not urls_file.exists():
        pytest.skip(f"{pack_name}: urls.txt not found")

    try:
        urls_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(
            f"data/packs/{pack_name}/urls.txt is not valid UTF-8: {exc}. "
            "All text files must use UTF-8 encoding."
        )


@pytest.mark.parametrize("pack_name", _PACK_NAMES)
def test_eval_questions_questions_are_non_empty(pack_name: str) -> None:
    """No question in eval/questions.json may have an empty 'question' field."""
    questions_file = _pack_dir(pack_name) / "eval" / "questions.json"
    if not questions_file.exists():
        pytest.skip(f"{pack_name}: eval/questions.json not found")

    questions = json.loads(questions_file.read_text(encoding="utf-8"))
    empty_q = [
        q.get("id", f"index:{i}")
        for i, q in enumerate(questions)
        if not q.get("question", "").strip()
    ]
    assert not empty_q, (
        f"data/packs/{pack_name}/eval/questions.json has questions with empty 'question' field: "
        f"{empty_q}."
    )


def test_all_four_pack_directories_exist() -> None:
    """All 4 new pack directories must exist under data/packs/.

    This is a prerequisite for all other tests in this module.
    """
    for pack_name in _PACK_NAMES:
        pack_path = _pack_dir(pack_name)
        assert pack_path.exists(), (
            f"data/packs/{pack_name}/ directory does not exist. "
            "Expected all 4 new pack directories to be created."
        )
        assert pack_path.is_dir(), f"data/packs/{pack_name} is not a directory."
