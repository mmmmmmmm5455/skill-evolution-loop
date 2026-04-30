# PRD: Skill Evolution Loop Connector

**Version:** 1.0
**Status:** DRAFT — post design-debate synthesis
**Author:** Multi-Agent Design Team (Architect P9 + Security Engineer + QA Lead)
**Date:** 2026-04-30
**Target completion:** 2026-05-07

---

## Executive Summary

The Skill Evolution Loop Connector is a self-healing system for the Claude Code skill ecosystem (~553 skills). When `skill-tester` detects a broken skill, the evolution loop automatically searches for alternatives, installs candidates in isolated sandboxes, tests them, and makes quantified replace-or-keep decisions. The system prioritizes safety: aggressive replacement only for critically broken skills, conservative human review for ambiguous cases, and full rollback capability with SHA-256 verified backups.

**This PRD incorporates findings from a 3-agent design debate** (Technical Director P9, Security Engineer, QA Lead) that identified 9 Critical-severity gaps in the original PLAN.md. All 9 are resolved in this PRD.

---

## 1. Product Vision

### 1.1 Problem Statement

Skills degrade over time. Dependencies break. Model behavior changes. Tool APIs evolve. Currently, when `skill-tester` discovers a broken skill (score < threshold), nothing happens automatically. A human must manually search for alternatives, test them, and decide whether to replace. With 553 skills, this is unsustainable.

### 1.2 Solution

A closed-loop system:
```
skill-tester (score < threshold)
  → search (archive + web + GitHub for alternatives)
  → install candidate (sandbox, never overwrite original)
  → test candidate (same 6 modules, 8 steps)
  → decide (quantified matrix: auto-replace / human review / keep)
  → if replace: backup original, swap, post-validate
  → if regression: auto-revert from backup
  → log everything to evolution_log.jsonl
```

### 1.3 Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Evolution loop skill-tester score | >= 80/100 | skill-tester on evolution-loop skills |
| Decision matrix coverage | 100% of input space | Automated 180-cell truth table test |
| Failure mode test coverage | 5/5 (F1-F5) | Integration tests with fixtures |
| evolution_log.jsonl validity | 100% schema-compliant | JSON Schema validation |
| Auto-revert success rate | 100% (backup restores correctly) | SHA-256 verification |
| False positive rate (bad auto-replace) | < 5% over 3 months | evolution_log.jsonl audit |
| P95 trigger-to-resolution | < 600s (single candidate) | Latency timer in log |

---

## 2. User Stories

### U1: Operator — Automatic Healing
> "As a skill ecosystem operator, when skill-tester reports a critically broken skill (score < 40), I want the system to automatically find and install a replacement without me touching anything."

**Acceptance:** T1 trigger → search → install → test → auto-replace (D1/D2/D3) completes without human intervention. evolution_log.jsonl records all steps. Original skill backed up to `.archive/`.

### U2: Operator — Human Review for Ambiguous Cases
> "As an operator, when a candidate is better but not unambiguously better (delta +10 to +19), I want a notification in SHARED_TASKS.json so I can review and approve/reject."

**Acceptance:** D4/D5/D7/D10 writes to SHARED_TASKS.json. Human sets status to "approved" or "rejected". Next loop iteration executes the decision.

### U3: Operator — Safety Net
> "As an operator, if a replacement breaks downstream skills, I want automatic rollback within minutes, not hours."

**Acceptance:** Post-replace immediate cascade test on top-3 dependents. If any dependent fails, auto-revert within 5 minutes. SHARED_TASKS.json entry created.

### U4: Developer — Audit Trail
> "As a developer investigating why a skill changed, I want a complete, machine-readable log of every evolution event."

**Acceptance:** evolution_log.jsonl is append-only, schema-valid, with ts/skill/event fields. Queryable with `jq`. No secrets in log output.

### U5: Security — Safe External Candidates
> "As a security engineer, I want web-sourced candidates scanned for prompt injection and data exfiltration patterns before they reach the test phase."

