#!/usr/bin/env python3
"""evolution_loop.py — 5-step Skill Evolution Closed Loop

Connects: skill-tester → skill-discovery → skill-manager → re-test → decision

Usage:
    python evolution_loop.py --skill <name> [--threshold 60] [--dry-run]
    python evolution_loop.py --batch skills/*/SKILL.md
    python evolution_loop.py --report

Architecture:
    [1] skill-tester tests skill → test_report.json (score 0-100)
    [2] skill-discovery finds alternatives (local archive, OpenSpace, GitHub)
    [3] skill-manager installs candidates
    [4] skill-tester re-tests new skill → new_test_report.json
    [5] Decision matrix → AUTO_REPLACE / FLAG_FOR_REVIEW / KEEP_ORIGINAL / REPORT_GAP
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parent
SKILLS_DIR = Path.home() / ".claude" / "skills"
ARCHIVE_DIR = Path.home() / ".claude" / "skills-archive"
BUS_DIR = Path.home() / ".claude" / "bus"
DECISION_LOG = PROJECT_DIR / "decisions.jsonl"


def main():
    parser = argparse.ArgumentParser(description="Skill Evolution Closed Loop")
    parser.add_argument("--skill", help="Skill name to evaluate")
    parser.add_argument("--threshold", type=int, default=60, help="Score threshold (default: 60)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without installing")
    parser.add_argument("--batch", help="Glob pattern for batch evaluation")
    parser.add_argument("--report", action="store_true", help="Print decision log summary")
    args = parser.parse_args()

    if args.report:
        print_report()
        return

    if args.batch:
        import glob
        for skill_md in glob.glob(os.path.expanduser(args.batch)):
            skill_name = Path(skill_md).parent.name if Path(skill_md).parent.name != "skills" else Path(skill_md).stem
            run_loop(skill_name, args.threshold, args.dry_run)
        return

    if not args.skill:
        parser.error("--skill or --batch or --report required")

    result = run_loop(args.skill, args.threshold, args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_loop(skill_name: str, threshold: int, dry_run: bool) -> dict:
    """Execute the 5-step evolution loop for a single skill."""
    orch_id = f"EVO-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    result = {
        "orchestration_id": orch_id,
        "skill": skill_name,
        "threshold": threshold,
        "dry_run": dry_run,
        "steps": {},
        "decision": None,
    }

    # ── Step 1: Test current skill ─────────────────────────────────────────
    step1 = step_test(skill_name)
    result["steps"]["1_test"] = step1
    old_score = step1.get("score", 0)

    if old_score >= threshold:
        result["decision"] = {
            "action": "KEEP_CURRENT",
            "reason": f"Score {old_score} >= threshold {threshold}",
        }
        log_decision(result)
        return result

    # ── Step 2: Discover alternatives ──────────────────────────────────────
    step2 = step_discover(skill_name)
    result["steps"]["2_discover"] = step2
    candidates = step2.get("candidates", [])

    if not candidates:
        result["decision"] = {
            "action": "REPORT_GAP",
            "reason": f"No alternatives found for '{skill_name}'",
        }
        log_decision(result)
        return result

    # ── Step 3: Install best candidate ─────────────────────────────────────
    best = candidates[0]
    if dry_run:
        step3 = {"status": "dry_run", "would_install": best}
    else:
        step3 = step_install(best)
    result["steps"]["3_install"] = step3

    if step3.get("status") not in ("installed", "dry_run"):
        result["decision"] = {
            "action": "KEEP_ORIGINAL",
            "reason": f"Install failed: {step3.get('error', 'unknown')}",
        }
        log_decision(result)
        return result

    # ── Step 4: Re-test new skill ──────────────────────────────────────────
    new_skill = best.get("name", f"{skill_name}-alt")
    step4 = step_test(new_skill)
    result["steps"]["4_retest"] = step4
    new_score = step4.get("score", 0)

    # ── Step 5: Decision matrix ────────────────────────────────────────────
    decision = decide(old_score, new_score, threshold)
    result["decision"] = decision

    log_decision(result)
    return result


def step_test(skill_name: str) -> dict:
    """Step 1/4: Run skill-tester against a skill.

    Writes test input to bus/ and returns placeholder.
    In production, the agent-mesh A0 coordinator reads this and dispatches
    the actual skill-tester agent.
    """
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    exists = skill_path.exists()

    input_file = BUS_DIR / f"evo_test_{skill_name}.json"
    input_data = {
        "skill": skill_name,
        "skill_path": str(skill_path),
        "exists": exists,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    input_file.parent.mkdir(parents=True, exist_ok=True)
    input_file.write_text(json.dumps(input_data, indent=2, ensure_ascii=False))

    if not exists:
        return {"status": "missing", "score": 0, "error": f"Skill not found: {skill_path}"}

    # Placeholder: real score comes from skill-tester agent execution
    return {
        "status": "test_input_written",
        "score": _estimate_score(skill_path),
        "input_file": str(input_file),
        "note": "Real score requires skill-tester agent execution via agent-mesh",
    }


def step_discover(skill_name: str) -> dict:
    """Step 2: Search for alternative skills.

    Searches: local skills-archive/, OpenSpace cloud, GitHub topics.
    """
    candidates = []

    # Search 1: Local archive
    if ARCHIVE_DIR.exists():
        for skill_dir in ARCHIVE_DIR.iterdir():
            if skill_dir.is_dir() and skill_name.lower() in skill_dir.name.lower():
                md = skill_dir / "SKILL.md"
                if md.exists():
                    candidates.append({
                        "name": skill_dir.name,
                        "source": "local-archive",
                        "path": str(md),
                    })

    # Search 2: Active skills with similar names
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name == skill_name:
            continue
        md = skill_dir / "SKILL.md"
        if md.exists() and _name_similarity(skill_name, skill_dir.name) > 0.5:
            candidates.append({
                "name": skill_dir.name,
                "source": "local-skills",
                "path": str(md),
            })

    # Search 3: OpenSpace registry (placeholder — requires API key)
    openspace_candidates = _search_openspace(skill_name)
    candidates.extend(openspace_candidates)

    # Sort by relevance
    candidates.sort(key=lambda c: _name_similarity(skill_name, c["name"]), reverse=True)

    return {
        "status": "complete",
        "candidates": candidates[:5],
        "search_sources": ["local-archive", "local-skills", "openspace"],
    }


def step_install(candidate: dict) -> dict:
    """Step 3: Install a candidate skill via skill-manager."""
    source = candidate.get("source", "unknown")
    name = candidate.get("name", "unknown")

    if source == "local-archive":
        # Copy from archive to active skills
        src = ARCHIVE_DIR / name
        dst = SKILLS_DIR / name
        if src.exists() and not dst.exists():
            import shutil
            shutil.copytree(str(src), str(dst))
            return {"status": "installed", "name": name, "source": source, "path": str(dst)}

    if source == "local-skills":
        return {"status": "already_installed", "name": name, "note": "Skill already in active skills"}

    # OpenSpace candidates: would need openspace CLI
    return {
        "status": "pending_manual",
        "name": name,
        "source": source,
        "note": "Install requires openspace CLI or manual download",
    }


def decide(old_score: int, new_score: int, threshold: int) -> dict:
    """Step 5: Decision matrix.

    Rules:
        new_score >= old_score + 10  → AUTO_REPLACE
        old_score <= new_score < old_score + 10 → FLAG_FOR_REVIEW
        new_score < old_score → KEEP_ORIGINAL
    """
    if new_score >= old_score + 10:
        return {"action": "AUTO_REPLACE", "old_score": old_score, "new_score": new_score,
                "delta": new_score - old_score, "reason": f"Significant improvement (+{new_score - old_score})"}
    elif new_score >= old_score:
        return {"action": "FLAG_FOR_REVIEW", "old_score": old_score, "new_score": new_score,
                "delta": new_score - old_score, "reason": f"Marginal improvement (+{new_score - old_score}), needs human review"}
    else:
        return {"action": "KEEP_ORIGINAL", "old_score": old_score, "new_score": new_score,
                "delta": new_score - old_score, "reason": f"New skill scores lower ({new_score} < {old_score})"}


def log_decision(result: dict) -> None:
    """Append decision to JSONL log."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "orchestration_id": result["orchestration_id"],
        "skill": result["skill"],
        "decision": result["decision"],
    }
    with open(DECISION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def print_report() -> None:
    """Print decision log summary."""
    if not DECISION_LOG.exists():
        print("No decisions logged yet.")
        return

    decisions = []
    with open(DECISION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                decisions.append(json.loads(line))

    actions = {}
    for d in decisions:
        action = d.get("decision", {}).get("action", "UNKNOWN")
        actions[action] = actions.get(action, 0) + 1

    print(f"Total decisions: {len(decisions)}")
    for action, count in sorted(actions.items()):
        print(f"  {action}: {count}")
    print(f"\nLast 5:")
    for d in decisions[-5:]:
        dec = d.get("decision", {})
        old_s = dec.get('old_score', '?')
        new_s = dec.get('new_score', '?')
        old_str = f"{old_s:3d}" if isinstance(old_s, int) else f"{str(old_s):>3s}"
        new_str = f"{new_s:3d}" if isinstance(new_s, int) else f"{str(new_s):>3s}"
        print(f"  {d['ts'][:19]} | {d['skill']:20s} | {dec.get('action', '?'):20s} | {old_str} → {new_str}")


def _estimate_score(skill_path: Path) -> int:
    """Estimate skill quality from SKILL.md structure. Placeholder for real tester."""
    try:
        content = skill_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0

    score = 50  # baseline
    if "## " in content:
        score += 5  # has sections
    if "```" in content:
        score += 5  # has code examples
    if "description:" in content.lower():
        score += 5  # has description
    if "---" in content:
        score += 5  # has frontmatter
    if len(content) > 500:
        score += 5  # substantial
    if len(content) > 2000:
        score += 5  # comprehensive
    return min(score, 95)


def _name_similarity(a: str, b: str) -> float:
    """Simple token-overlap similarity between two names."""
    tokens_a = set(a.lower().replace("-", " ").replace("_", " ").split())
    tokens_b = set(b.lower().replace("-", " ").replace("_", " ").split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / max(len(tokens_a), len(tokens_b))


def _search_openspace(skill_name: str) -> list[dict]:
    """Search OpenSpace for matching skills. Requires openspace CLI."""
    candidates = []
    openspace_cmd = None

    for cmd in ["openspace", "python -m openspace"]:
        import shutil
        if shutil.which(cmd.split()[0]):
            openspace_cmd = cmd
            break

    if not openspace_cmd:
        return candidates

    try:
        import subprocess
        result = subprocess.run(
            f"{openspace_cmd} search {skill_name} --limit 3",
            shell=True, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                name = line.strip()
                if name and name != skill_name:
                    candidates.append({
                        "name": name,
                        "source": "openspace",
                        "path": f"openspace:{name}",
                    })
    except Exception:
        pass

    return candidates


if __name__ == "__main__":
    main()
