---
name: evolution-install
description: Installs candidate skills to sandbox directories. Dependency resolution, tiered sandbox model, archive integrity verification.
type: skill
tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
dependencies:
  - os-sandbox-file-discovery-and-validation
evolution: true
---

## Description

Installs candidate skills to isolated sandbox directories. Resolves dependencies from archive. Verifies file integrity (SHA-256 for archive sources). Applies tiered sandbox model based on candidate source trust level.

## Instructions

### Step 1: Sanitize Candidate Name

Run candidate.name through sanitization. If invalid → skip candidate, `install_ready: false`, reason: `name_sanitization_failed`.

### Step 2: Determine Sandbox Type

| Source | Sandbox Type | Pre-Test Gate |
|---|---|---|
| archive | filesystem_only | none |
| installed | filesystem_only | none |
| github | filesystem + prompt_scan | security_audit before main test |
| websearch | filesystem + prompt_scan | human_review_required |

### Step 3: Create Sandbox Directory

```
Path: .claude/skills/.sandbox/{skill_name}__candidate_{ISO8601_basictime}/
```

Verify sandbox root `.claude/skills/.sandbox/` exists. Create if not.
Create candidate-specific sandbox dir. If exists → append `_2`, `_3`.

On creation failure (ENOSPC, EACCES) → retry 2x with 10s spacing. If still fails → abort loop, log F4.

### Step 4: Copy Candidate Files

Copy all candidate files to sandbox directory.

Validate:
- File count > 0
- Each file passes UTF-8 encoding check
- Each file < 100KB (reject if larger)
- Frontmatter parses without error
- No symlinks pointing outside sandbox

If validation fails → `install_ready: false`, reason: specific failure.

### Step 5: SHA-256 Verification (Archive Sources)

If candidate.source == "archive":
- Read stored checksum from archive manifest
- Compute SHA-256 of installed files
- Mismatch → disqualify, log `event: "archive_integrity_failure"`

### Step 6: Dependency Resolution

Parse candidate frontmatter for:
- `## Requires` section
- `## Dependencies` section
- YAML `requires:` or `dependencies:` field

For each dependency:
1. SATISFIED: exists in `.claude/skills/` → done
2. UNSATISFIED_ARCHIVE: exists in `skills-archive/` → restore to sandbox
3. UNSATISFIED_EXTERNAL: not found → `install_ready: false`, `missing_deps: [...]`

Max dependency chain depth: 3 levels.
Circular detected → disqualify.
Candidate depends on skill it replaces → disqualify.

### Step 7: Security Pre-Scan (GitHub/WebSearch Sources)

If sandbox_type includes "prompt_scan":
- Scan candidate content against `security_patterns.json`
- Check for: prompt injection patterns, exfiltration URLs, dangerous tool patterns
- If any pattern matches → `install_ready: false`, `security_flag: true`

### Step 8: Set Install Readiness

`install_ready: true` requires ALL of:
- Sanitization passed
- Sandbox directory created
- All files copied and validated
- SHA-256 verified (if archive)
- All dependencies resolved (no UNSATISFIED_EXTERNAL)
- No circular dependencies
- Security scan passed (if applicable)
- NOT (source == websearch AND human_review_required)

### Step 9: Output

Update candidate entry in `search_results.json`:
```json
{
  "install_ready": true/false,
  "sandbox_path": "string",
  "install_error": "reason_if_failed",
  "missing_deps": ["dep1"],
  "security_flag": false,
  "requires_human_review": true/false
}
```
