"""
Atomic mkdir lock for Skill Evolution Loop.
Uses mkdir atomicity (works on all filesystems, including Windows).
Replaces the broken PID-file approach from PLAN.md v1.0.
"""
import os
import json
import time
from pathlib import Path

def load_config():
    config_path = Path(__file__).parent.parent / "config" / "thresholds.json"
    with open(config_path) as f:
        cfg = json.load(f)
        return cfg["lock"], cfg["timeouts"]

def acquire(skill_name: str, lock_root: str = ".claude/skills/.locks") -> tuple[bool, str]:
    """
    Returns (acquired, reason).
    acquired=True: lock acquired successfully.
    acquired=False: lock contended (another process holds it).
    """
    lock_config, timeout_config = load_config()
    lock_dir = os.path.join(lock_root, f"{skill_name}.lock")

    try:
        os.makedirs(lock_dir, exist_ok=False)
    except FileExistsError:
        if _is_stale(lock_dir, lock_config["ttl_seconds"]):
            _break_stale(lock_dir)
            try:
                os.makedirs(lock_dir, exist_ok=False)
            except FileExistsError:
                return False, "contended_after_stale_break"
        else:
            return False, "contended"

    ts_file = os.path.join(lock_dir, "acquired_at")
    with open(ts_file, "w") as f:
        f.write(str(time.time()))

    return True, "acquired"

def release(skill_name: str, lock_root: str = ".claude/skills/.locks") -> bool:
    lock_dir = os.path.join(lock_root, f"{skill_name}.lock")
    try:
        ts_file = os.path.join(lock_dir, "acquired_at")
        if os.path.exists(ts_file):
            os.remove(ts_file)
        os.rmdir(lock_dir)
        return True
    except OSError:
        return False

def _is_stale(lock_dir: str, ttl_seconds: int) -> bool:
    ts_file = os.path.join(lock_dir, "acquired_at")
    if not os.path.exists(ts_file):
        return True
    try:
        with open(ts_file) as f:
            acquired = float(f.read().strip())
        return (time.time() - acquired) > ttl_seconds
    except (ValueError, OSError):
        return True

def _break_stale(lock_dir: str):
    import shutil
    shutil.rmtree(lock_dir, ignore_errors=True)
