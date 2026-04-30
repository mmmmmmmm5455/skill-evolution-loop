"""
Tests for skill_name sanitization.
Covers: valid names, path traversal, Windows reserved, special chars, length limits.
"""
import sys
sys.path.insert(0, "src/lib")
from sanitize import sanitize_skill_name

VALID_NAMES = [
    "pdf-generator",
    "skill_tester_v2",
    "code-reviewer",
    "abc123",
    "my-skill",
    "x",
    "a" * 64,
]

INVALID_NAMES = [
    ("", "empty"),
    ("   ", "whitespace"),
    ("a" * 65, "too_long"),
    ("skill/name", "path_separator"),
    ("skill\\name", "backslash"),
    ("../escape", "parent_dir"),
    ("..\\escape", "windows_parent"),
    ("skill:name", "colon"),
    ("skill<name", "angle_bracket"),
    ("skill>name", "angle_bracket_close"),
    ('skill"name', "double_quote"),
    ("skill|name", "pipe"),
    ("skill?name", "question_mark"),
    ("skill*name", "asterisk"),
    ("CON", "windows_reserved_con"),
    ("con", "windows_reserved_con_lower"),
    ("NUL", "windows_reserved_nul"),
    ("COM1", "windows_reserved_com1"),
    ("LPT1", "windows_reserved_lpt1"),
    ("PRN", "windows_reserved_prn"),
    ("AUX", "windows_reserved_aux"),
]


def test_valid_names():
    for name in VALID_NAMES:
        is_valid, reason = sanitize_skill_name(name)
        assert is_valid, f"Expected valid: '{name}', got: {reason}"


def test_invalid_names():
    for name, expected_reason in INVALID_NAMES:
        is_valid, reason = sanitize_skill_name(name)
        assert not is_valid, f"Expected invalid: '{name}'"


if __name__ == "__main__":
    test_valid_names()
    test_invalid_names()
    print(f"PASS: {len(VALID_NAMES)} valid names accepted")
    print(f"PASS: {len(INVALID_NAMES)} invalid names rejected")