**Acceptance:** 7th test module `security_audit` (weight >= 0.10). Candidates flagged by security scanner are disqualified regardless of other scores. WebSearch candidates require manual review gate before test execution.

---

## 3. Quality Gates

### Gate 1: Design Completeness
- [ ] Decision matrix covers 100% of (old_score, candidate_score, delta) input space
- [ ] All 7 failure modes (F1-F7) have documented detection + response + escalation
- [ ] All 5 rollback triggers (R1-R5) are testable with compressed time windows

### Gate 2: Security Hardening
- [ ] skill_name sanitization rejects `../`, `..\`, `:`, `<`, `>`, `"`, `|`, `?`, `*`, Windows reserved names
- [ ] `security_audit` module scans candidates for: prompt injection patterns, URL exfiltration, unauthorized tool calls
- [ ] WebSearch candidates gated behind human approval before test execution
- [ ] Archive skills have SHA-256 integrity verification
- [ ] Logs scrubbed of secrets before append (API key patterns, tokens, absolute home paths)

### Gate 3: Test Infrastructure
- [ ] Test fixture directory with: 3 broken skills, 3 candidate skills at different quality levels, 2 mock score injectors
- [ ] Decision matrix parameterized test: 180-cell truth table, every cell maps to exactly 1 row
- [ ] R4 downstream break test with compressed 60s window (not 24h)
- [ ] Input validation test: truncated JSON, NaN scores, missing fields → rejected with specific error

### Gate 4: Performance
- [ ] Total loop timeout: 900s (not 600s — to accommodate 3-candidate worst case)
- [ ] Per-candidate test timeout: 120s
- [ ] Search phase: max 75s across all 4 sources
- [ ] Post-replace validation: max 300s
- [ ] Global concurrency limit: max 3 simultaneous evolution loops

### Gate 5: Production Readiness
- [ ] Rate limit budget enforced: 20 websearch/min, 50 github/min
- [ ] Cost tracking: `cost_estimate_usd` field in evolution_log.jsonl
- [ ] Atomic lock via `mkdir` (not PID file) — Windows compatible
- [ ] Monotonic clock for debounce (not wall clock)
- [ ] evolution_log.jsonl rotation policy: 30-day rotation, 12 monthly archives

---

## 4. Resolved Design Decisions (from 3-agent debate)

### D1: Decision Matrix — Full Coverage (resolves Architect F1, QA F1.2)

Original PLAN.md had 12 rows with uncovered input regions. Revised matrix: **14 rows with catch-all**, evaluated top-to-bottom, first match wins.

| Row | Old Score | Candidate Score | Delta | Action |
|---|---|---|---|---|
| D1 | < 40 | >= 75 | >= +35 | Auto-replace |
| D2 | < 50 | >= 80 | >= +30 | Auto-replace |
| D3 | < 60 | >= 80 | >= +20 | Auto-replace + notify |
| D4 | < 60 | 70–79 | >= +10 | Flag for human review |
| D5 | < 60 | 60–69 | >= +5 | Flag for human review (marginal) |
| D6 | < 60 | >= 70 | < +10 | Keep original, log gap |
| D7 | < 60 | < 60 | any | Keep original |
| D8 | 60–75 | >= 85 | >= +10 | Flag for human review |
| D9 | 60–75 | >= 75 | any | Keep original |
| D10 | 60–75 | < 75 | any | Keep original |
| D11 | >= 76 | >= 90 | >= +14 | Flag for human review |
| D12 | >= 76 | < 90 or < +14 | — | Keep original |
| D13 | any | < 50 | any | Reject candidate |
| **D14** | **any** | **any** | **any** | **Log + discard (catch-all)** |

### D2: Search Ranking Weights — Tool Footprint First (resolves Architect F3)

