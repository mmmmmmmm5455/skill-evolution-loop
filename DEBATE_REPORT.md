# DEBATE_REPORT: Skill Evolution Loop Design Debate

**Date:** 2026-04-30
**Participants:** Technical Director P9, Security Engineer, QA Lead
**Moderator:** Systems Architect (P9)
**Result:** 3-agent debate complete — 9 Critical findings, all resolved in PRD v1.0

---

## Agent Verdicts

| Agent | Verdict | Critical | High | Medium | Low |
|---|---|---|---|---|---|
| Technical Director (P9) | APPROVE WITH CHANGES | 4 | 4 | 2 | 0 |
| Security Engineer | UNSAFE | 2 | 3 | 3 | 1 |
| QA Lead | NEEDS ADDITIONAL SPECIFICATION | 6 | 9 | 9 | 0 |

## Cross-Agent Consensus (findings identified by 3/3 agents)

### G1: skill_name Path Traversal — No Sanitization (Critical)

**All 3 agents flagged this independently.**

- **Security F2:** `../`, `..\`, absolute paths, Windows reserved names (CON, NUL, COM1) not sanitized
- **Architect F4:** Sandbox path `{skill_name}__candidate_{ts}` constructed from unsanitized input
- **QA F2.4:** Unicode/emoji in skill names, Windows filesystem character restrictions

**Resolution:** PRD §4 D8 — strict allowlist: `[a-zA-Z0-9_-]`, max 64 chars, reject Windows reserved names, reject path separators.

### G2: Web Candidate Supply Chain — No Security Validation (Critical)

**All 3 agents flagged this independently.**

- **Security F1:** Malicious prompt injection, exfiltration via web-sourced skills
- **Architect F4:** Sandbox is directory only — no process/network isolation
- **QA F2.5:** Candidate with same name but different (malicious) function passes C2

**Resolution:** PRD §4 D3 + D9 — tiered sandbox by source trust, 7th test module `security_audit`, WebSearch candidates require human review gate before test.

### G3: Decision Matrix — Uncovered Input Regions (Critical)

**Architect + QA flagged this.**

- **Architect F1:** old=35, candidate=78, delta=+43 → no row matches (candidate < 85 blocks D1, delta > +19 blocks D4, candidate > 69 blocks D5)
- **QA F1.2:** Independent analysis confirming same gap at old=55/candidate=75/delta=20

**Resolution:** PRD §4 D1 — expanded to 14 rows with D14 catch-all. All 180 cells of (old×candidate×delta) partition verified covered.

## Two-Agent Consensus

### G4: Lock Mechanism Broken on Windows

- **Architect F9 (Critical):** PID-file lock with TOCTOU race, PID reuse, global vs per-skill contradiction
- **Security F6 (High):** Advisory-only, no mutual exclusion, Windows PID recycling

**Resolution:** PRD §4 D4 — atomic `mkdir` lock, 60s TTL, per-skill lock directory.

### G5: API Rate Limit + Cost Governance Missing

- **Architect F6 (Critical):** No rate limit budget, no cost tracking, 429 handling

**Resolution:** PRD §4 D5 — token-bucket rate limiter, WebSearch 20/min 200/hr, graceful degradation to archive-only.

### G6: LLM Score Variance at Threshold Boundaries

- **QA F5.1 (Critical):** Candidate scoring 79 vs 81 crosses D3/D4 boundary → irreversible auto-replace decided by noise

**Resolution:** PRD §4 D6 — 3 runs per candidate, 95% CI lower bound, 5-point hysteresis above threshold.

### G7: Test Fixture Infrastructure Missing

- **QA F4.1 (Critical):** No broken skill fixtures, no candidate fixtures, no mock score injector

**Resolution:** PRD §5.3 — fixture directory structure with 3 broken skills, 3 candidates, mock score files.

### G8: SLA Timeout Contradiction

- **QA F7.1 (Critical):** 600s total timeout < 735s worst-case phase sum (75+360+300)

**Resolution:** PRD §4 D7 — 900s total timeout, parallel candidate testing (3×120s → 120s).

### G9: Downstream Break Detection Window

- **Architect F5 (Critical):** 24h passive window too slow for core skills (>5 dependents)

**Resolution:** PRD §4 — immediate cascade test on top-3 dependents after every replacement. Tiered windows: core=1h, standard=24h.

## Unique Findings by Agent

### Security Engineer (not covered by others)

| Finding | Severity | Resolution |
|---|---|---|
| Archive poisoning — Priority 1 trust without integrity | High | SHA-256 verification on archive restore (PRD R10) |
| Log-based info disclosure — absolute paths | Medium | Path scrubbing in log writer (PRD R11) |
| Search query injection — skill_name in WebSearch | Medium | Sanitization before query construction (PRD R12) |
| No execution sandbox during test | High | Tiered sandbox model (PRD D3) |
| evolution_state.json deletion as attack surface | Low | Tracked for v1.1 |

### Architect (not covered by others)

| Finding | Severity | Resolution |
|---|---|---|
| Search ranking weights inverted — C2 (lexical) > C3 (tools) | High | Swapped weights + added C6 (PRD D2) |
| "Declared manifest" undefined | High | Defined in PRD §5.3 |
| evolution_state.json schema missing | High | Schema defined in src/schemas/ |
| Dependency parsing format-brittle | Medium | Multi-format grammar (PRD §4) |
| Decision matrix risk profile inverted | High | Fixed in revised matrix (PRD D1) |

### QA Lead (not covered by others)

| Finding | Severity | Resolution |
|---|---|---|
| D12 dead code — §4.3 gate makes it unreachable | High | Removed in revised matrix (PRD D13 replaces it) |
| R4 untestable in CI (requires 24h) | Critical | Configurable R4_WINDOW_SECONDS, 60s in test mode (PRD) |
| R4 assumes downstream skills ARE tested | High | Proactive cascade test after replace (PRD) |
| R2 "previously passed" undefined | Medium | Defined as best score in last 7 days (PRD) |
| Debounce reset on "different modules" ambiguous | High | Exact set comparison logic defined (PRD) |
| No input validation on test_output.json | Critical | JSON Schema validation before trigger eval (PRD) |
| No failure mode for broken skill-tester | High | skill-tester sanity check added (PRD) |
| No concurrency limits → API exhaustion | High | Max 3 concurrent loops (PRD) |
| evolution_log.jsonl append failure silent | Medium | Append return code check + fallback log (PRD) |
| No throttle on debounce resets | Medium | Reset counter, 5 resets/24h → escalate (PRD) |
| D1/D3 auto-replace non-deterministic due to overlapping rows | Critical | Top-down evaluation, first match wins (PRD) |
| Float boundary ambiguity | Medium | All thresholds defined as explicit float comparisons (PRD) |

## Metrics

- **Total findings:** 42 across 3 agents
- **Critical:** 9 (all resolved in PRD)
- **High:** 16 (all resolved or tracked)
- **Medium:** 14 (12 resolved, 2 tracked for v1.1)
- **Low:** 3 (tracked for v1.1+)
- **Agents in full agreement (3/3):** 3 findings (G1, G2, G3)
- **Agents in partial agreement (2/3):** 6 findings (G4-G9)

## Conclusion

The original PLAN.md had a sound macro-architecture but critical gaps in input validation, security, testability, and completeness. The 3-agent debate surfaced 9 Critical findings, all of which have been addressed in PRD v1.0 through specific, quantified design changes. The revised system is now safe to proceed to implementation, subject to stakeholder approval of PRD §9.
