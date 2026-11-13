#!/usr/bin/env bash
# test_loop.sh — End-to-end test of Skill Evolution Loop
# Validates all components: evolution_loop.py, bus_connector.sh, decision matrix
set -euo pipefail
cd "$(dirname "$0")"

PASS=0; FAIL=0
pass() { echo "[PASS] $1"; PASS=$((PASS + 1)); }
fail() { echo "[FAIL] $1"; FAIL=$((FAIL + 1)); }

echo "=== E2E Test: Skill Evolution Loop ==="
echo ""

# ── Test 1: Syntax check ──────────────────────────────────────────────────
echo "--- Test 1: Syntax ---"
if python -c "import py_compile; py_compile.compile('evolution_loop.py', doraise=True)" 2>&1; then
  pass "evolution_loop.py syntax valid"
else
  fail "evolution_loop.py syntax error"
fi

if bash -n bus_connector.sh 2>&1; then
  pass "bus_connector.sh syntax valid"
else
  fail "bus_connector.sh syntax error"
fi

# ── Test 2: Dry-run on existing skill ─────────────────────────────────────
echo ""; echo "--- Test 2: Read-only dry-run ---"
DECISIONS_BEFORE=$(git hash-object decisions.jsonl)
if output=$(python evolution_loop.py --skill caveman --dry-run 2>&1); then
  if echo "$output" | python -c "import json,sys; d=json.load(sys.stdin); assert d['dry_run'] and d['decision']['action'] == 'DRY_RUN_ONLY'"; then
    pass "Dry-run returns the explicit no-effects preview"
  else
    fail "Dry-run returned an invalid preview"
  fi
else
  fail "Dry-run command failed before producing valid JSON"
fi

# ── Test 3: All 5 step functions importable ────────────────────────────────
echo ""; echo "--- Test 3: Function imports ---"
if python -c "
import sys; sys.path.insert(0, '.')
from evolution_loop import step_test, step_discover, step_install, decide, run_loop
print('All 5 functions imported')
" 2>&1; then
  pass "All 5 step functions importable"
else
  fail "Function import failed"
fi

# ── Test 4: Decision matrix edge cases ─────────────────────────────────────
echo ""; echo "--- Test 4: Decision matrix ---"
python -c "
from evolution_loop import decide
errors = []

# Case 1: new >> old (auto-replace)
r = decide(40, 70, 60)
assert r['action'] == 'AUTO_REPLACE', f'Case 1 failed: got {r[\"action\"]}'

# Case 2: new > old but within threshold (flag)
r = decide(75, 82, 60)
assert r['action'] == 'FLAG_FOR_REVIEW', f'Case 2 failed: got {r[\"action\"]}'

# Case 3: new < old (keep original)
r = decide(80, 50, 60)
assert r['action'] == 'KEEP_ORIGINAL', f'Case 3 failed: got {r[\"action\"]}'

# Case 4: equal scores (flag)
r = decide(70, 70, 60)
assert r['action'] == 'FLAG_FOR_REVIEW', f'Case 4 failed: got {r[\"action\"]}'

print('All 4 decision matrix cases pass')
" 2>&1
if [[ $? -eq 0 ]]; then
  pass "Decision matrix: all edge cases correct"
else
  fail "Decision matrix edge case failed"
fi

# ── Test 5: Report mode ────────────────────────────────────────────────────
echo ""; echo "--- Test 5: Report ---"
if python evolution_loop.py --report 2>&1 | grep -q "Total decisions"; then
  pass "Report mode produces output"
else
  fail "Report mode failed"
fi

# ── Test 6: Output verification ────────────────────────────────────────────
echo ""; echo "--- Test 6: Read-only contract ---"
if [[ "$DECISIONS_BEFORE" == "$(git hash-object decisions.jsonl)" ]]; then
  pass "Dry-run did not modify decisions.jsonl"
else
  fail "Dry-run changed the decision log"
fi

if python -B -X utf8 -m unittest discover -s tests -p 'test_dry_run_contract.py' -q; then
  pass "Dry-run performs no Bus, install, external or log writes"
else
  fail "Dry-run read-only contract failed"
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo ""; echo "=============================================="
echo "Results: $PASS passed, $FAIL failed"
if [[ $FAIL -eq 0 ]]; then
  echo "EVOLUTION LOOP: ALL TESTS PASS"
  exit 0
else
  echo "EVOLUTION LOOP: $FAIL TEST(S) FAILED"
  exit 1
fi
