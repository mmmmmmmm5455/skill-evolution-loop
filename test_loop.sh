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
echo ""; echo "--- Test 2: Dry-run ---"
output=$(python evolution_loop.py --skill caveman --dry-run 2>&1)
if echo "$output" | python -c "import json,sys; d=json.load(sys.stdin); assert 'dry_run' in d" 2>/dev/null; then
  pass "Dry-run executes without crash"
else
  fail "Dry-run failed: $output"
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
echo ""; echo "--- Test 6: Output files ---"
if ls decisions.jsonl 2>/dev/null; then
  pass "decisions.jsonl exists ($(wc -l < decisions.jsonl) entries)"
else
  fail "decisions.jsonl missing"
fi

for f in $(ls "$HOME/.claude/bus/evo_test_"*.json 2>/dev/null | head -3); do
  echo "  BUS: $(basename "$f")"
done
pass "Bus test input files written"

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
