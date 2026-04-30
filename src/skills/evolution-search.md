---
name: evolution-search
description: Searches for candidate skill replacements across 4 sources (archive, installed, WebSearch, GitHub) with rate limiting and 6-criterion ranking.
type: skill
tools:
  - Glob
  - Grep
  - Read
  - Bash
  - WebSearch
  - WebFetch
dependencies:
  - find-skills
evolution: true
---

## Description

Given a failing skill, searches across 4 priority-ordered sources for candidate replacements. Applies 6-criterion matching and ranking. Respects rate limits. Returns top 3 candidates in `search_results.json`.

## Instructions

### Step 1: Sanitize Input

Run skill_name through sanitization:
- Reject if contains: `/`, `\`, `..`, `:`, `<`, `>`, `"`, `|`, `?`, `*`
- Reject if matches Windows reserved names (case-insensitive): CON, PRN, AUX, NUL, COM1-9, LPT1-9
- Reject if length > 64 or empty
- Allowed: `^[a-zA-Z0-9_-]+$`

If sanitization fails → log, return `candidate_count: 0`, reason: `name_sanitization_failed`.

### Step 2: Extract Skill Function

Read original skill file at `.claude/skills/{skill_name}/skill.md`. Extract:
- `skill_function`: from `description` field or first heading
- `declared_tools`: from `tools:` frontmatter list
- `tags`: from `tags:` frontmatter (if present)

If original skill file unreadable → use skill_name as function, empty tools list.

### Step 3: Search Priority 1 — Local Archive

Search `skills-archive/` using Glob for skill names with Jaro-Winkler >= 0.70 to original. Grep within matching skills for functional overlap (shared verbs/nouns). Timeout: 10s.

### Step 4: Search Priority 2 — Installed Skills

Search `.claude/skills/` for skills with similar name patterns or tool overlap. Timeout: 5s.

### Step 5: Search Priority 3 — WebSearch

Check rate limiter: `can_websearch()` must return true.

Query 1: `"claude code skill {skill_function}"`
Query 2: `"{skill_function} skill claude code .md"`

Timeout: 30s per query. Rate limit hit → fall back to archive-only, log `event: "rate_limited"`.

Extract candidate names and source URLs from search results.

### Step 6: Search Priority 4 — GitHub WebSearch

Check rate limiter: `can_github()` must return true.

Query: `site:github.com claude code skill {skill_function}`

Timeout: 30s. Rate limit hit → skip.

### Step 7: Candidate Matching

For each candidate found, compute 5 criteria. Candidate must satisfy >= 3 to enter ranking:

**C1 — Name similarity (weight 0.20):**
`jaro_winkler(skill_name, candidate_name)` >= 0.70 → pass

**C2 — Functional overlap (weight 0.15):**
Candidate description shares >= 1 verb AND >= 1 noun with original skill description → pass

**C3 — Tool footprint match (weight 0.30):**
Count intersection of original.declared_tools and candidate.declared_tools. If intersection / original_count >= 0.50 → pass

**C4 — Source freshness (weight 0.10):**
Archive: modified within 180 days → pass
GitHub: stars >= 5 → pass

**C5 — Dependency discipline (weight 0.05):**
Candidate dependency count <= original dependency count + 3 → pass

**C6 — Failing module coverage (weight 0.20):**
If original failed on M2 (Tool Reference), candidate whose tools list includes >= 80% of original tools gets bonus: 1.0.
If original failed on M5 (Dependency Chain), candidate with 0 missing deps gets bonus: 1.0.
Otherwise: proportional bonus based on overlap with failing modules.

### Step 8: Ranking

```
RANK_SCORE = (C1_pass × 0.20) + (C2_pass × 0.15) + (C3_pass × 0.30)
           + (C4_pass × 0.10) + (C5_pass × 0.05) + (C6_score × 0.20)
```

- RANK_SCORE >= 0.70 → strong candidate
- RANK_SCORE 0.50-0.69 → weak candidate, collect up to 3
- RANK_SCORE < 0.50 → discard

### Step 9: Output

Write `search_results.json`:
```json
{
  "skill_name": "string",
  "trigger_score": 0.0,
  "trigger_id": "T1-T5",
  "failing_modules": ["string"],
  "candidates": [...],
  "candidate_count": 0-3,
  "search_duration_ms": 0,
  "timestamp": "ISO8601",
  "rate_limited_sources": []
}
```

### Step 10: Terminal Conditions

- 0 candidates after all 4 sources exhausted → `candidate_count: 0` (triggers F1)
- 1-3 candidates → proceed to INSTALL phase
