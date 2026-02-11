#!/usr/bin/env bash
# Scans source code for banned patterns indicating incomplete work,
# stub implementations, or code quality issues.
set -euo pipefail

exit_code=0
echo "=== Banned Pattern Scanner ==="

# 1. TODO/FIXME/HACK/PLACEHOLDER in source code (not tests)
echo ""
echo "--- Check 1: TODO/FIXME/HACK/PLACEHOLDER in source code ---"
matches=$(git grep -nE '(TODO|FIXME|HACK|PLACEHOLDER|XXX)' \
  -- 'bootstrap/src/**/*.py' 'backend/**/*.py' ':!bootstrap/src/*/tests/*' ':!backend/tests/*' 2>/dev/null || true)
if [ -n "$matches" ]; then
  echo "ERROR: Found banned markers in source code:"
  echo "$matches"
  exit_code=1
else
  echo "  OK"
fi

# 2. assert False in test files (stub tests)
echo ""
echo "--- Check 2: Stub tests (assert False) ---"
matches=$(git grep -nE 'assert\s+False' -- '**/test_*.py' 2>/dev/null || true)
if [ -n "$matches" ]; then
  echo "ERROR: Found stub tests (assert False):"
  echo "$matches"
  exit_code=1
else
  echo "  OK"
fi

# 3. Swallowed exceptions: bare except or except Exception: pass
echo ""
echo "--- Check 3: Swallowed exceptions ---"
bare=$(git grep -nP '^\s*except\s*:' -- 'bootstrap/src/**/*.py' 'backend/**/*.py' ':!backend/tests/*' 2>/dev/null || true)
if [ -n "$bare" ]; then
  echo "ERROR: Bare except: found:"
  echo "$bare"
  exit_code=1
else
  echo "  OK"
fi

# Also check for except Exception: pass pattern
swallowed=$(git grep -nP -A1 'except\s+(Exception|BaseException)' \
  -- 'bootstrap/src/**/*.py' 'backend/**/*.py' ':!bootstrap/src/*/tests/*' ':!backend/tests/*' 2>/dev/null | \
  grep -B1 '^\s*pass\s*$' || true)
if [ -n "$swallowed" ]; then
  echo "WARNING: Potential swallowed exceptions found"
  echo "$swallowed"
fi

# 4. Debug artifacts in source code
echo ""
echo "--- Check 4: Debug artifacts ---"
matches=$(git grep -nE '(breakpoint\(\)|import\s+pdb|pdb\.set_trace)' \
  -- 'bootstrap/src/**/*.py' 'backend/**/*.py' ':!bootstrap/src/*/tests/*' ':!backend/tests/*' 2>/dev/null || true)
if [ -n "$matches" ]; then
  echo "ERROR: Debug artifacts found:"
  echo "$matches"
  exit_code=1
else
  echo "  OK"
fi

echo ""
echo "=== Scan Complete ==="
[ $exit_code -eq 0 ] && echo "All checks passed" || echo "FAILED"
exit $exit_code
