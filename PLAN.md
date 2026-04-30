# PLAN: Skill Evolution Loop Connector v2.0

**Status:** DRAFT v2.0 — Post Debate
**Author:** Systems Architect (P9) + 3-Agent Design Debate
**Date:** 2026-04-30
**Changelog from v1.0:** Decision matrix 12→14 rows, search weights inverted, tiered sandbox model, atomic mkdir lock, rate limit budget, LLM confidence intervals, 900s SLA, sanitization spec, 7th security module, immediate cascade test, input validation gate

---

## §1 — TRIGGER

### 1.1 Activation Thresholds

Evolution loop activates when skill-tester writes `test_output.json` and ANY condition is true:

| ID | Condition | Threshold | Automation |
|---|---|---|---|
| T1 | Overall critical failure | `overall_score < 40` | Auto-trigger, no human gate |
| T2 | Overall degraded | `40 <= overall_score < 60` | Auto-trigger, notification sent |
| T3 | Multi-module systemic failure | `>= 3 modules each < 50` | Auto-trigger regardless of overall |
| T4 | Single-module catastrophic | Any 1 module `< 30` | Auto-trigger even if overall >= 60 |
| T5 | Regression flag | `current < previous - 15` | Auto-trigger, bit-rot detection |

### 1.2 Pre-Trigger Input Validation (NEW v2.0)

Before evaluating any trigger, validate `test_output.json` against schema. Reject with `event: "input_invalid"` if:
- JSON is malformed or truncated
- `overall_score` is NaN, Infinity, or outside [0, 100]
- Any `module_score` is NaN, Infinity, or outside [0, 100]
- `skill_name` missing or empty
- Required fields absent

### 1.3 Non-Triggers

- `overall_score >= 70` with 0 modules `< 50` → no trigger
- `overall_score >= 60` with only 1 module 40-49 → logged, deferred
- Skill not in skill-tester manifest → no trigger
- Skill tagged `evolution: false` → skip permanently
- First-ever test (no baseline) → T5 disabled; T1-T4 only
- Score fluctuation `|delta| < 5` → noise, logged only

### 1.4 7-Module Criteria (NEW: +security_audit)

| Module | Critical Fail | Degraded | Symptom |
|---|---|---|---|
| M1 — Syntax/Parse | `< 50` | 50-64 | YAML/frontmatter parse failure |
| M2 — Tool Reference | `< 40` | 40-59 | Referenced tools don't exist |
| M3 — Prompt Executability | `< 50` | 50-64 | Unresolved placeholders, vague verbs |
| M4 — Output Schema | `< 40` | 40-59 | No output format or schema violation |
| M5 — Dependency Chain | `< 40` | 40-59 | Referenced skills missing |
| M6 — Invocation Contract | `< 50` | 50-64 | skill-tool definition malformed |
| M7 — Security Audit | `< 50` | 50-64 | Prompt injection, exfil patterns, dangerous tools |

### 1.5 Debounce

- Same skill + same trigger ID: no re-trigger within **3600s** (1 hour)
- Uses **monotonic clock** for duration, wall clock for logging only
- State in `evolution_state.json` per skill
- Manual override: delete `evolution_state.json` to force
- Debounce reset counter: after 5 resets in 24h → escalate to human review

---

## §2 — SEARCH

### 2.1 Search Sources

| Priority | Source | Method | Timeout | Fallback |
|---|---|---|---|---|
| 1 | Local Archive | `Glob` + `Grep` on `skills-archive/` (553 skills) | 10s | → Priority 2 |
| 2 | Installed Skills | `Glob` on `~/.claude/skills/` | 5s | → Priority 3 |
| 3 | WebSearch | `"claude code skill {skill_function}"` (2 variants) | 30s | Retry 1x, → Priority 4 |
| 4 | GitHub WebSearch | `site:github.com claude code skill {skill_name}` | 30s | → dead-letter |

**NEW v2.0:** Rate limit budget enforced before each external call. If limit hit → fall back to archive-only, log `event: "rate_limited"`.

### 2.2 Match Criteria (>= 3 of 5)

