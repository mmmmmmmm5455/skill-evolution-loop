---
name: evolution-rollback
description: Executes skill replacement with backup, SHA-256 verification, atomic swap, cascade testing, and auto-revert capability.
type: skill
tools:
  - Bash
  - Read
  - Write
dependencies: []
evolution: true
---

## Description

The final phase of the evolution loop. Performs the actual skill replacement: backup the original with SHA-256 verification, atomically swap in the candidate, run immediate cascade tests on dependents, and auto-revert if any regression is detected.

## Instructions

### Step 1: Pre-Flight Checks

Verify:
- Candidate sandbox exists at `{sandbox_path}`
- Original skill exists at `.claude/skills/{skill_name}/`
- Archive directory `.claude/skills/.archive/` exists (create if not)
- Lock directory `.claude/skills/.locks/` exists (create if not)
- Sufficient disk space: at least 2x original skill size + 10MB buffer

If any check fails → abort, return `status: "preflight_failed"`.

### Step 2: Backup Original

```
backup_path = .claude/skills/.archive/{skill_name}__{ISO8601_basictime}/
```

Copy original skill directory recursively to backup_path.

Compute SHA-256 for every file in backup. Write `backup_manifest.json`:
```json
{
  "skill_name": "string",
  "backup_timestamp": "ISO8601",
  "original_path": ".claude/skills/{skill_name}/",
  "files": {
    "skill.md": "sha256_hash",
    "...": "sha256_hash"
  },
  "pre_replace_score": 0.0,
  "candidate_name": "string",
  "candidate_source": "string"
}
```

Re-read all backup files. Verify checksums match manifest. If mismatch → abort, do NOT proceed to swap.

### Step 3: Acquire Lock

Use atomic mkdir lock:
```
.claude/skills/.locks/{skill_name}.lock/
```

If lock acquisition fails → wait up to 60s (poll every 5s). If still fails → abort, return `status: "lock_timeout"`.

### Step 4: Atomic Swap

Move candidate from sandbox to skill path:
```
mv .claude/skills/.sandbox/{candidate_dir}/ .claude/skills/{skill_name}/
```

`mv` within same filesystem is atomic (inode rename). If across filesystems → copy then delete, with rollback on failure.

### Step 5: Release Lock

```
rmdir .claude/skills/.locks/{skill_name}.lock/
```

### Step 6: Immediate Cascade Test (R4a)

Identify top-3 dependents of replaced skill (skills listing this skill in their dependencies). Run skill-tester on each dependent.

If any dependent fails (score drops or overall < 50):
→ Trigger **R4a auto-revert** immediately
→ Log `event: "revert"`, `reason: "R4a_immediate_cascade_failure"`

### Step 7: Post-Replace Smoke Test

Run skill-tester on the newly installed skill (1 run, not 3 — speed priority over CI precision).

Compare:
- **R1:** new_score < old_score (any amount) → auto-revert
- **R2:** any module that passed in the BEST run in last 7 days now fails → auto-revert
- **R3:** SHA-256 of any installed file doesn't match expected → auto-revert
- **R5:** smoke test exceeds 300s → auto-revert

### Step 8: Auto-Revert Procedure (if R1-R5 triggered)

```
1. ACQUIRE lock (may already hold from Step 3)
2. MOVE current (bad replacement) → .archive/{skill_name}__reverted_{ISO8601}/
3. RESTORE from backup: cp -r {backup_path} → .claude/skills/{skill_name}/
4. VERIFY: sha256sum -c backup_manifest.json
5. RE-TEST: skill-tester on restored skill (1 run)
6. CHECK: restored score within ±3 of pre-replacement score
7. If check fails → CRITICAL: last known-good backup may be corrupted
   → Write SHARED_TASKS.json priority: "critical"
   → Try next-newest backup
8. RELEASE lock
9. LOG: evolution_log.jsonl with event: "revert", reason code R1-R5
10. NOTIFY: SHARED_TASKS.json priority: "high", type: "evolution_revert"
```

### Step 9: Cleanup on Success

If no revert triggered:
- Remove sandbox directory
- Log `event: "replace"`, `status: "success"`
- Log `event: "post_validate"`, `status: "stable"`
- Update `evolution_state.json`: clear debounce, store new baseline score

### Step 10: Output

```json
{
  "status": "replaced|reverted|preflight_failed|lock_timeout",
  "skill_name": "string",
  "backup_path": "string",
  "new_score": 0.0,
  "old_score": 0.0,
  "cascade_test_results": {
    "dependents_tested": 0,
    "dependents_failed": 0,
    "failed_dependents": []
  },
  "revert_triggered": false,
  "revert_reason": "R1|R2|R3|R4a|R4b|R5|null",
  "revert_successful": false,
  "sha256_verified": true
}
```

### Step 11: Passive R4b Registration

Register the replacement timestamp for R4b (24h passive downstream detection). Write to `evolution_state.json`:
```json
{
  "last_replacement_ts": "ISO8601",
  "replaced_skill": "string",
  "r4b_window_end": "ISO8601 + 24h (or 1h for core skills with >=5 dependents)"
}
```

### Safety Guarantees

- Original skill NEVER deleted before SHA-256 verified backup exists
- Lock prevents concurrent modifications to same skill
- Cascade test catches downstream breaks within minutes (not hours)
- Auto-revert restores exact pre-replacement state
- All file operations logged with checksums for audit