```
RANK_SCORE = (C1_name × 0.20) + (C2_functional × 0.15) + (C3_tools × 0.30)
           + (C4_freshness × 0.10) + (C5_deps × 0.05) + (C6_failing_module_match × 0.20)
```

C6 (new): Failing module coverage. If original failed on M2 (Tool Reference), candidate that scores well on M2 gets bonus.

### D3: Sandbox Model — Tiered by Source Trust (resolves Security F1, Architect F4)

| Source | Sandbox | Pre-Test Gate |
|---|---|---|
| Archive (Priority 1) | Filesystem isolation | None (trusted) |
| Installed (Priority 2) | Filesystem isolation | None |
| GitHub >= 5 stars (Priority 4) | Filesystem + prompt scan | Run `security_audit` module first |
| WebSearch raw (Priority 3) | Filesystem + prompt scan | **Human review required before test execution** |

### D4: Lock Mechanism — Atomic mkdir (resolves Architect F9, Security F6)

Replace PID-file approach with atomic `mkdir`:

```
.claude/skills/.locks/{skill_name}.lock/  ← mkdir succeeds = lock acquired
```

`mkdir` is atomic on all filesystems. No TOCTOU. 60s TTL via timestamp file inside lock dir. Cron cleanup for stale locks.

### D5: Rate Limit Budget (resolves Architect F6)

| API | Limit | Window |
|---|---|---|
| WebSearch | 20 calls | per minute |
| WebSearch | 200 calls | per hour |
| GitHub (unauthenticated) | 50 calls | per minute |

Graceful degradation: if rate limit hit → fall back to archive-only search. Log `event: "rate_limited", fallback: "archive_only"`.

### D6: LLM Score Variance — Confidence Intervals (resolves QA F5.1)

- Run skill-tester on candidate **3 times**
- Use **lower bound of 95% CI** for decision thresholds, not point estimate
- Hysteresis: auto-replace requires candidate score at least 5 points above threshold
- Log `score_variance` and `confidence_interval` to evolution_log.jsonl

### D7: SLA Timeout — 900s (resolves QA F7.1)

- Total loop timeout: **900s** (was 600s)
- Phase budgets: 75s search + 360s test (3 candidates × 120s parallel) + 300s validate + 165s buffer
- Parallel candidate testing: all 3 candidates tested concurrently (120s max, not 360s)
- This resolves the 735s > 600s contradiction

### D8: skill_name Sanitization (resolves Security F2, QA F2.4)

Reject any skill_name matching:
- Contains `/`, `\`, `..`
- Contains `:`, `<`, `>`, `"`, `|`, `?`, `*`
- Matches Windows reserved: `CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9` (case-insensitive)
- Length > 64 characters
- Empty or whitespace-only

### D9: 7th Test Module — security_audit (resolves Security F1)

| Module | Weight | Measures |
|---|---|---|
| `security_audit` | 0.10 | Static scan for prompt injection patterns, exfiltration URLs, dangerous tool calls |

All other module weights scaled proportionally to accommodate:
- tool_usage: 0.18, prompt_alignment: 0.18, output_schema: 0.13, error_handling: 0.13, self_description: 0.13, edge_case_coverage: 0.15, security_audit: 0.10

---

## 5. Architecture

### 5.1 Component Diagram

```
┌──────────────┐     test_output.json     ┌─────────────────────┐
│ skill-tester │ ──────────────────────→  │  EVOLUTION LOOP     │
└──────────────┘                           │                     │
                                           │ §1 TRIGGER          │
┌──────────────┐     candidates            │ §2 SEARCH           │
│ WebSearch    │ ←─────────────────────    │ §3 INSTALL          │
│ GitHub       │ ←─────────────────────    │ §4 TEST (7 modules) │
│ Archive/553  │ ←─────────────────────    │ §5 DECIDE (14 rows) │
└──────────────┘                           │ §6 ROLLBACK         │
                                           │ §7 FAILURE MODES    │
┌──────────────┐     human-review tasks    │ §8 INTEGRATION      │
│SHARED_TASKS  │ ←─────────────────────    └─────────────────────┘
│  .json       │                                  │
└──────────────┘                                  ▼
                                        ┌─────────────────────┐
                                        │ evolution_log.jsonl  │
                                        │ (append-only audit)  │
                                        └─────────────────────┘
```

