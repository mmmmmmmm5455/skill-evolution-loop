---
name: evolution-decide
description: Evaluates the 14-row decision matrix against old skill score and candidate test results. Produces quantified replace/keep/review decision.
type: skill
tools:
  - Read
  - Write
dependencies: []
evolution: true
---

## Description

Takes old skill score and candidate test results (with CI lower bounds). Evaluates the 14-row decision matrix top-down, first match wins. Applies tie-breaking for multiple candidates. Routes human-review decisions to SHARED_TASKS.json.

## Instructions

### Step 1: Read Inputs

From `test_output.json` (original skill):
- `overall_score` as old_score

From `search_results.json` (candidates):
- Each candidate's `ci_lower` as candidate_score
- Each candidate's `hysteresis_applied_score`

### Step 2: Prepare Candidates

Sort passing candidates by `ci_lower` descending. Only candidates with `passed_min_bar: true` are evaluated.

### Step 3: Evaluate Decision Matrix

For each candidate, evaluate rows D1-D14 in order. Within each row, check ALL conditions. First row where ALL conditions match → select that action for this candidate.

**D1:** `old_score < 40 AND candidate_score >= 75 AND delta >= 35`
→ Action: **auto_replace**
Rationale: Original is critically broken (T1). Candidate is clearly superior.

**D2:** `old_score < 50 AND candidate_score >= 80 AND delta >= 30`
→ Action: **auto_replace**
Rationale: Original is borderline broken. Strong candidate, large improvement.

**D3:** `old_score < 60 AND candidate_score >= 80 AND delta >= 20`
→ Action: **auto_replace_notify**
Rationale: Degraded original, clearly better candidate. Auto-replace with notification.

**D4:** `old_score < 60 AND candidate_score >= 70 AND candidate_score <= 79 AND delta >= 10`
→ Action: **human_review**
Rationale: Degraded original, decent candidate, moderate improvement. Human decides.

**D5:** `old_score < 60 AND candidate_score >= 60 AND candidate_score <= 69 AND delta >= 5`
→ Action: **human_review_marginal**
Rationale: Marginal improvement. High uncertainty. Human must validate.

**D6:** `old_score < 60 AND candidate_score >= 70 AND delta < 10`
→ Action: **keep_original**
Rationale: Candidate is ok but improvement too small to justify risk.

**D7:** `old_score < 60 AND candidate_score < 60`
→ Action: **keep_original**
Rationale: Candidate is also bad. No improvement.

**D8:** `old_score >= 60 AND old_score <= 75 AND candidate_score >= 85 AND delta >= 10`
→ Action: **human_review**
Rationale: Original is decent. Candidate is excellent. Worth human attention.

**D9:** `old_score >= 60 AND old_score <= 75 AND candidate_score >= 60 AND candidate_score <= 84`
→ Action: **keep_original**
Rationale: Candidate is comparable or marginally better. Not worth risk.

**D10:** `old_score >= 60 AND old_score <= 75 AND candidate_score < 60`
→ Action: **keep_original**
Rationale: Candidate is worse. Regression prevention.

**D11:** `old_score >= 76 AND candidate_score >= 90 AND delta >= 14`
→ Action: **human_review**
Rationale: Original is good. Candidate must be exceptional to justify review.

**D12:** `old_score >= 76 AND (candidate_score < 90 OR delta < 14)`
→ Action: **keep_original**
Rationale: Original is already good. Insufficient gain to risk.

**D13:** `candidate_score < 50`
→ Action: **reject_candidate**
Rationale: Below minimum quality bar regardless of old score.

**D14:** (no conditions — catch-all)
→ Action: **log_discard**
Rationale: Unclassified input combination. Log for analysis. Keep original.

### Step 4: Apply Hysteresis Margin

Before finalizing any auto_replace or auto_replace_notify action, verify:
- `candidate_score >= threshold + 5` (hysteresis margin from config)

If hysteresis check fails → downgrade D1/D2/D3 to human_review.

Example: D3 threshold is candidate >= 80. With hysteresis, candidate must be >= 85. If candidate ci_lower = 82 → downgrade to D4 (human_review).

### Step 5: Tie-Breaking (Multiple Candidates)

If 2+ candidates qualify for the same action level:

1. **Safety-first:** if candidate A = auto_replace, candidate B = human_review → human_review wins (safer)
2. **Score-based:** highest ci_lower wins
3. **Source trust:** Archive > Installed > GitHub (>=5 stars) > WebSearch
4. **Dependency count:** fewer external deps preferred
5. **Module alignment:** candidate excelling in trigger-causing modules preferred

### Step 6: Execute Decision

**Auto-replace (D1/D2/D3):**
Return action with selected candidate. Proceed to ROLLBACK phase.

**Human review (D4/D5/D8/D11):**
Write to SHARED_TASKS.json:
```json
{
  "task_id": "evo-review-{skill_name}-{timestamp}",
  "type": "skill_evolution_review",
  "priority": "medium",
  "skill": "{skill_name}",
  "old_score": 0.0,
  "candidate_name": "string",
  "candidate_score": 0.0,
  "ci_lower": 0.0,
  "ci_upper": 0.0,
  "delta": 0.0,
  "decision_row": "D4|D5|D8|D11",
  "action_required": "approve_replace | reject_candidate",
  "created": "ISO8601",
  "expires": "ISO8601 + 3 days",
  "status": "pending"
}
```
Return `status: "human_review_queued"`.

**Keep original (D6/D7/D9/D10/D12):**
Log decision, return `status: "keep_original"`.

**Reject candidate (D13):**
Log rejection, return `status: "candidate_rejected"`.

**Catch-all (D14):**
Log unclassified input. Return `status: "unclassified_discard"`. Flag for analysis.

### Step 7: Output

```json
{
  "status": "auto_replace|auto_replace_notify|human_review_queued|keep_original|candidate_rejected|unclassified_discard",
  "decision_row": "D1-D14",
  "selected_candidate": "name or null",
  "old_score": 0.0,
  "new_score": 0.0,
  "delta": 0.0,
  "ci_lower": 0.0,
  "tie_breaker_applied": false,
  "hysteresis_downgraded": false
}
```
