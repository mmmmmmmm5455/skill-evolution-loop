"""
skill_name sanitization for Skill Evolution Loop.
Rejects path traversal, Windows reserved names, and special characters.

Allowed pattern: ^[a-zA-Z0-9_-]+$
Max length: 64 chars
Windows reserved names: CON, PRN, AUX, NUL, COM1-9, LPT1-9
"""
import re
import json
from pathlib import Path

def load_config():
    config_path = Path(__file__).parent.parent / "config" / "thresholds.json"
    with open(config_path) as f:
        return json.load(f)["sanitization"]

def sanitize_skill_name(name: str) -> tuple[bool, str]:
    """
    Returns (is_valid, reason).
    is_valid=True means the name is safe to use in paths and search queries.
    """
    config = load_config()

    if not name or not name.strip():
        return False, "empty_or_whitespace"

    if len(name) > config["max_length"]:
        return False, f"exceeds_max_length_{config['max_length']}"

    if not re.match(config["skill_name_pattern"], name):
        return False, "invalid_characters"

    if name.upper() in config["windows_reserved"]:
        return False, "windows_reserved_name"

    return True, "ok"