### 5.2 Data Flow

```
1. skill-tester writes test_output.json → evolution loop reads
2. Trigger evaluation → if any T1-T5 condition met → proceed
3. Search phase → writes search_results.json (candidates)
4. Install phase → sandbox at .sandbox/{name}__candidate_{ts}/
5. Test phase → skill-tester on sandboxed candidate → test_output_candidate.json
6. Decision phase → evaluates 14-row matrix → action
7. If auto-replace: backup → swap → post-validate → log
8. If human-review: write to SHARED_TASKS.json
9. If revert: restore from .archive/ → verify SHA-256 → log
```

### 5.3 File Layout

```
.claude/projects/skill-evolution-loop/
├── PRD.md                         # This document
├── PLAN.md                        # Updated architecture spec (post-debate)
├── SKILL_MANIFEST.md              # Required skills inventory
├── DEBATE_REPORT.md               # 3-agent debate synthesis
├── README.md                      # Project overview
├── .gitignore
├── src/
│   ├── skills/
│   │   ├── evolution-loop.md      # Main orchestrator skill
│   │   ├── evolution-trigger.md   # §1 Trigger evaluation
│   │   ├── evolution-search.md    # §2 Search across 4 sources
│   │   ├── evolution-install.md   # §3 Sandbox install + dep resolution
│   │   ├── evolution-test.md      # §4 Candidate testing (7 modules)
│   │   ├── evolution-decide.md    # §5 Decision matrix evaluation
│   │   └── evolution-rollback.md  # §6 Backup, replace, auto-revert
│   ├── schemas/
│   │   ├── test_output.schema.json
│   │   ├── search_results.schema.json
│   │   ├── evolution_log.schema.json
│   │   └── evolution_state.schema.json
│   ├── config/
│   │   ├── thresholds.json        # All numeric thresholds (tunable)
│   │   ├── evolution_blacklist.json
│   │   └── security_patterns.json # Prompt injection + exfil patterns
│   └── lib/
│       ├── sanitize.py            # skill_name sanitization
│       ├── lock.py                # Atomic mkdir lock
│       ├── rate_limiter.py        # Token-bucket rate limiter
│       └── log_writer.py          # JSONL append with schema validation
├── tests/
│   ├── fixtures/
│   │   ├── skills/
│   │   │   ├── skill_good.md      # Expected score 85+
│   │   │   ├── skill_bad_yaml.md  # Broken frontmatter
│   │   │   ├── skill_bad_tools.md # References non-existent tools
│   │   │   └── skill_bad_deps.md  # Missing dependencies
│   │   ├── candidates/
│   │   │   ├── candidate_superior.md   # Score 90+
│   │   │   ├── candidate_marginal.md   # Score 70-79
│   │   │   └── candidate_malicious.md  # Contains prompt injection (security test)
│   │   └── scores/
│   │       ├── score_t1.json      # Overall < 40, triggers T1
│   │       ├── score_t2.json      # Overall 40-60, triggers T2
│   │       └── score_edge.json    # Boundary scores for matrix testing
│   ├── test_matrix.py             # 180-cell decision matrix test
│   ├── test_sanitize.py           # skill_name sanitization tests
│   ├── test_lock.py               # Lock mechanism tests
│   └── test_integration.py        # End-to-end loop tests
└── logs/
    └── .gitkeep
```

---

## 6. Skill Manifest

### 6.1 Required Skills (from archive — auto-restore)