| Criterion | Check | Weight |
|---|---|---|
| C1 — Name similarity | `jaro_winkler(skill_name, candidate) >= 0.70` | 20% |
| C2 — Functional overlap | Description shares >= 1 verb + >= 1 noun | 15% |
| C3 — Tool footprint match | >= 50% of original's declared tools present | **30%** |
| C4 — Source freshness | Archive: < 180 days. GitHub: stars >= 5 | 10% |
| C5 — Dependency discipline | Candidate deps <= original deps + 3 | 5% |
| **C6 — Failing module coverage** | Candidate excels in modules that triggered loop | **20%** |

### 2.3 Ranking Formula (v2.0 — weights inverted from v1.0)

```
RANK_SCORE = (C1 × 0.20) + (C2 × 0.15) + (C3 × 0.30) + (C4 × 0.10) + (C5 × 0.05) + (C6 × 0.20)

>= 0.70 → strong candidate
0.50-0.69 → weak candidate, collect up to 3
< 0.50  → discard
```

**Rationale:** C3 (Tool footprint) is the strongest signal of functional equivalence — tools are concrete named APIs. C2 (Functional overlap) is lexical-only, high false-positive rate. v1.0 had these inverted. C6 connects ranking directly to the failure that triggered the loop.

### 2.4 skill_name Sanitization (NEW v2.0)

Before ANY search query construction or path construction:
- Reject if contains: `/`, `\`, `..`, `:`, `<`, `>`, `"`, `|`, `?`, `*`
- Reject if matches (case-insensitive): `CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`
- Reject if length > 64 or empty/whitespace-only
- Allowed pattern: `^[a-zA-Z0-9_-]+$`

---

## §3 — INSTALL

### 3.1 Tiered Sandbox Model (NEW v2.0)

| Source | Sandbox Type | Pre-Test Gate |
|---|---|---|
| Archive (Priority 1) | Filesystem isolation | None |
| Installed (Priority 2) | Filesystem isolation | None |
| GitHub >= 5 stars (Priority 4) | Filesystem + prompt scan | Run M7 security_audit before main test |
| WebSearch raw (Priority 3) | Filesystem + prompt scan | **Human review required before test** |

Sandbox paths:
```
.sandbox/{skill_name}__candidate_{ts}/      # Rank 1
.sandbox/{skill_name}__candidate_r2_{ts}/   # Rank 2
.sandbox/{skill_name}__candidate_r3_{ts}/   # Rank 3
```

### 3.2 Dependency Resolution

1. Parse `## Requires` / `## Dependencies` / YAML frontmatter `requires:` / YAML `dependencies:`
2. Check each against installed manifest
3. Classify: SATISFIED / UNSATISFIED_ARCHIVE (auto-restore) / UNSATISFIED_EXTERNAL (block)
4. Max depth: **3 levels**
5. Circular detected → disqualify
6. **NEW:** Candidate must not depend on skill it replaces

### 3.3 Archive Integrity (NEW v2.0)

On archive restore: verify SHA-256 checksum against stored manifest. If mismatch → disqualify candidate, log `event: "archive_integrity_failure"`.

### 3.4 Install Failure Handling

| Failure | Action | Retries |
|---|---|---|
| File copy error | Skip candidate, try next | 0 |
| Sandbox dir creation fails | Abort loop for this skill | 2 (10s spacing) |
| Candidate empty / malformed / > 100KB | Reject, log | 0 |
| SHA-256 mismatch on archive restore | Disqualify, log | 0 |
| Path sanitization rejects skill_name | Reject candidate | 0 |

---

## §4 — TEST

### 4.1 Test Protocol

```
skill-tester \
  --target {sandbox_path} \
  --modules tool_usage,prompt_alignment,output_schema,error_handling,self_description,edge_case_coverage,security_audit \
  --steps 8 \
  --output test_output_candidate.json \
  --timeout-per-module 30
```

### 4.2 Test Dimensions (7 modules — v2.0)

| Module | Weight | Measures |
|---|---|---|
| `tool_usage` | 0.18 | Correct invocation of declared tools |
| `prompt_alignment` | 0.18 | Output matches declared purpose |
| `output_schema` | 0.13 | JSON output matches expected schema |
| `error_handling` | 0.13 | Graceful handling of bad/missing inputs |
| `self_description` | 0.13 | Skill accurately describes capabilities |
| `edge_case_coverage` | 0.15 | Handles boundary inputs |
| **`security_audit`** | **0.10** | **Prompt injection patterns, exfil URLs, dangerous tool calls** |

