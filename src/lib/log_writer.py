"""
JSONL log writer with schema validation and secret scrubbing.
Append-only. One JSON object per line.
"""
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone

SECRET_PATTERNS = [
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), 'ghp_REDACTED'),
    (re.compile(r'sk-[a-zA-Z0-9]{32,}'), 'sk-REDACTED'),
    (re.compile(r'Bearer [A-Za-z0-9_\-\.]+'), 'Bearer_REDACTED'),
    (re.compile(r'AIza[0-9A-Za-z\-_]{35}'), 'GAPI_REDACTED'),
    (re.compile(r'[a-zA-Z0-9+/]{40,}={0,2}'), 'BASE64_LIKE_REDACTED'),
    (re.compile(r'/home/[a-zA-Z0-9_\-]+/'), '/home/USER/'),
    (re.compile(r'C:\\\\Users\\\\[a-zA-Z0-9_\-]+'), 'C:\\\\Users\\\\USER'),
]

def scrub_secrets(data: dict) -> dict:
    data["secrets_scrubbed"] = True
    serialized = json.dumps(data)
    for pattern, replacement in SECRET_PATTERNS:
        serialized = pattern.sub(replacement, serialized)
    return json.loads(serialized)

def append_log(log_path: str, entry: dict, schema: dict = None) -> bool:
    """
    Append a single JSON line to evolution_log.jsonl.
    - Adds ts if missing
    - Scrubs secrets
    - Validates against schema if provided
    - Returns True on success
    """
    if "ts" not in entry:
        entry["ts"] = datetime.now(timezone.utc).isoformat()

    entry = scrub_secrets(entry)

    if schema:
        try:
            import jsonschema
            jsonschema.validate(entry, schema)
        except ImportError:
            pass
        except Exception:
            return False

    try:
        line = json.dumps(entry, ensure_ascii=False)
        if "\n" in line:
            return False
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except OSError:
        fallback = log_path.replace(".jsonl", "_critical.jsonl")
        try:
            with open(fallback, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": entry["ts"], "event": "log_write_failed", "target": log_path}) + "\n")
        except OSError:
            pass
        return False
