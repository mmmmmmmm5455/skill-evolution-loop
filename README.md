# Skill Evolution Loop

Closed-loop self-healing system for Claude Code skills. When `skill-tester` detects a broken skill, the evolution loop automatically searches for alternatives, installs candidates in isolated sandboxes, tests them, and makes quantified replace-or-keep decisions.

## Architecture

```
skill-tester (score < threshold)
  → evolution-trigger (validate input, evaluate T1-T5)
  → evolution-search (4 sources, 6-criterion ranking, rate-limited)
  → evolution-install (tiered sandbox, dependency resolution, SHA-256 verify)
  → evolution-test (7 modules, 3 runs per candidate, 95% CI)
  → evolution-decide (14-row matrix, hysteresis, tie-breaking)
  → evolution-rollback (backup, atomic swap, cascade test, auto-revert)
  → evolution_log.jsonl (append-only audit trail)
```

## Design Principles

1. **AI handles semantics, code handles computation** — deterministic ops in Python libs
2. **Skills are composable** — 7 narrow skills, not 1 monolithic skill
3. **Automation must self-audit** — built-in quality gates at every phase
4. **Conservative by default** — auto-replace only when delta is unambiguous

## Quick Start

```bash
# Restore required skills from archive
for skill in ccgs-skill-test ccgs-security-audit ccgs-test-helpers os-sandbox-file-discovery-and-validation; do
  cp -r skills-archive/$skill ~/.claude/skills/$skill/
done

# Run evolution loop on a skill
skill-tester --target skills/my-skill/ --output skills/my-skill/test_output.json
evolution-loop --input skills/my-skill/test_output.json
```

## Project Structure

```
├── PRD.md                   # Product requirements
├── PLAN.md                  # Architecture spec v2.0
├── SKILL_MANIFEST.md        # Required skills inventory
├── DEBATE_REPORT.md         # 3-agent design debate
├── src/
│   ├── skills/              # 7 evolution-loop skill definitions
│   ├── schemas/             # 4 JSON schemas
│   ├── config/              # thresholds, blacklist, security patterns
│   └── lib/                 # sanitize, lock, rate_limiter, log_writer
├── tests/
│   ├── fixtures/            # Test data (skills, candidates, scores)
│   ├── test_matrix.py       # 180-cell decision matrix test
│   └── test_sanitize.py     # skill_name sanitization test
└── logs/                    # Runtime logs (gitignored)
```

## Quality Gates

- skill-tester score >= 80 on all 7 evolution-loop skills
- Decision matrix: 180/180 cells covered
- Failure modes F1-F5: integration tested
- Rollback triggers R1-R5: tested with compressed time windows
- evolution_log.jsonl: 100% schema-valid

## Key Thresholds

| Parameter | Value |
|---|---|
| Auto-replace trigger | D1: old<40, candidate>=75, delta>=35 |
| Standard auto-replace | D3: old<60, candidate>=80, delta>=20 |
| Human review SLA | 3 days, auto-reject on expiry |
| LLM runs per candidate | 3 (for 95% CI) |
| Hysteresis margin | 5 points above threshold |
| Max concurrent loops | 3 |
| Loop timeout | 900s |
| Backup retention | 50 per skill, 90-day eviction |

## Decision Matrix (14 rows, full coverage)

| Row | Old Score | Candidate Score | Delta | Action |
|---|---|---|---|---|
| D1 | <40 | >=75 | >=+35 | Auto-replace |
| D2 | <50 | >=80 | >=+30 | Auto-replace |
| D3 | <60 | >=80 | >=+20 | Auto-replace + notify |
| D4 | <60 | 70-79 | >=+10 | Human review |
| D5 | <60 | 60-69 | >=+5 | Human review (marginal) |
| D6-D7 | <60 | varies | varies | Keep original |
| D8 | 60-75 | >=85 | >=+10 | Human review |
| D9-D10 | 60-75 | varies | varies | Keep original |
| D11 | >=76 | >=90 | >=+14 | Human review |
| D12 | >=76 | <90 or <+14 | — | Keep original |
| D13 | any | <50 | — | Reject |
| D14 | any | any | any | Catch-all discard |

## License

MIT
