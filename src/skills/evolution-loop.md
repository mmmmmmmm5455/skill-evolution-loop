---
name: evolution-loop
description: Main orchestrator for the Skill Evolution Loop. Coordinates trigger→search→install→test→decide→rollback phases.
type: skill
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
dependencies:
  - evolution-trigger
  - evolution-search
  - evolution-install
  - evolution-test
  - evolution-decide
  - evolution-rollback
evolution: true
---

## Description

Orchestrates the closed-loop skill self-healing pipeline. Watches for skill-tester `test_output.json` files, evaluates triggers, and coordinates all 6 phases. Runs on-demand (post skill-tester hook) with cron safety net.

## Instructions

When invoked, execute each phase in sequence. Stop at any phase that returns a terminal status.

### Phase 1: Trigger Evaluation

Invoke `evolution-trigger` on the skill's `test_output.json`.

Check:
- Input validation passes (JSON Schema)
- Any T1-T5 condition met
- Debounce check passes
- Skill not blacklisted
- Skill not already blocked

Terminal conditions:
- `status: "no_trigger"` → exit, skill is healthy
- `status: "debounce_active"` → exit, recently processed
- `status: "input_invalid"` → log, exit
- `status: "blocked"` → exit, human intervention needed
- `status: "triggered"` → proceed to Phase 2

### Phase 2: Search

Invoke `evolution-search` with skill_name, failing_modules, and skill_function derived from the original skill description.

The search skill:
1. Sanitizes skill_name
2. Queries 4 sources (archive, installed, WebSearch, GitHub) with rate limiting
3. Scores candidates using 6-criterion ranking formula
4. Returns top 3 candidates in `search_results.json`

Terminal conditions:
- `candidate_count == 0` → trigger F1, write to SHARED_TASKS.json, exit
- `candidate_count > 0` → proceed to Phase 3

### Phase 3: Install

For each candidate in ranked order (max 3), invoke `evolution-install`:

1. Determine sandbox type based on source (tiered model)
2. Sanitize candidate name for path construction
3. Create sandbox directory under `.claude/skills/.sandbox/`
4. Resolve dependencies (archive→restore, installed→symlink, external→flag)
5. Verify install: file count, UTF-8, frontmatter parse, SHA-256 if from archive
6. If WebSearch source AND install_ready: set `requires_human_review: true`

Terminal conditions:
- All candidates fail install → trigger F2 variant, log, exit
- At least 1 candidate installed → proceed to Phase 4

### Phase 4: Test

For each installed candidate, invoke `evolution-test`:

1. Run skill-tester 3 times per candidate (for 95% CI)
2. 7 modules: tool_usage, prompt_alignment, output_schema, error_handling, self_description, edge_case_coverage, security_audit
3. Compute mean scores, 95% confidence interval
4. Apply hysteresis: candidate score = lower bound of CI
5. Gate check: mean >= 50, no module < 30, security_audit >= 50

Terminal conditions:
- All candidates fail minimum bar → trigger F2, log, exit
- At least 1 candidate passes → proceed to Phase 5

### Phase 5: Decide

Invoke `evolution-decide` with old_score and all candidate scores:

1. Evaluate 14-row decision matrix (D1-D14), top-down, first match wins
2. Apply tie-breaking rules if multiple candidates qualify
3. For auto-replace (D1/D2/D3): proceed to Phase 6
4. For human-review (D4/D5/D8/D11): write to SHARED_TASKS.json, exit
5. For keep/reject (D6/D7/D9/D10/D12/D13/D14): log, cleanup sandbox, exit

### Phase 6: Rollback (Replace)

For auto-replace decisions, invoke `evolution-rollback`:

1. BACKUP: copy original to `.archive/{skill}__{ISO8601}/`
2. VERIFY: SHA-256 all backup files, write manifest
3. LOCK: atomic mkdir on `.locks/{skill}.lock/`
4. SWAP: move candidate from sandbox to `skills/{skill}/`
5. UNLOCK: rmdir lock
6. CASCADE: run skill-tester on top-3 dependents immediately
7. GATE: if new_score <= old_score OR any dependent fails → auto-revert
8. LOG: append to evolution_log.jsonl
9. NOTIFY: if D3, write to SHARED_TASKS.json

### Phase 7: Cleanup

- Remove sandbox directories for discarded candidates
- Update evolution_state.json with new baseline score
- If auto-replace succeeded: update skill-tester manifest

### Logging

Every phase writes to `evolution_log.jsonl` via the log_writer library. All entries include `ts`, `skill`, `event`. Secrets scrubbed before append. Schema validated.

### Error Handling

- Any phase crash → log `loop_crash` with last phase, exit code
- 900s total timeout → F6
- Sandbox dirs are isolated → no partial mutation on crash
- Restartable from checkpoint via evolution_state.json
