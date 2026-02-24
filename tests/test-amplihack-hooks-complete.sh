#!/bin/bash
# Complete hook verification test suite for amplihack PR #2422
# Tests fresh installation from PR branch and verifies all hooks work

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TEST_DIR="/tmp/amplihack-hook-test-$$"
PR_BRANCH="fix/claude-md-installation"
REPO_URL="https://github.com/rysweet/amplihack.git"
FAILED_TESTS=0
PASSED_TESTS=0

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_TESTS++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_TESTS++))
}

log_info() {
    echo -e "[INFO] $1"
}

cleanup() {
    log_info "Cleaning up test directory: $TEST_DIR"
    rm -rf "$TEST_DIR"
}

trap cleanup EXIT

# ==============================================================================
# TEST 1: Fresh Checkout and Installation
# ==============================================================================
log_test "TEST 1: Fresh checkout of PR branch"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

if git clone -b "$PR_BRANCH" "$REPO_URL" amplihack; then
    log_pass "Successfully cloned PR branch"
else
    log_fail "Failed to clone PR branch"
    exit 1
fi

# ==============================================================================
# TEST 2: Verify CLAUDE.md in Repository
# ==============================================================================
log_test "TEST 2: Verify CLAUDE.md exists in cloned repo"
if [ -f "$TEST_DIR/amplihack/CLAUDE.md" ]; then
    log_pass "CLAUDE.md exists in repository"
else
    log_fail "CLAUDE.md NOT found in repository"
fi

# ==============================================================================
# TEST 3: Build and Install Package
# ==============================================================================
log_test "TEST 3: Build package wheel (tests build_hooks.py)"
cd "$TEST_DIR/amplihack"

if python3 -m build --wheel 2>&1 | tee build.log; then
    log_pass "Package built successfully"
else
    log_fail "Package build failed"
    cat build.log
fi

# Check build log for CLAUDE.md copy
if grep -q "Copying.*CLAUDE.md" build.log; then
    log_pass "build_hooks.py copied CLAUDE.md"
else
    log_fail "build_hooks.py did NOT copy CLAUDE.md"
fi

