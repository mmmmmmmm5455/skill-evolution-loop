# SKILL_MANIFEST: Skill Evolution Loop

**Date:** 2026-04-30
**Purpose:** Declare all skills needed to build, test, and operate the Skill Evolution Loop.
**Rule:** Every skill listed must either exist in archive/installed OR have a concrete creation plan.

---

## 1. Archive Skills to Restore (10 skills)

Run before implementation: restore from `skills-archive/` to `~/.claude/skills/`.

| # | Skill Name | Archive Path | Purpose | Priority |
|---|---|---|---|---|
| 1 | `ccgs-skill-test` | `skills-archive/ccgs-skill-test/` | Skill testing framework — used to test evolution-loop skills themselves | **Blocking** |
| 2 | `ccgs-skill-improve` | `skills-archive/ccgs-skill-improve/` | Skill improvement patterns — used to refine candidates | High |
| 3 | `ccgs-security-audit` | `skills-archive/ccgs-security-audit/` | Security scanning patterns — feeds `security_audit` module | **Blocking** |
| 4 | `ccgs-test-helpers` | `skills-archive/ccgs-test-helpers/` | Test utilities — mock score injector, fixture management | **Blocking** |
| 5 | `ccgs-test-setup` | `skills-archive/ccgs-test-setup/` | Test fixture setup — creates broken skill fixtures | High |
| 6 | `sci-skill-evolution` | `skills-archive/sci-skill-evolution/` | Existing evolution skill — study for patterns, avoid reinvention | Medium |
| 7 | `os-sandbox-file-discovery-and-validation` | `skills-archive/os-sandbox-file-discovery-and-validation/` | Sandbox file validation — directory isolation verification | **Blocking** |
| 8 | `ccgs-architecture-decision` | `skills-archive/ccgs-architecture-decision/` | ADR template — for recording architecture decisions | Low |
| 9 | `openviking-skill-creator` | `skills-archive/openviking-skill-creator/` | Skill authoring patterns — for writing new evolution skills | High |
| 10 | `pm-skill-authoring-workflow` | `skills-archive/pm-skill-authoring-workflow/` | PM skill authoring workflow — PRD-to-skill methodology | Medium |

## 2. Installed Skills (already active — 12 skills)

| # | Skill Name | Purpose | Used In Phase |
|---|---|---|---|
| 1 | `caveman` | Terse communication mode | All phases |
| 2 | `pua` | Quality push mode — drives score >= 80 | Phase 6 (Testing) |
| 3 | `brainstorming` | Design ideation | Phase 1 (Design) |
| 4 | `github-helper` | GitHub issue/PR operations | Phase 7 (GitHub) |
| 5 | `github-ops` | GitHub repo creation, push | Phase 7 (GitHub) |
| 6 | `find-skills` | Skill discovery in archive/installed | Phase 2 (Search) |
| 7 | `executing-plans` | Plan execution engine | Phase 5 (Implementation) |
| 8 | `dispatching-parallel-agents` | Multi-agent orchestration | All phases |
| 9 | `code-audit` | Code quality review | Phase 5 (Implementation) |
| 10 | `write-plan` | Plan document generation | Phase 1 (Design) |
| 11 | `simplify` | Code simplification review | Phase 5 (Implementation) |
| 12 | `verification-before-completion` | Pre-completion verification | Phase 6 (Testing) |

## 3. New Skills to Create (7 skills)

These are the core evolution-loop skills. Each must pass skill-tester with score >= 80.

| # | Skill Name | File | Phase | Dependencies |
|---|---|---|---|---|
| 1 | `evolution-loop` | `src/skills/evolution-loop.md` | Orchestrator — coordinates §1-§8 | evolution-trigger, evolution-search, evolution-install, evolution-test, evolution-decide, evolution-rollback |
| 2 | `evolution-trigger` | `src/skills/evolution-trigger.md` | §1 — Reads test_output.json, evaluates T1-T5, debounce check | evolution_log.schema.json, test_output.schema.json |
| 3 | `evolution-search` | `src/skills/evolution-search.md` | §2 — 4-source search, rate limiting, ranking, C1-C6 scoring | find-skills, rate_limiter, search_results.schema.json |
| 4 | `evolution-install` | `src/skills/evolution-install.md` | §3 — Sandbox install, dependency resolution, sanitization | os-sandbox-file-discovery-and-validation, sanitize, lock |
| 5 | `evolution-test` | `src/skills/evolution-test.md` | §4 — 7-module candidate testing, 3-run CI computation | ccgs-skill-test, ccgs-security-audit |
| 6 | `evolution-decide` | `src/skills/evolution-decide.md` | §5 — 14-row decision matrix, tie-breaking, human-review routing | SHARED_TASKS.json |
| 7 | `evolution-rollback` | `src/skills/evolution-rollback.md` | §6 — Backup, swap, post-validate, auto-revert (R1-R5) | SHA-256, backup_manifest.json |

## 4. Support Libraries (4 files)

Not skills — utility code used by skills.