### 4.3 LLM Confidence Intervals (NEW v2.0)

- Run skill-tester on candidate **3 times**
- Compute mean + 95% confidence interval
- Use **lower bound of CI** for decision matrix, not point estimate
- Hysteresis: auto-replace requires candidate score >= threshold **+ 5 points**
- Log `score_variance`, `ci_lower`, `ci_upper` to evolution_log.jsonl

### 4.4 Candidate Minimum Bar

- Mean overall_score >= 50 (lower bound >= 45)
- No single module mean < 30
- security_audit module must not flag candidate (score >= 50 on M7)
- Candidates failing → discarded, logged `candidate_rejected_pretest`

### 4.5 Test Constraints

- 3 runs per candidate (for CI computation)
- Timeout: 120s per candidate per run, **parallel** across candidates
- Retries: 1 on infrastructure failure; 0 on score failure
- Test artifacts in sandbox directory only

---

## §5 — DECISION MATRIX (v2.0 — 14 rows, full coverage)

**Evaluation rule:** Rows evaluated top-to-bottom. First row where ALL conditions are satisfied is selected. D14 is catch-all.

| Row | Old Score | Candidate Score | Delta | Action |
|---|---|---|---|---|
| D1 | `< 40` | `>= 75` | `>= +35` | **Auto-replace** |
| D2 | `< 50` | `>= 80` | `>= +30` | **Auto-replace** |
| D3 | `< 60` | `>= 80` | `>= +20` | **Auto-replace + notify** |
| D4 | `< 60` | `70–79` | `>= +10` | Flag for human review |
| D5 | `< 60` | `60–69` | `>= +5` | Flag for human review (marginal) |
| D6 | `< 60` | `>= 70` | `< +10` | Keep original, log gap |
| D7 | `< 60` | `< 60` | any | Keep original |
| D8 | `60–75` | `>= 85` | `>= +10` | Flag for human review |
| D9 | `60–75` | `60–84` | any | Keep original |
| D10 | `60–75` | `< 60` | any | Keep original |
| D11 | `>= 76` | `>= 90` | `>= +14` | Flag for human review |
| D12 | `>= 76` | `< 90 or < +14` | — | Keep original |
| D13 | any | `< 50` | any | Reject candidate |
| **D14** | **any** | **any** | **any** | **Log + discard (catch-all)** |

**Coverage verification:** 180-cell (old_score × candidate_score × delta) truth table → every cell maps to exactly 1 row. Tested in `tests/test_matrix.py`.

### 5.2 Tie-Breaking

1. Safety-first: if one candidate = auto-replace, another = review → review wins
2. Score-based: highest composite RANK_SCORE wins
3. Source trust: Archive > Installed > GitHub (>= 5 stars) > WebSearch
4. Dependency preference: fewer external deps wins at equal score
5. Module alignment: candidate excelling in trigger-causing modules favored

### 5.3 Auto-Replace Sequence

```
1. BACKUP: cp original/ → .archive/{skill_name}__{ISO8601}/
2. VERIFY: sha256sum all files, write backup_manifest.json
3. LOCK:  atomic mkdir .locks/{skill_name}.lock/
4. SWAP:  mv candidate/ → skills/{skill_name}/
5. UNLOCK: rmdir .locks/{skill_name}.lock/
6. CASCADE: skill-tester on top-3 dependents (immediate)
7. GATE:  if new_score <= old_score OR any dependent fails → auto-revert
8. LOG:   write evolution_log.jsonl
9. NOTIFY: if D3, broadcast to SHARED_TASKS.json
```

---

## §6 — ROLLBACK

### 6.1 Backup

```
Backup path: .archive/{skill_name}__{ISO8601}/
Manifest:    backup_manifest.json (SHA-256 per file)
Verification: Re-read all files, checksum match before swap
```

### 6.2 Auto-Revert Triggers (v2.0)