| Skill | Archive Path | Purpose |
|---|---|---|
| `sci-skill-evolution` | `skills-archive/sci-skill-evolution/` | Existing evolution skill — study for patterns, potential base |
| `ccgs-skill-test` | `skills-archive/ccgs-skill-test/` | Skill testing framework |
| `ccgs-skill-improve` | `skills-archive/ccgs-skill-improve/` | Skill improvement patterns |
| `ccgs-security-audit` | `skills-archive/ccgs-security-audit/` | Security scanning patterns |
| `ccgs-test-helpers` | `skills-archive/ccgs-test-helpers/` | Test utilities |
| `ccgs-test-setup` | `skills-archive/ccgs-test-setup/` | Test fixture setup |
| `ccgs-architecture-decision` | `skills-archive/ccgs-architecture-decision/` | ADR template |
| `os-sandbox-file-discovery-and-validation` | `skills-archive/os-sandbox-file-discovery-and-validation/` | Sandbox file validation |
| `openviking-skill-creator` | `skills-archive/openviking-skill-creator/` | Skill authoring patterns |
| `pm-skill-authoring-workflow` | `skills-archive/pm-skill-authoring-workflow/` | PM skill authoring workflow |

### 6.2 Required Skills (installed — already active)

| Skill | Purpose |
|---|---|
| `caveman` | Terse communication mode |
| `pua` | Quality push mode |
| `brainstorming` | Design ideation |
| `github-helper` / `github-ops` | GitHub operations |
| `find-skills` | Skill discovery |
| `executing-plans` | Plan execution |
| `dispatching-parallel-agents` | Multi-agent orchestration |
| `code-audit` | Code quality review |

### 6.3 New Skills to Create

| Skill | File | Purpose |
|---|---|---|
| `evolution-loop` | `src/skills/evolution-loop.md` | Main orchestrator — coordinates all phases |
| `evolution-trigger` | `src/skills/evolution-trigger.md` | Reads test_output.json, evaluates T1-T5, debounce check |
| `evolution-search` | `src/skills/evolution-search.md` | 4-source search with rate limiting, ranking |
| `evolution-install` | `src/skills/evolution-install.md` | Sandbox install, dependency resolution, sanitization |
| `evolution-test` | `src/skills/evolution-test.md` | 7-module candidate testing, CI computation |
| `evolution-decide` | `src/skills/evolution-decide.md` | 14-row decision matrix evaluation |
| `evolution-rollback` | `src/skills/evolution-rollback.md` | Backup, swap, post-validate, auto-revert |

---

## 7. Risk Register