| # | File | Purpose | Language |
|---|---|---|---|
| 1 | `src/lib/sanitize.py` | skill_name sanitization — rejects path traversal, reserved names, special chars | Python |
| 2 | `src/lib/lock.py` | Atomic mkdir lock — 60s TTL, stale detection, per-skill isolation | Python |
| 3 | `src/lib/rate_limiter.py` | Token-bucket rate limiter — WebSearch 20/min, GitHub 50/min | Python |
| 4 | `src/lib/log_writer.py` | JSONL append with schema validation + secret scrubbing | Python |

## 5. Schemas (4 files)

| # | File | Validates |
|---|---|---|
| 1 | `src/schemas/test_output.schema.json` | skill-tester output (input to evolution loop) |
| 2 | `src/schemas/search_results.schema.json` | Search phase output |
| 3 | `src/schemas/evolution_log.schema.json` | Every evolution_log.jsonl line |
| 4 | `src/schemas/evolution_state.schema.json` | Per-skill debounce/block/retry state |

## 6. Configuration (3 files)

| # | File | Content |
|---|---|---|
| 1 | `src/config/thresholds.json` | All numeric thresholds: T1-T5, D1-D14, R1-R5, debounce, lock TTL, rate limits, timeouts |
| 2 | `src/config/evolution_blacklist.json` | Skills permanently excluded from evolution: `["skill_a", "skill_b"]` |
| 3 | `src/config/security_patterns.json` | Prompt injection patterns, exfiltration URL patterns, dangerous tool call patterns |

## 7. Test Fixtures (9 files)

| # | File | Purpose |
|---|---|---|
| 1 | `tests/fixtures/skills/skill_good.md` | Known-good skill — expected score 85+ |
| 2 | `tests/fixtures/skills/skill_bad_yaml.md` | Broken YAML frontmatter — triggers M1 failure |
| 3 | `tests/fixtures/skills/skill_bad_tools.md` | References non-existent tools — triggers M2 failure |
| 4 | `tests/fixtures/skills/skill_bad_deps.md` | Missing dependencies — triggers M5 failure |
| 5 | `tests/fixtures/candidates/candidate_superior.md` | Scores 90+ — triggers D1/D2/D3 auto-replace |
| 6 | `tests/fixtures/candidates/candidate_marginal.md` | Scores 70-79 — triggers D4/D5 human review |
| 7 | `tests/fixtures/candidates/candidate_malicious.md` | Contains prompt injection — must be flagged by security_audit |
| 8 | `tests/fixtures/scores/score_t1.json` | Overall < 40 — triggers T1 |
| 9 | `tests/fixtures/scores/score_edge.json` | Boundary scores for 180-cell decision matrix test |

## 8. Skill Dependency Graph

```
evolution-loop
├── evolution-trigger
│   └── test_output.schema.json
├── evolution-search
│   ├── find-skills (installed)
│   ├── rate_limiter (lib)
│   └── search_results.schema.json
├── evolution-install
│   ├── os-sandbox-file-discovery-and-validation (archive)
│   ├── sanitize (lib)
│   └── lock (lib)
├── evolution-test
│   ├── ccgs-skill-test (archive)
│   └── ccgs-security-audit (archive)
├── evolution-decide
│   ├── SHARED_TASKS.json
│   └── thresholds.json
└── evolution-rollback
    ├── lock (lib)
    └── log_writer (lib)
```

## 9. Restoration Commands

```bash
# Restore blocking skills first
cp -r skills-archive/ccgs-skill-test/ ~/.claude/skills/ccgs-skill-test/
cp -r skills-archive/ccgs-security-audit/ ~/.claude/skills/ccgs-security-audit/
cp -r skills-archive/ccgs-test-helpers/ ~/.claude/skills/ccgs-test-helpers/
cp -r skills-archive/os-sandbox-file-discovery-and-validation/ ~/.claude/skills/os-sandbox-file-discovery-and-validation/

# Restore support skills
cp -r skills-archive/ccgs-skill-improve/ ~/.claude/skills/ccgs-skill-improve/
cp -r skills-archive/ccgs-test-setup/ ~/.claude/skills/ccgs-test-setup/
cp -r skills-archive/openviking-skill-creator/ ~/.claude/skills/openviking-skill-creator/
cp -r skills-archive/sci-skill-evolution/ ~/.claude/skills/sci-skill-evolution/
cp -r skills-archive/ccgs-architecture-decision/ ~/.claude/skills/ccgs-architecture-decision/
cp -r skills-archive/pm-skill-authoring-workflow/ ~/.claude/skills/pm-skill-authoring-workflow/
```

## 10. Verification

```bash
# Check all archive skills exist
for skill in ccgs-skill-test ccgs-security-audit ccgs-test-helpers os-sandbox-file-discovery-and-validation \
            ccgs-skill-improve ccgs-test-setup openviking-skill-creator sci-skill-evolution \
            ccgs-architecture-decision pm-skill-authoring-workflow; do
  test -d "skills-archive/$skill" && echo "OK: $skill" || echo "MISSING: $skill"
done

# Check all installed skills exist
for skill in caveman pua brainstorming github-helper github-ops find-skills \
            executing-plans dispatching-parallel-agents code-audit write-plan simplify \
            verification-before-completion; do
  test -d "$HOME/.claude/skills/$skill" && echo "OK: $skill" || echo "MISSING: $skill"
done
```