| ID | Condition | Action |
|---|---|---|
| R1 | New score < old score (any amount) | Auto-revert |
| R2 | Any module that passed in BEST run in last 7 days now fails | Auto-revert |
| R3 | SHA-256 of any file mismatches expected | Auto-revert |
| **R4a** | **Immediate cascade: top-3 dependents fail after replace** | **Auto-revert within 5 min** |
| R4b | Any dependent fails within 24h (passive detection) | Auto-revert |
| R5 | Post-replace validation exceeds 300s | Auto-revert |

**v2.0 change:** R4 split into active (R4a, immediate cascade test) and passive (R4b, 24h). Tiered windows: core skills (>=5 dependents) = 1h polling, standard (1-4) = 24h, leaf (0) = skip.

### 6.3 Auto-Revert Procedure

```
1. LOCK:   atomic mkdir .locks/{skill_name}.lock/
2. MOVE:   current → .archive/{skill_name}__reverted_{ts}/
3. RESTORE: latest backup → skills/{skill_name}/
4. VERIFY:  sha256sum -c backup_manifest.json
5. RE-TEST: skill-tester on restored skill
6. CHECK:   restored score within ±3 of pre-replacement score
7. UNLOCK:  rmdir .locks/{skill_name}.lock/
8. LOG:     evolution_log.jsonl, reason code R1-R5
9. NOTIFY:  SHARED_TASKS.json priority: "high"
```

### 6.4 Backup Retention

- **50 backups per skill** (not global)
- Minimum 1 backup per skill (last backup never auto-evicted)
- FIFO eviction beyond 50
- 30-day → compress to `.tar.gz`
- 90-day → eligible for eviction (if > 1 backup exists)
- Protected: `protected: true` tag → never evicted

---

## §7 — FAILURE MODES

| ID | Mode | Detection | Response |
|---|---|---|---|
| F1 | 0 candidates found | search_results has candidate_count: 0 | SHARED_TASKS "evolution_gap", retry 24h, 3× consecutive → escalate |
| F2 | All candidates fail test | All < 50 or module < 30 | Log per-candidate scores, SHARED_TASKS, retry 7 days |
| F3 | Downstream chain break | R4a or R4b triggers | Auto-revert immediately, SHARED_TASKS critical, block further evolution |
| F4 | Filesystem error | ENOSPC/EACCES/EIO | Abort, preserve original, SHARED_TASKS high |
| F5 | Infinite loop | Same skill > 3 triggers in 60 min | Block auto-replace, force human-review only |
| F6 | Loop crash | Non-zero exit or > 900s timeout | Sandbox dirs isolated, restartable from checkpoint |
| **F7** | **Invalid input** | **test_output.json fails schema validation** | **Reject, log input_invalid, do NOT trigger** |
| **F8** | **Rate limit exhaustion** | **All external sources return 429** | **Fall back to archive-only, log, notify** |
| **F9** | **skill-tester malfunction** | **Sanity check: known-good skill scores < 50** | **Block all evolution, SHARED_TASKS critical** |

---

## §8 — INTEGRATION

### 8.1 Input Validation (NEW v2.0)

First action of evolution loop: validate `test_output.json` against JSON Schema. Fields required: `skill_name`, `overall_score`, `module_scores` (7 modules), `test_timestamp`, `exit_code`. Reject invalid input with specific error before trigger evaluation.

### 8.2 Concurrency & Locking (v2.0)

**Atomic mkdir lock** (replaces PID-file approach from v1.0):

```
Lock path:   .claude/skills/.locks/{skill_name}.lock/
Acquire:     mkdir returns 0 → locked. Returns EEXIST → contended.
Release:     rmdir after operation complete.
Stale:       If lock dir exists > 60s, check timestamp file inside.
             If timestamp > 60s old, remove lock dir (stale break).
```

`mkdir` is atomic on all filesystems. No TOCTOU race. No PID reuse problem.
**Global concurrency limit:** Max 3 simultaneous evolution loops. Additional triggers queued. Queue timeout: 3600s → escalate.

### 8.3 Rate Limiting (NEW v2.0)

Token-bucket rate limiter shared across all loops:

| API | Limit | Window | 429 Response |
|---|---|---|---|
| WebSearch | 20 | per minute | Exponential backoff 1s→2s→4s→8s, then dead-letter |
| WebSearch | 200 | per hour | Graceful degradation to archive-only |
| GitHub | 50 | per minute | Exponential backoff, then dead-letter |