| ID | Risk | Severity | Mitigation | Status |
|---|---|---|---|---|
| R1 | Web candidate contains prompt injection | Critical | security_audit module + human gate for WebSearch | Resolved in PRD |
| R2 | skill_name escapes sandbox path | Critical | Sanitization: reject `../`, `..\`, reserved names | Resolved in PRD |
| R3 | Decision matrix has uncovered inputs | Critical | 14-row matrix with D14 catch-all + 180-cell test | Resolved in PRD |
| R4 | Lock fails on Windows (TOCTOU/PID reuse) | Critical | Atomic mkdir lock, 60s TTL, cron cleanup | Resolved in PRD |
| R5 | API rate limits cause cascading failure | Critical | Rate limit budget, graceful degradation to archive-only | Resolved in PRD |
| R6 | LLM score variance crosses decision boundary | Critical | 3-run CI, hysteresis (+5 above threshold) | Resolved in PRD |
| R7 | Loop timeout < actual phase sum | Critical | 900s total, parallel candidate testing | Resolved in PRD |
| R8 | Downstream break undetected for 24h | Critical | Immediate cascade test on top-3 dependents | Resolved in PRD |
| R9 | No test fixtures — untestable | Critical | Fixture directory + mock score injector defined | Resolved in PRD |
| R10 | Archive-poisoned skill auto-installed | High | SHA-256 integrity check on archive restore | Resolved in PRD |
| R11 | Secrets leak into evolution_log.jsonl | Medium | Pre-append secret scrubbing filter | Resolved in PRD |
| R12 | Search query injection via skill_name | Medium | Sanitization rejects special chars before query construction | Resolved in PRD |

---

## 8. Acceptance Criteria (for this PRD)

### Must pass before implementation starts:
- [ ] PRD reviewed and approved by stakeholder (you)
- [ ] PLAN.md updated with all debate fixes
- [ ] Project directory structure created
- [ ] All 10 archive skills confirmed present and restorable

### Must pass before v1.0 release:
- [ ] All 7 evolution-loop skills pass skill-tester with score >= 80
- [ ] Decision matrix 180-cell test: 0 uncovered cells
- [ ] F1-F5 integration tests pass (zero candidates, all fail test, downstream break, FS error, infinite loop)
- [ ] R1-R5 rollback tests pass (immediate regression, module regression, file integrity, downstream, timeout)
- [ ] security_audit module correctly flags malicious candidate fixture
- [ ] skill_name sanitization correctly rejects all 15+ invalid patterns
- [ ] Atomic lock test: 10 concurrent processes, 0 double-acquisitions
- [ ] Rate limiter test: 30 calls in 60s, exactly 20 succeed
- [ ] evolution_log.jsonl: 1000 appends, 0 schema violations

---

## 9. Stakeholder Questions (pending your input)

1. **GitHub repo name**: What should the new repo be called? Suggested: `skill-evolution-loop`
2. **GitHub org/account**: Which GitHub account should own the repo?
3. **Archive trust model**: Do you want to require SHA-256 verification for ALL archive skills (more secure, more setup), or only for skills restored during evolution (lighter weight)?
4. **Human review SLA**: For D4/D5/D8/D11 (flagged for human review), what's the maximum acceptable wait before the system auto-rejects the candidate? Default: 7 days.

---

## Appendix A: Debate Report Summary

Full report at `DEBATE_REPORT.md`. Summary:

| Agent | Verdict | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| Technical Director (P9) | APPROVE WITH CHANGES | 4 | 4 | 2 | 0 |
| Security Engineer | UNSAFE | 2 | 3 | 3 | 1 |
| QA Lead | NEEDS ADDITIONAL SPECIFICATION | 6 | 9 | 9 | 0 |

All 9 Critical findings resolved in this PRD (§4, D1-D9). 16 High findings resolved or tracked for v1.1.

## Appendix B: Key Thresholds Summary

| Parameter | Value | Rationale |
|---|---|---|
| T1 trigger | overall < 40 | Critical failure — immediate auto-trigger |
| T2 trigger | 40 <= overall < 60 | Degraded — auto-trigger with notification |
| T3 trigger | >= 3 modules < 50 | Systemic failure |
| T4 trigger | any module < 30 | Single-module catastrophic |
| T5 trigger | score drop >= 15 | Regression/bit-rot |
| D1 auto-replace | old < 40, candidate >= 75, delta >= +35 | Broken skill, clearly better candidate |
| D2 auto-replace | old < 50, candidate >= 80, delta >= +30 | Borderline skill, strong candidate |
| D3 auto-replace | old < 60, candidate >= 80, delta >= +20 | Degraded skill, good candidate + notification |
| R1 revert | new < old (any amount) | Never accept regression |
| R4 revert | any dependent fails within 24h | Cascading failure prevention |
| Debounce | 3600s per skill+trigger combo | Prevent thrashing |
| Loop timeout | 900s total | Accommodates 3-candidate worst case |
| Lock TTL | 60s | Prevents stale lock accumulation |
| Backup retention | 50 per skill, 90-day eviction | Balance safety vs disk |
| Max concurrent loops | 3 | Prevents API rate limit exhaustion |
| WebSearch rate limit | 20/min, 200/hr | Prevents API abuse |
| LLM test runs per candidate | 3 | Enables 95% CI computation |
| Hysteresis margin | 5 points above threshold | Prevents boundary oscillation |