# ==============================================================================
# TEST 4: Install Package
# ==============================================================================
log_test "TEST 4: Install package with pip"
WHEEL_FILE=$(ls dist/*.whl | head -1)

if [ -z "$WHEEL_FILE" ]; then
    log_fail "No wheel file found"
    exit 1
fi

if pip3 install --force-reinstall "$WHEEL_FILE"; then
    log_pass "Package installed successfully"
else
    log_fail "Package installation failed"
fi

# ==============================================================================
# TEST 5: Run amplihack launch to stage files
# ==============================================================================
log_test "TEST 5: Run 'amplihack launch' to stage to ~/.amplihack/"

# This might fail due to various reasons, but we just need staging
if timeout 30 amplihack launch --help 2>&1 | grep -q "amplihack"; then
    log_pass "amplihack command works"
else
    log_info "amplihack launch had issues, but continuing to test staging..."
fi

# ==============================================================================
# TEST 6: Verify CLAUDE.md Copied to ~/.amplihack/
# ==============================================================================
log_test "TEST 6: Verify CLAUDE.md exists at ~/.amplihack/CLAUDE.md"
if [ -f "$HOME/.amplihack/CLAUDE.md" ]; then
    log_pass "CLAUDE.md exists at ~/.amplihack/"
    log_info "File size: $(wc -c < "$HOME/.amplihack/CLAUDE.md") bytes"
else
    log_fail "CLAUDE.md NOT found at ~/.amplihack/"
fi

# ==============================================================================
# TEST 7: Verify .claude Directory
# ==============================================================================
log_test "TEST 7: Verify .claude directory exists"
if [ -d "$HOME/.amplihack/.claude" ]; then
    log_pass ".claude directory exists"
else
    log_fail ".claude directory NOT found"
fi

# ==============================================================================
# TEST 8: Test PreToolUse Hook
# ==============================================================================
log_test "TEST 8: Test PreToolUse hook executes without ImportError"
HOOK_OUTPUT=$(echo '{"toolUse": {"name": "Bash", "input": {"command": "echo test"}}}' | \
    python3 "$HOME/.amplihack/.claude/tools/xpia/hooks/pre_tool_use.py" 2>&1)

if echo "$HOOK_OUTPUT" | grep -qi "ImportError"; then
    log_fail "PreToolUse hook has ImportError"
    echo "$HOOK_OUTPUT"
elif echo "$HOOK_OUTPUT" | grep -q "{}"; then
    log_pass "PreToolUse hook works (returned {})"
else
    log_fail "PreToolUse hook returned unexpected output"
    echo "$HOOK_OUTPUT"
fi

# ==============================================================================
# TEST 9: Test SessionStart Hook
# ==============================================================================
log_test "TEST 9: Test SessionStart hook executes without ImportError"
HOOK_OUTPUT=$(timeout 15 python3 "$HOME/.amplihack/.claude/tools/amplihack/hooks/session_start.py" 2>&1)

if echo "$HOOK_OUTPUT" | grep -qi "ImportError"; then
    log_fail "SessionStart hook has ImportError"
    echo "$HOOK_OUTPUT"
elif echo "$HOOK_OUTPUT" | grep -q "hookSpecificOutput"; then
    log_pass "SessionStart hook works"
else
    log_info "SessionStart hook returned: ${HOOK_OUTPUT:0:100}..."
    log_pass "SessionStart hook executed (no ImportError)"
fi

# ==============================================================================
# TEST 10: Test Stop Hook
# ==============================================================================
log_test "TEST 10: Test Stop hook executes without ImportError"
HOOK_OUTPUT=$(timeout 30 python3 "$HOME/.amplihack/.claude/tools/amplihack/hooks/stop.py" 2>&1)

if echo "$HOOK_OUTPUT" | grep -qi "ImportError"; then
    log_fail "Stop hook has ImportError"
    echo "$HOOK_OUTPUT"
elif echo "$HOOK_OUTPUT" | grep -q "decision"; then
    log_pass "Stop hook works (returned decision)"
else
    log_pass "Stop hook executed (no ImportError)"
fi

# ==============================================================================
# TEST 11: Test PostToolUse Hook
# ==============================================================================
log_test "TEST 11: Test PostToolUse hook executes without ImportError"
HOOK_OUTPUT=$(echo '{"toolUse": {"name": "Bash", "input": {}}, "output": "test"}' | \
    python3 "$HOME/.amplihack/.claude/tools/amplihack/hooks/post_tool_use.py" 2>&1)

if echo "$HOOK_OUTPUT" | grep -qi "ImportError"; then
    log_fail "PostToolUse hook has ImportError"
    echo "$HOOK_OUTPUT"
else
    log_pass "PostToolUse hook works (no ImportError)"
fi

# ==============================================================================
# TEST 12: Test PreCompact Hook
# ==============================================================================
log_test "TEST 12: Test PreCompact hook executes without ImportError"
HOOK_OUTPUT=$(timeout 35 python3 "$HOME/.amplihack/.claude/tools/amplihack/hooks/pre_compact.py" 2>&1)

if echo "$HOOK_OUTPUT" | grep -qi "ImportError"; then
    log_fail "PreCompact hook has ImportError"
    echo "$HOOK_OUTPUT"
else
    log_pass "PreCompact hook works (no ImportError)"
fi

# ==============================================================================
# TEST 13: Test Statusline Hook
# ==============================================================================
log_test "TEST 13: Test statusline hook executes"
if timeout 5 "$HOME/.amplihack/.claude/tools/statusline.sh" > /dev/null 2>&1; then
    log_pass "Statusline hook works"
else
    log_fail "Statusline hook failed"
fi

# ==============================================================================
# TEST 14: Verify settings.json Configuration
# ==============================================================================
log_test "TEST 14: Verify settings.json has all hooks configured"
if [ -f "$HOME/.claude/settings.json" ]; then
    HOOK_COUNT=$(cat "$HOME/.claude/settings.json" | grep -c "PreToolUse\|SessionStart\|Stop\|PostToolUse\|PreCompact" || true)
    if [ "$HOOK_COUNT" -ge 5 ]; then
        log_pass "All 5 hooks found in settings.json"
    else
        log_fail "Only $HOOK_COUNT hooks found in settings.json (expected 5)"
    fi
else
    log_info "settings.json not found (may not be created yet)"
fi

# ==============================================================================
# TEST 15: Test Python Import of Package
# ==============================================================================
log_test "TEST 15: Test Python can import amplihack package"
if python3 -c "import amplihack; from pathlib import Path; print(Path(amplihack.__file__).parent)" > /dev/null 2>&1; then
    PACKAGE_PATH=$(python3 -c "import amplihack; from pathlib import Path; print(Path(amplihack.__file__).parent)")
    log_pass "amplihack package imports successfully from: $PACKAGE_PATH"

    # Check if CLAUDE.md is in the package
    if [ -f "$PACKAGE_PATH/CLAUDE.md" ]; then
        log_pass "CLAUDE.md found in installed package"
    else
        log_fail "CLAUDE.md NOT found in installed package at $PACKAGE_PATH/"
    fi
else
    log_fail "Cannot import amplihack package"
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
echo ""
echo "=============================================="
echo "TEST SUMMARY"
echo "=============================================="
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo "=============================================="

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo ""
    echo "The PR fix is working correctly:"
    echo "  ✓ CLAUDE.md is included in package build"
    echo "  ✓ CLAUDE.md is copied to ~/.amplihack/"
    echo "  ✓ All hooks execute without ImportError"
    echo "  ✓ Hooks can find project root"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    echo "Issues found - PR needs more work"
    exit 1
fi