Cost tracking: `cost_estimate_usd` field in evolution_log.jsonl for search events.

### 8.4 Output Contracts

**SHARED_TASKS.json** (human-review items D4/D5/D8/D11):
```json
{
  "task_id": "evo-review-{skill}-{ts}",
  "type": "skill_evolution_review",
  "priority": "medium",
  "skill": "{skill_name}",
  "old_score": 0.0,
  "candidate_name": "string",
  "candidate_score": 0.0,
  "ci_lower": 0.0,
  "delta": 0.0,
  "decision_row": "D4|D5|D8|D11",
  "candidate_source": "archive|websearch|github",
  "action_required": "approve_replace | reject_candidate",
  "created": "ISO8601",
  "expires": "ISO8601 + 7 days",
  "status": "pending"
}
```

**evolution_log.jsonl**: One JSON per line. Every line has: `ts`, `skill`, `event`. Append-only, schema-validated, **secrets scrubbed** before append. Paths logged as relative (no absolute home paths).

### 8.5 File Layout

```
.claude/projects/skill-evolution-loop/
├── PRD.md
├── PLAN.md (this file)
├── SKILL_MANIFEST.md
├── DEBATE_REPORT.md
├── README.md
├── .gitignore
├── src/
│   ├── skills/          # 7 evolution-loop skill definitions
│   ├── schemas/         # 4 JSON schemas
│   ├── config/          # thresholds.json, blacklist, security patterns
│   └── lib/             # sanitize, lock, rate_limiter, log_writer
├── tests/
│   ├── fixtures/        # skills/, candidates/, scores/
│   ├── test_matrix.py   # 180-cell decision matrix test
│   └── test_integration.py
└── logs/
```

---

## §9 — STAKEHOLDER QUESTION

### "Should the evolution loop run on schedule (cron) or on-demand?"

**Decision: On-demand primary + cron daily sweep safety net. Same as v1.0, unchanged by debate.**

| Dimension | On-Demand Only | Cron Only (24h) | Hybrid (Chosen) |
|---|---|---|---|
| Detection latency | < 5s | Up to 24h | < 5s primary, 24h max |
| Miss resilience | Low | High | High (two paths) |
| Resource cost | Near-zero | ~110s/day | Near-zero |
| Implementation complexity | Low | Low | Medium (dedup) |
| Concurrency risk | High | None | Medium (atomic lock + max 3 concurrent) |

**NEW v2.0 additions:**
- Global concurrency limit: max 3 simultaneous loops
- Cron sweep dedup: check evolution_log.jsonl for existing entry with matching skill+test_timestamp
- Graceful degradation: if rate-limited or all web sources fail → archive-only fallback

---

## §10 — SLA & PERFORMANCE (NEW v2.0)

| Metric | Target | Measurement |
|---|---|---|
| P95 trigger-to-resolution (single candidate) | < 600s | evolution_log.jsonl duration field |
| P95 trigger-to-resolution (3 candidates) | < 900s | Parallel testing keeps this under limit |
| Max concurrent loops | 3 | Global semaphore |
| Search phase | < 75s total | Per-source timeouts in §2.1 |
| Candidate test (all 3) | < 120s | Parallel execution |
| Post-replace validation | < 300s | R5 timeout |
| Loop crash timeout | 900s | F6 detection |
| Lock stale threshold | 60s | Cron cleanup |

---

## VERIFICATION

```bash
test -f C:/Users/qwqwh/.claude/projects/skill-evolution-loop/PLAN.md
grep -c "Decision Matrix\|決策矩陣" PLAN.md     # >= 1
grep -c "Rollback\|rollback" PLAN.md             # >= 1
grep -c "evolution_log.jsonl" PLAN.md            # >= 1
grep -c "skill-tester" PLAN.md                   # >= 3
grep -c "security_audit" PLAN.md                 # >= 1 (NEW)
grep -c "sanitiz" PLAN.md                        # >= 1 (NEW)
grep -c "atomic mkdir\|atomic.*lock" PLAN.md     # >= 1 (NEW)
grep -c "confidence interval\|CI" PLAN.md        # >= 1 (NEW)
grep -c "rate.limit\|rate_limit" PLAN.md         # >= 1 (NEW)
```
