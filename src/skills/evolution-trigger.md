---
name: evolution-trigger
description: Evaluates trigger conditions (T1-T5) from skill-tester output. Input validation, debounce check, non-trigger exclusion.
type: skill
tools:
  - Read
  - Grep
  - Bash
dependencies: []
evolution: true
---

## Description

Reads `test_output.json` from skill-tester, validates it against JSON Schema, evaluates 5 trigger conditions against configured thresholds, and checks debounce state. Returns trigger decision.

## Instructions

### Step 1: Read Input

Read `{skill_dir}/test_output.json`. If file missing or unreadable → return `status: "no_input"`.

### Step 2: Validate Input

Validate against `test_output.schema.json`:
- `skill_name`: non-empty, matches `^[a-zA-Z0-9_-]+$`, max 64 chars
- `overall_score`: number, 0-100, not NaN, not Infinity
- `module_scores`: all 7 modules present, each 0-100, not NaN, not Infinity
- `failing_modules`: array of strings
- `test_timestamp`: ISO 8601 date-time string

If validation fails → log `event: "input_invalid"`, return `status: "input_invalid"`, specific error detail.

### Step 3: Check Blacklist & Evolution Flag

- Check `evolution_blacklist.json`. If skill_name present → return `status: "blacklisted"`.
- Check skill metadata for `evolution: false`. If set → return `status: "evolution_disabled"`.

### Step 4: Check Blocked State

Read `.claude/skills/{skill_name}/evolution_state.json`. If `blocked: true` → return `status: "blocked"`, `block_reason`.

### Step 5: Debounce Check

Read `last_triggered_monotonic_ms` from evolution_state.json. Compare against current monotonic time. If difference < 3600000ms (1 hour) AND same trigger_id → return `status: "debounce_active"`.

Check `debounce_reset_count_24h`. If >= 5 → return `status: "debounce_throttled"`, escalate to human review.

### Step 6: Evaluate Triggers

Evaluate in order T1→T2→T3→T4→T5. First match wins.

**T1 — Critical Failure:**
`overall_score < 40` → trigger

**T2 — Degraded:**
`40 <= overall_score < 60` → trigger

**T3 — Multi-Module Systemic:**
Count modules where `module_score < 50`. If count >= 3 → trigger

**T4 — Single Module Catastrophic:**
Any module score `< 30` → trigger

**T5 — Regression:**
`previous_score` exists AND `(previous_score - overall_score) >= 15` → trigger

### Step 7: Score Fluctuation Filter

If `previous_score` exists AND `|overall_score - previous_score| < 5` → log noise, return `status: "no_trigger", reason: "score_fluctuation_noise"`.

### Step 8: First-Run Handling

If no `previous_score` (first-ever test) → T5 disabled. Only T1-T4 evaluated.

### Step 9: Non-Trigger Exclusion

If `overall_score >= 70` AND 0 modules < 50 → return `status: "no_trigger", reason: "skill_healthy"`.

If `overall_score >= 60` AND only 1 module in 40-49 → return `status: "no_trigger", reason: "deferred_isolated_degradation"`.

### Step 10: Update State

If triggered: write `evolution_state.json` with:
- `last_triggered_monotonic_ms`: current monotonic time
- `last_triggered_wallclock`: current ISO 8601
- `last_trigger_id`: T1/T2/T3/T4/T5
- `debounce_reset_count_24h`: incremented if different failing modules
- `last_test_timestamp`: from test_output.json

### Output Format

```json
{
  "status": "triggered|no_trigger|debounce_active|blocked|blacklisted|evolution_disabled|input_invalid",
  "trigger_id": "T1|T2|T3|T4|T5|null",
  "skill_name": "string",
  "overall_score": 0.0,
  "failing_modules": ["string"],
  "reason": "string"
}
```
