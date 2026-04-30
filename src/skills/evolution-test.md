---
name: evolution-test
description: Tests candidate skills using skill-tester. 7 modules, 3 runs per candidate for 95% confidence interval. Parallel execution.
type: skill
tools:
  - Bash
  - Read
  - Write
dependencies:
  - ccgs-skill-test
  - ccgs-security-audit
evolution: true
---

## Description

Runs skill-tester against sandbox-installed candidates. Executes 3 runs per candidate for LLM score variance handling. Computes 95% confidence intervals. Applies minimum bar gates. Tests candidates in parallel.

## Instructions

### Step 1: Validate Candidate Readiness

Read `search_results.json`. Filter to candidates with `install_ready: true`.

For each ready candidate, read `requires_human_review` flag. If true → skip (human gate not yet passed).

### Step 2: Prepare Test Command

For each candidate:
```
skill-tester \
  --target {sandbox_path} \
  --modules tool_usage,prompt_alignment,output_schema,error_handling,self_description,edge_case_coverage,security_audit \
  --steps 8 \
  --output {sandbox_path}/test_output_candidate_run{N}.json \
  --timeout-per-module 30
```

### Step 3: Run Tests (3 runs per candidate, parallel across candidates)

Run all candidates in parallel (max 3 concurrent). For each candidate, run 3 sequential test executions.

Timeout: 120s per candidate total (all 3 runs). If timeout → mark candidate as `test_timeout`, discard.

Store all 3 run outputs as:
- `{sandbox_path}/test_output_candidate_run1.json`
- `{sandbox_path}/test_output_candidate_run2.json`
- `{sandbox_path}/test_output_candidate_run3.json`

### Step 4: Compute Statistics

For each candidate, across 3 runs:

```
mean_score = (run1 + run2 + run3) / 3
std_dev = sqrt(sum((x - mean)^2) / 3)
ci_margin = 1.96 * (std_dev / sqrt(3))
ci_lower = mean_score - ci_margin
ci_upper = mean_score + ci_margin
```

Log `score_variance` = std_dev^2.

### Step 5: Apply Hysteresis

Candidate score for decision matrix = `ci_lower` (lower bound of 95% CI).

This means: a candidate must be CONSISTENTLY good, not just lucky on one run. The lower bound protects against LLM non-determinism inflating scores.

Hysteresis margin: candidate must be at least 5 points above the decision threshold. E.g., D3 triggers at candidate >= 80. With hysteresis, candidate >= 85 required for auto-replace.

### Step 6: Minimum Bar Gate

Candidate passes if ALL:
- `mean_score >= 50`
- `ci_lower >= 45`
- No single module mean < 30
- `security_audit` mean >= 50
- No security flag raised

Candidates failing minimum bar → `candidate_rejected_pretest`, logged with scores.

### Step 7: Rank Passing Candidates

Sort passing candidates by `ci_lower` descending.

### Step 8: Output

Update `search_results.json` with test results:
```json
{
  "candidates": [
    {
      "name": "string",
      "test_results": {
        "mean_score": 0.0,
        "std_dev": 0.0,
        "ci_lower": 0.0,
        "ci_upper": 0.0,
        "score_variance": 0.0,
        "module_means": {},
        "hysteresis_applied_score": 0.0,
        "passed_min_bar": true,
        "runs_completed": 3
      }
    }
  ]
}
```

### Termination Conditions

- All candidates fail minimum bar → return `status: "all_candidates_failed_test"` (triggers F2)
- At least 1 candidate passes → return `status: "candidates_ready_for_decision"`, proceed to DECIDE phase
