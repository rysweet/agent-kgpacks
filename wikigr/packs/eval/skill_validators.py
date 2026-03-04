"""Validation methods for skill delivery evaluation output.

Provides syntax checking, content validation, and optional execution
testing for code generated during skill delivery evaluation.
"""

import re
import subprocess

from wikigr.packs.eval.skill_models import CodingTask, ValidationResult


def extract_code_blocks(output: str) -> list[str]:
    """Extract fenced code blocks from LLM output."""
    pattern = r"```(?:\w+)?\n(.*?)```"
    blocks = re.findall(pattern, output, re.DOTALL)
    return [b.strip() for b in blocks if b.strip()]


def check_syntax(language: str, output: str) -> tuple[bool, list[str]]:
    """Check syntax validity of code blocks in output."""
    blocks = extract_code_blocks(output)
    if not blocks:
        return False, ["No code blocks found in output"]

    errors = []
    for block in blocks:
        if language == "python":
            try:
                compile(block, "<eval>", "exec")
            except SyntaxError as e:
                errors.append(f"Python syntax error line {e.lineno}: {e.msg}")
        elif language in ("json",):
            import json

            try:
                json.loads(block)
            except json.JSONDecodeError as e:
                errors.append(f"JSON parse error: {e.msg}")
        elif language in ("yaml", "toml"):
            # Best-effort: check for obvious structural issues
            pass
        else:
            # For rust, go, etc.: heuristic brace balance check
            open_braces = block.count("{") + block.count("(") + block.count("[")
            close_braces = block.count("}") + block.count(")") + block.count("]")
            if abs(open_braces - close_braces) > 1:
                errors.append(f"Unbalanced brackets: {open_braces} open, {close_braces} close")

    return len(errors) == 0, errors


def check_must_contain(tokens: list[str], output: str) -> dict[str, bool]:
    """Check which required tokens are present (case-insensitive)."""
    lower_output = output.lower()
    return {token: token.lower() in lower_output for token in tokens}


def check_must_not_contain(tokens: list[str], output: str) -> dict[str, bool]:
    """Check which forbidden tokens are present. True = found = bad."""
    lower_output = output.lower()
    return {token: token.lower() in lower_output for token in tokens}


def check_expected_constructs(constructs: list[str], output: str) -> dict[str, bool]:
    """Check for expected code constructs (treated as regex patterns)."""
    results = {}
    for construct in constructs:
        try:
            results[construct] = bool(re.search(construct, output))
        except re.error:
            # If invalid regex, fall back to literal match
            results[construct] = construct in output
    return results


def run_execution_test(
    test_code: str | None, output: str
) -> tuple[bool | None, str | None]:
    """Run optional execution test against the output.

    Combines the first code block from output with test_code and runs it.
    Only supports Python execution tests.
    """
    if test_code is None:
        return None, None

    blocks = extract_code_blocks(output)
    if not blocks:
        return False, "No code blocks to test"

    full_code = blocks[0] + "\n\n" + test_code
    try:
        result = subprocess.run(
            ["python3", "-c", full_code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        passed = result.returncode == 0
        output_text = result.stdout if passed else result.stderr
        return passed, output_text[:500]
    except subprocess.TimeoutExpired:
        return False, "Execution timed out (10s)"
    except Exception as e:
        return False, f"Execution error: {e}"


def validate_task_output(task: CodingTask, output: str) -> ValidationResult:
    """Run all validation checks on task output."""
    syntax_valid, syntax_errors = check_syntax(task.validation.language, output)
    contains_required = check_must_contain(task.validation.must_contain, output)
    contains_forbidden = check_must_not_contain(task.validation.must_not_contain, output)
    constructs_found = check_expected_constructs(task.validation.expected_constructs, output)
    exec_passed, exec_output = run_execution_test(task.validation.execution_test, output)

    return ValidationResult(
        syntax_valid=syntax_valid,
        syntax_errors=syntax_errors,
        contains_required=contains_required,
        contains_forbidden=contains_forbidden,
        constructs_found=constructs_found,
        execution_passed=exec_passed,
        execution_output=exec_output,
    )
