"""
TDD tests for Issue 211 Improvement 7: eval question quality for 8 losing packs.

These tests define the contract for the updated eval questions:
- Structural integrity (valid JSONL, required fields, no duplicates)
- Difficulty distribution unchanged per pack
- Pack-specific content rules enforcing the improvements described in the spec

Tests are written first (TDD) so they specify expected behaviour precisely.
Running against the pre-improvement files would produce failures; running against
the updated files should produce all-green results.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_ROOT = Path(__file__).parents[3] / "data" / "packs"

PACK_PATHS: dict[str, Path] = {
    "go-expert": DATA_ROOT / "go-expert" / "eval" / "questions.jsonl",
    "react-expert": DATA_ROOT / "react-expert" / "eval" / "questions.jsonl",
    "openai-api-expert": DATA_ROOT / "openai-api-expert" / "eval" / "questions.jsonl",
    "zig-expert": DATA_ROOT / "zig-expert" / "eval" / "questions.jsonl",
    "langchain-expert": DATA_ROOT / "langchain-expert" / "eval" / "questions.jsonl",
    "vercel-ai-sdk": DATA_ROOT / "vercel-ai-sdk" / "eval" / "questions.jsonl",
    "bicep-infrastructure": DATA_ROOT / "bicep-infrastructure" / "eval" / "questions.jsonl",
    "llamaindex-expert": DATA_ROOT / "llamaindex-expert" / "eval" / "questions.jsonl",
}

REQUIRED_FIELDS = {"id", "domain", "difficulty", "question", "ground_truth", "source"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}

# Expected total counts and difficulty distributions (unchanged from before)
EXPECTED_COUNTS: dict[str, dict[str, int]] = {
    "go-expert": {"total": 50, "easy": 20, "medium": 20, "hard": 10},
    "react-expert": {"total": 50, "easy": 20, "medium": 20, "hard": 10},
    "openai-api-expert": {"total": 50, "easy": 20, "medium": 20, "hard": 10},
    "zig-expert": {"total": 50, "easy": 20, "medium": 20, "hard": 10},
    "langchain-expert": {"total": 51, "easy": 20, "medium": 20, "hard": 11},
    "vercel-ai-sdk": {"total": 50, "easy": 20, "medium": 20, "hard": 10},
    "bicep-infrastructure": {"total": 51, "easy": 20, "medium": 20, "hard": 11},
    "llamaindex-expert": {"total": 50, "easy": 20, "medium": 20, "hard": 10},
}


_RECORDS_CACHE: dict[str, list[dict[str, Any]]] = {}


def load_records(pack: str) -> list[dict[str, Any]]:
    """Parse JSONL and return list of record dicts (cached per pack)."""
    if pack in _RECORDS_CACHE:
        return _RECORDS_CACHE[pack]
    path = PACK_PATHS[pack]
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                pytest.fail(f"{pack}: invalid JSON on line {lineno}: {exc}")
    _RECORDS_CACHE[pack] = records
    return records


def by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in records}


# ---------------------------------------------------------------------------
# Parametrised structural tests (all 8 packs)
# ---------------------------------------------------------------------------

ALL_PACKS = list(PACK_PATHS.keys())


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_file_exists(pack: str):
    """JSONL file exists on disk."""
    assert PACK_PATHS[pack].exists(), f"Missing: {PACK_PATHS[pack]}"


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_valid_jsonl(pack: str):
    """Every line in the JSONL file parses as valid JSON (load_records will fail otherwise)."""
    records = load_records(pack)
    assert len(records) > 0, f"{pack}: file is empty"


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_required_fields_present(pack: str):
    """Every record has all six required fields."""
    records = load_records(pack)
    for r in records:
        missing = REQUIRED_FIELDS - set(r.keys())
        assert not missing, f"{pack} id={r.get('id','?')}: missing fields {missing}"


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_no_empty_field_values(pack: str):
    """Required fields must not be empty strings."""
    records = load_records(pack)
    for r in records:
        for field in REQUIRED_FIELDS:
            val = r.get(field, "")
            assert (
                val and str(val).strip()
            ), f"{pack} id={r.get('id','?')}: field '{field}' is empty"


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_no_duplicate_ids(pack: str):
    """Question IDs must be unique within each pack."""
    records = load_records(pack)
    seen: set[str] = set()
    dupes = []
    for r in records:
        if r["id"] in seen:
            dupes.append(r["id"])
        else:
            seen.add(r["id"])
    assert not dupes, f"{pack}: duplicate IDs found: {dupes}"


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_valid_difficulty_values(pack: str):
    """All difficulty values must be one of easy / medium / hard."""
    records = load_records(pack)
    invalid = [
        f"id={r['id']} difficulty={r['difficulty']}"
        for r in records
        if r.get("difficulty") not in VALID_DIFFICULTIES
    ]
    assert not invalid, f"{pack}: invalid difficulty values: {invalid}"


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_question_count(pack: str):
    """Total question count must be unchanged from the specification."""
    records = load_records(pack)
    expected = EXPECTED_COUNTS[pack]["total"]
    assert len(records) == expected, f"{pack}: expected {expected} questions, got {len(records)}"


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_difficulty_distribution(pack: str):
    """Easy / medium / hard counts must be unchanged from the specification."""
    records = load_records(pack)
    by_diff: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    for r in records:
        diff = r.get("difficulty", "")
        if diff in by_diff:
            by_diff[diff] += 1
    expected = EXPECTED_COUNTS[pack]
    for diff in ("easy", "medium", "hard"):
        assert (
            by_diff[diff] == expected[diff]
        ), f"{pack}: expected {expected[diff]} {diff} questions, got {by_diff[diff]}"


# ---------------------------------------------------------------------------
# go-expert — Go 1.21-1.23 stdlib content tests
# ---------------------------------------------------------------------------

GO_TARGET_IDS = {"ge_009", "ge_010", "ge_011", "ge_012", "ge_019", "ge_020"}

# Keywords that must appear somewhere in question OR ground_truth for the target set
GO_STDLIB_KEYWORDS = {
    "ge_009": ["slices.Contains", "slices"],
    "ge_010": ["slices.Index", "-1"],
    "ge_011": ["iter.Seq", "iter"],
    "ge_012": ["math/rand/v2", "rand/v2"],
    "ge_019": ["unique", "unique.Make"],
    "ge_020": ["slices.Sorted", "Sorted"],
}


@pytest.fixture(scope="module")
def go_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("go-expert"))


def test_go_target_ids_exist(go_records: dict[str, dict[str, Any]]):
    """Target replacement question IDs must be present."""
    missing = GO_TARGET_IDS - set(go_records.keys())
    assert not missing, f"go-expert: missing target IDs: {missing}"


@pytest.mark.parametrize("qid,keywords", GO_STDLIB_KEYWORDS.items())
def test_go_stdlib_keyword_present(
    qid: str, keywords: list[str], go_records: dict[str, dict[str, Any]]
):
    """Each replaced go-expert question must reference its Go 1.21-1.23 stdlib topic."""
    r = go_records[qid]
    combined = (r["question"] + " " + r["ground_truth"]).lower()
    matched = any(kw.lower() in combined for kw in keywords)
    assert matched, (
        f"go-expert {qid}: none of {keywords} found in question/ground_truth.\n"
        f"  question: {r['question'][:120]}\n"
        f"  ground_truth: {r['ground_truth'][:120]}"
    )


def test_go_target_questions_are_easy(go_records: dict[str, dict[str, Any]]):
    """Replaced questions must still be marked easy."""
    for qid in GO_TARGET_IDS:
        r = go_records[qid]
        assert (
            r["difficulty"] == "easy"
        ), f"go-expert {qid}: expected difficulty=easy, got {r['difficulty']}"


def test_go_non_target_easy_questions_unchanged(go_records: dict[str, dict[str, Any]]):
    """Non-target easy questions (ge_001-008, ge_013-018) must still exist."""
    expected_easy_non_target = {f"ge_{i:03d}" for i in range(1, 21)} - GO_TARGET_IDS
    missing = expected_easy_non_target - set(go_records.keys())
    assert not missing, f"go-expert: non-target easy questions disappeared: {missing}"


# ---------------------------------------------------------------------------
# react-expert — React 19+ features
# ---------------------------------------------------------------------------

REACT_EASY_IDS = {f"re_{i:03d}" for i in range(1, 21)}

# Expected React 19 topics by question ID
REACT_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "re_001": ['"use client"', "use client"],
    "re_002": ['"use server"', "use server"],
    "re_003": ["use()", "use hook"],
    "re_004": ["useFormStatus"],
    "re_005": ["useOptimistic"],
    "re_006": ["<title>", "<meta>", "document metadata", "Document Metadata"],
    "re_007": ["preloadImage", "preload"],
    "re_008": ["ref", "function component", "forwardRef"],
    "re_009": ["useActionState"],
    "re_010": ["Server Component", "RSC"],
    "re_011": ["boundary", '"use client"', "use client"],
    "re_012": ["cache()"],
    "re_013": ["Server Action", "action="],
    "re_014": ["Suspense", "Server Component"],
    "re_015": ["Context", "provider"],
    "re_016": ["startTransition", "Server Action"],
    "re_017": ["ref cleanup", "cleanup function"],
    "re_018": ["prefetchDNS"],
    "re_019": ["hydration", "error"],
    "re_020": ["taint", "experimental_taintObjectReference"],
}

# String that must NOT appear in any easy react ground_truth
REACT_FORBIDDEN_STRINGS = [
    "React Expert",  # old system prompt artefact
    "As a React Expert",
]


@pytest.fixture(scope="module")
def react_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("react-expert"))


def test_react_easy_ids_exist(react_records: dict[str, dict[str, Any]]):
    """All 20 easy question IDs re_001–re_020 must be present."""
    missing = REACT_EASY_IDS - set(react_records.keys())
    assert not missing, f"react-expert: missing easy IDs: {missing}"


def test_react_easy_questions_are_easy(react_records: dict[str, dict[str, Any]]):
    """re_001-re_020 must have difficulty=easy."""
    for qid in REACT_EASY_IDS:
        r = react_records[qid]
        assert (
            r["difficulty"] == "easy"
        ), f"react-expert {qid}: expected difficulty=easy, got {r['difficulty']}"


@pytest.mark.parametrize("qid,keywords", REACT_TOPIC_KEYWORDS.items())
def test_react19_topic_keyword_present(
    qid: str, keywords: list[str], react_records: dict[str, dict[str, Any]]
):
    """Each React 19 easy question must reference its specific React 19 topic."""
    r = react_records[qid]
    combined = r["question"] + " " + r["ground_truth"]
    matched = any(kw in combined for kw in keywords)
    assert matched, (
        f"react-expert {qid}: none of {keywords} found.\n"
        f"  question: {r['question'][:120]}\n"
        f"  ground_truth: {r['ground_truth'][:120]}"
    )


@pytest.mark.parametrize("forbidden", REACT_FORBIDDEN_STRINGS)
def test_react_no_system_artefacts(forbidden: str, react_records: dict[str, dict[str, Any]]):
    """No easy question ground_truth should contain old 'React Expert' system prompt artefacts."""
    violations = [
        qid for qid in REACT_EASY_IDS if forbidden in react_records[qid].get("ground_truth", "")
    ]
    assert not violations, f"react-expert: '{forbidden}' found in ground_truth of: {violations}"


# ---------------------------------------------------------------------------
# openai-api-expert — Responses API and current model names
# ---------------------------------------------------------------------------

OA_DEPRECATED_MODEL_PATTERNS = [
    r"gpt-4-turbo\b",  # deprecated; use gpt-4o
    r"gpt-3\.5-turbo\b",  # deprecated; use gpt-4o-mini
]

OA_RESPONSES_API_IDS = {"oa_002", "oa_038", "oa_044"}

OA_RESPONSES_API_KEYWORDS: dict[str, list[str]] = {
    "oa_002": ["/v1/responses", "Responses API"],
    "oa_038": ["previous_response_id"],
    "oa_044": ["web_search", "built-in tool", "file_search", "computer_use"],
}

OA_MAX_COMPLETION_TOKENS_ID = "oa_004"

_OA_DEPRECATION_CONTEXT = re.compile(
    r"(deprecated|legacy|previously|old|former|replaced|instead of|use .* instead)",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def oa_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("openai-api-expert"))


@pytest.mark.parametrize("pattern", OA_DEPRECATED_MODEL_PATTERNS)
def test_openai_no_deprecated_model_names(pattern: str, oa_records: dict[str, dict[str, Any]]):
    """ground_truth must not recommend deprecated models as current choices."""
    compiled = re.compile(pattern)
    flagged = []
    for r in oa_records.values():
        gt = r.get("ground_truth", "")
        # Allow mentions that are clearly historical/comparison context
        # Flag only where the deprecated name appears as a recommended model
        if compiled.search(gt) and not _OA_DEPRECATION_CONTEXT.search(gt):
            flagged.append(r["id"])
    assert not flagged, (
        f"openai-api-expert: pattern '{pattern}' found in ground_truth without "
        f"deprecation context in: {flagged}"
    )


@pytest.mark.parametrize("qid,keywords", OA_RESPONSES_API_KEYWORDS.items())
def test_openai_responses_api_questions(
    qid: str, keywords: list[str], oa_records: dict[str, dict[str, Any]]
):
    """Responses API question IDs must exist and contain expected keywords."""
    assert qid in oa_records, f"openai-api-expert: {qid} not found"
    r = oa_records[qid]
    combined = r["question"] + " " + r["ground_truth"]
    matched = any(kw in combined for kw in keywords)
    assert matched, (
        f"openai-api-expert {qid}: none of {keywords} found.\n"
        f"  question: {r['question'][:120]}\n"
        f"  ground_truth: {r['ground_truth'][:120]}"
    )


def test_openai_responses_api_count(oa_records: dict[str, dict[str, Any]]):
    """At least 3 distinct Responses API questions must be present."""
    present = OA_RESPONSES_API_IDS & set(oa_records.keys())
    assert len(present) >= 3, (
        f"openai-api-expert: expected >=3 Responses API questions "
        f"({OA_RESPONSES_API_IDS}), found {present}"
    )


def test_openai_max_completion_tokens_for_reasoning(oa_records: dict[str, dict[str, Any]]):
    """oa_004 ground_truth must mention max_completion_tokens for reasoning models."""
    r = oa_records[OA_MAX_COMPLETION_TOKENS_ID]
    gt = r["ground_truth"]
    assert "max_completion_tokens" in gt, (
        f"openai-api-expert oa_004: 'max_completion_tokens' not found in ground_truth.\n"
        f"  ground_truth: {gt[:200]}"
    )


def test_openai_current_models_mentioned(oa_records: dict[str, dict[str, Any]]):
    """At least one of the current flagship models (gpt-4o, o1, o3) must appear
    in ground_truth answers that discuss model recommendations."""
    current_models = ["gpt-4o", "gpt-4o-mini", "o1", "o3"]
    # oa_009 is explicitly about current model names
    r = oa_records.get("oa_009", {})
    gt = r.get("ground_truth", "")
    matched = any(m in gt for m in current_models)
    assert matched, (
        f"openai-api-expert oa_009: none of {current_models} found in ground_truth.\n"
        f"  ground_truth: {gt[:200]}"
    )


# ---------------------------------------------------------------------------
# zig-expert — No async/await (removed in Zig 0.12), correct replacements
# ---------------------------------------------------------------------------

ZIG_TARGET_IDS = {"ze_019", "ze_040", "ze_048"}

ZIG_ASYNC_PATTERNS = [
    r"\basync\b",
    r"\bawait\b",
    r"\bnosuspend\b",
    r"\bsuspend\b",
    r"\basync fn\b",
]

ZIG_REPLACEMENT_KEYWORDS: dict[str, list[str]] = {
    "ze_019": ["GeneralPurposeAllocator", "leak"],
    "ze_040": ["b.dependency", "addImport", "build system", "0.13"],
    "ze_048": ["anytype", "comptime"],
}


@pytest.fixture(scope="module")
def zig_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("zig-expert"))


@pytest.mark.parametrize("pattern", ZIG_ASYNC_PATTERNS)
def test_zig_no_async_keywords(pattern: str, zig_records: dict[str, dict[str, Any]]):
    """No question or ground_truth should reference removed Zig async/await keywords."""
    compiled = re.compile(pattern)
    flagged = [
        r["id"]
        for r in zig_records.values()
        if compiled.search(r["question"] + " " + r["ground_truth"])
    ]
    assert not flagged, f"zig-expert: async/await pattern '{pattern}' found in: {flagged}"


@pytest.mark.parametrize("qid,keywords", ZIG_REPLACEMENT_KEYWORDS.items())
def test_zig_replacement_content(
    qid: str, keywords: list[str], zig_records: dict[str, dict[str, Any]]
):
    """Replacement questions must cover their specified topics."""
    assert qid in zig_records, f"zig-expert: {qid} not found"
    r = zig_records[qid]
    combined = r["question"] + " " + r["ground_truth"]
    matched = any(kw.lower() in combined.lower() for kw in keywords)
    assert matched, (
        f"zig-expert {qid}: none of {keywords} found.\n"
        f"  question: {r['question'][:120]}\n"
        f"  ground_truth: {r['ground_truth'][:120]}"
    )


def test_zig_target_source_fields_updated(zig_records: dict[str, dict[str, Any]]):
    """Source fields for replaced questions must reflect new topics (not async_io)."""
    old_sources = {"async_io", "async_functions", "async_suspend"}
    for qid in ZIG_TARGET_IDS:
        r = zig_records[qid]
        assert (
            r["source"] not in old_sources
        ), f"zig-expert {qid}: source='{r['source']}' still references removed async topic"


# ---------------------------------------------------------------------------
# langchain-expert — LangServe deprecated, LangGraph Platform successor
# ---------------------------------------------------------------------------

LC_LANGSERVE_IDS = {"le_015", "le_035"}
LC_LANGGRAPH_KEYWORD = "LangGraph"


@pytest.fixture(scope="module")
def lc_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("langchain-expert"))


@pytest.mark.parametrize("qid", sorted(LC_LANGSERVE_IDS))
def test_langchain_langserve_mentions_langgraph_successor(
    qid: str, lc_records: dict[str, dict[str, Any]]
):
    """LangServe questions must note LangGraph Platform as the recommended successor."""
    assert qid in lc_records, f"langchain-expert: {qid} not found"
    r = lc_records[qid]
    gt = r["ground_truth"]
    assert LC_LANGGRAPH_KEYWORD in gt, (
        f"langchain-expert {qid}: '{LC_LANGGRAPH_KEYWORD}' not found in ground_truth.\n"
        f"  ground_truth: {gt[:200]}"
    )


@pytest.mark.parametrize("qid", sorted(LC_LANGSERVE_IDS))
def test_langchain_langserve_mentions_deprecation(qid: str, lc_records: dict[str, dict[str, Any]]):
    """LangServe ground_truth must note that LangServe is deprecated/soft-deprecated."""
    assert qid in lc_records, f"langchain-expert: {qid} not found"
    r = lc_records[qid]
    gt = r["ground_truth"].lower()
    deprecated_signals = ["deprecated", "soft-deprecated", "no longer", "succeeded", "successor"]
    matched = any(sig in gt for sig in deprecated_signals)
    assert matched, (
        f"langchain-expert {qid}: no deprecation signal found in ground_truth.\n"
        f"  ground_truth: {r['ground_truth'][:200]}"
    )


# ---------------------------------------------------------------------------
# vercel-ai-sdk — SSE + AI Data Stream Protocol (no WebSocket), maxSteps
# ---------------------------------------------------------------------------

VA_WEBSOCKET_PATTERN = re.compile(r"WebSocket", re.IGNORECASE)
VA_WEBSOCKET_NEGATIVE_CONTEXT_PATTERN = re.compile(
    r"(not|no|without|unsupported|excluded|instead).{0,30}WebSocket"
    r"|WebSocket.{0,30}(not|no|unsupported|excluded)",
    re.IGNORECASE,
)

VA_SSE_IDS = {"va_017", "va_034"}  # questions about streaming protocols
VA_MAXSTEPS_ID = "va_007"


@pytest.fixture(scope="module")
def va_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("vercel-ai-sdk"))


@pytest.mark.parametrize("qid", sorted(VA_SSE_IDS))
def test_vercel_no_websocket_in_streaming_questions(
    qid: str, va_records: dict[str, dict[str, Any]]
):
    """Streaming protocol questions must not *claim* the SDK uses WebSocket.

    Mentioning WebSocket in a negative/contrast context (e.g. "WebSocket is not
    natively supported") is acceptable — that is the corrected answer.  The test
    fails only when WebSocket appears without an accompanying negation that makes
    clear it is unsupported.
    """
    assert qid in va_records, f"vercel-ai-sdk: {qid} not found"
    r = va_records[qid]
    combined = r["question"] + " " + r["ground_truth"]

    if VA_WEBSOCKET_PATTERN.search(combined):
        # Allowed only if the mention is unambiguously in a "not supported" context
        has_negation = VA_WEBSOCKET_NEGATIVE_CONTEXT_PATTERN.search(combined)
        assert has_negation, (
            f"vercel-ai-sdk {qid}: 'WebSocket' present without a clear negation — "
            f"SDK uses SSE, not WebSocket.\n"
            f"  ground_truth: {r['ground_truth'][:300]}"
        )


@pytest.mark.parametrize("qid", sorted(VA_SSE_IDS))
def test_vercel_sse_mentioned_in_streaming_questions(
    qid: str, va_records: dict[str, dict[str, Any]]
):
    """Streaming protocol questions must mention SSE (Server-Sent Events)."""
    assert qid in va_records, f"vercel-ai-sdk: {qid} not found"
    r = va_records[qid]
    combined = r["question"] + " " + r["ground_truth"]
    assert "SSE" in combined or "Server-Sent Events" in combined, (
        f"vercel-ai-sdk {qid}: SSE not mentioned in streaming protocol question.\n"
        f"  ground_truth: {r['ground_truth'][:200]}"
    )


def test_vercel_maxsteps_is_primary_param(va_records: dict[str, dict[str, Any]]):
    """`maxSteps` must be identified as the primary step-limit parameter in va_007."""
    assert VA_MAXSTEPS_ID in va_records, f"vercel-ai-sdk: {VA_MAXSTEPS_ID} not found"
    r = va_records[VA_MAXSTEPS_ID]
    gt = r["ground_truth"]
    assert "maxSteps" in gt, (
        f"vercel-ai-sdk va_007: 'maxSteps' not found in ground_truth.\n"
        f"  ground_truth: {gt[:200]}"
    )


def test_vercel_ai_data_stream_protocol_mentioned(va_records: dict[str, dict[str, Any]]):
    """At least one streaming question must mention 'AI Data Stream Protocol'."""
    found = any(
        "AI Data Stream" in va_records.get(qid, {}).get("ground_truth", "") for qid in VA_SSE_IDS
    )
    assert found, (
        "vercel-ai-sdk: 'AI Data Stream Protocol' not mentioned in any streaming "
        f"question ground_truth ({VA_SSE_IDS})"
    )


# ---------------------------------------------------------------------------
# bicep-infrastructure — az.getSecret() in .bicepparam, not ARM inline syntax
# ---------------------------------------------------------------------------

BI_TARGET_ID = "bi_011"
BI_CORRECT_SYNTAX = "az.getSecret"
BI_ARM_SYNTAX_PATTERN = re.compile(r"@Microsoft\.KeyVault\(", re.IGNORECASE)
# Context patterns that indicate the ARM syntax is mentioned as a contrast/warning, not recommended
BI_ARM_CONTRAST_PATTERN = re.compile(
    r"(older|legacy|deprecated|applies to ARM|not.*\.bicepparam|ARM JSON|do not use|instead)",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def bi_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("bicep-infrastructure"))


def test_bicep_bi011_exists(bi_records: dict[str, dict[str, Any]]):
    """bi_011 must exist."""
    assert BI_TARGET_ID in bi_records, f"bicep-infrastructure: {BI_TARGET_ID} not found"


def test_bicep_bi011_uses_getSecret(bi_records: dict[str, dict[str, Any]]):
    """bi_011 ground_truth must use az.getSecret() for .bicepparam Key Vault references."""
    r = bi_records[BI_TARGET_ID]
    gt = r["ground_truth"]
    assert BI_CORRECT_SYNTAX in gt, (
        f"bicep-infrastructure bi_011: '{BI_CORRECT_SYNTAX}' not found in ground_truth.\n"
        f"  ground_truth: {gt[:300]}"
    )


def test_bicep_bi011_no_arm_inline_syntax(bi_records: dict[str, dict[str, Any]]):
    """bi_011 ground_truth must not *recommend* the ARM JSON @Microsoft.KeyVault() syntax.

    Mentioning it in a contrast/warning context (e.g. "the older @Microsoft.KeyVault(...)
    syntax applies to ARM JSON, not .bicepparam files") is acceptable and correct.
    The test fails only when the ARM syntax appears without an accompanying contrast
    that makes clear it should NOT be used for Bicep .bicepparam files.
    """
    r = bi_records[BI_TARGET_ID]
    gt = r["ground_truth"]
    if BI_ARM_SYNTAX_PATTERN.search(gt):
        # Allowed only if the ARM syntax is explicitly contrasted as wrong for Bicep
        has_contrast = BI_ARM_CONTRAST_PATTERN.search(gt)
        assert has_contrast, (
            f"bicep-infrastructure bi_011: @Microsoft.KeyVault() found without a "
            f"contrast/warning — should use az.getSecret() for Bicep .bicepparam files.\n"
            f"  ground_truth: {gt[:300]}"
        )


def test_bicep_bi011_mentions_bicepparam(bi_records: dict[str, dict[str, Any]]):
    """bi_011 question must reference .bicepparam files (not ARM template parameter files)."""
    r = bi_records[BI_TARGET_ID]
    q = r["question"]
    assert ".bicepparam" in q or "bicepparam" in q.lower(), (
        f"bicep-infrastructure bi_011: '.bicepparam' not in question.\n" f"  question: {q[:200]}"
    )


# ---------------------------------------------------------------------------
# llamaindex-expert — terminology correctness (no changes expected)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def li_records() -> dict[str, dict[str, Any]]:
    return by_id(load_records("llamaindex-expert"))


def test_llamaindex_vectorstore_terminology(li_records: dict[str, dict[str, Any]]):
    """At least one question must use the correct 'VectorStoreIndex' terminology
    (not 'VectorIndex' or other variants)."""
    correct_term = "VectorStoreIndex"
    wrong_variants = ["VectorIndex", "VectorDB", "vectorstore_index"]
    found_correct = False
    flagged = []
    for r in li_records.values():
        combined = r["question"] + r["ground_truth"]
        if correct_term in combined:
            found_correct = True
        if any(v in combined for v in wrong_variants):
            flagged.append(r["id"])
    assert (
        found_correct
    ), f"llamaindex-expert: '{correct_term}' not found in any question/ground_truth"
    assert (
        not flagged
    ), f"llamaindex-expert: incorrect index name variants {wrong_variants} found in: {flagged}"


def test_llamaindex_no_wrong_index_names(li_records: dict[str, dict[str, Any]]):
    """Questions must not use incorrect LlamaIndex class names like 'GPTVectorStoreIndex'
    (the old 0.8.x name; current is VectorStoreIndex)."""
    old_names = ["GPTVectorStoreIndex", "GPTSimpleVectorIndex", "GPTListIndex"]
    flagged = [
        r["id"]
        for r in li_records.values()
        if any(name in r["question"] + r["ground_truth"] for name in old_names)
    ]
    assert not flagged, f"llamaindex-expert: deprecated class names found in: {flagged}"


def test_llamaindex_agentworkflow_terminology(li_records: dict[str, dict[str, Any]]):
    """If any question covers agentic workflows, it must use 'AgentWorkflow' (not 'agent_workflow')."""
    # Look for records that discuss agents/workflows
    agentic = [
        r for r in li_records.values() if "agent" in (r["question"] + r["ground_truth"]).lower()
    ]
    for r in agentic:
        combined = r["question"] + r["ground_truth"]
        # Check that snake_case variants are not used where CamelCase is expected
        assert "agent_workflow" not in combined, (
            f"llamaindex-expert {r['id']}: 'agent_workflow' (snake_case) found; "
            f"should be 'AgentWorkflow' (CamelCase)"
        )


# ---------------------------------------------------------------------------
# Cross-pack security / content hygiene tests
# ---------------------------------------------------------------------------

SECURITY_PATTERNS = [
    re.compile(r"\$\([^)]+\)"),  # shell command substitution $(...)
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style API key
    re.compile(r"Bearer [A-Za-z0-9]{20,}"),  # Bearer token
]

SCRIPT_INJECTION_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+=[\"']", re.IGNORECASE),  # HTML event handlers
]


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_no_real_credentials_or_secrets(pack: str):
    """No question or ground_truth should embed real-looking credentials or tokens."""
    records = load_records(pack)
    for r in records:
        combined = r["question"] + " " + r["ground_truth"]
        for pattern in SECURITY_PATTERNS:
            match = pattern.search(combined)
            if match:
                pytest.fail(
                    f"{pack} id={r['id']}: potential credential/secret pattern "
                    f"'{pattern.pattern}' found near: '{combined[max(0,match.start()-20):match.start()+40]}'"
                )


@pytest.mark.parametrize("pack", ALL_PACKS)
def test_no_script_injection_content(pack: str):
    """No question or ground_truth should contain XSS / script injection payloads."""
    records = load_records(pack)
    for r in records:
        combined = r["question"] + " " + r["ground_truth"]
        for pattern in SCRIPT_INJECTION_PATTERNS:
            if pattern.search(combined):
                pytest.fail(
                    f"{pack} id={r['id']}: script injection pattern '{pattern.pattern}' found"
                )
