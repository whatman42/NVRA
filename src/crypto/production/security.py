"""Secret-leak scanning helpers for packages, logs, and audit trails."""

from __future__ import annotations

import re
from pathlib import Path

# Patterns that must never appear in packaged artifacts / logs
_SECRET_PATTERNS = [
    re.compile(r"api[_-]?secret\s*[:=]\s*['\"]?[A-Za-z0-9+/=_\-]{16,}", re.I),
    re.compile(r"api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9+/=_\-]{12,}", re.I),
    re.compile(r"bot[_-]?token\s*[:=]\s*['\"]?\d{8,}:[A-Za-z0-9_\-]{20,}", re.I),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"(?:password|secret_pin|pin_secret)\s*[:=]\s*['\"]\d{6}['\"]", re.I),
]


def scan_text_for_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


def scan_file_for_secrets(path: Path) -> list[str]:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text_for_secrets(data)


def scan_tree_for_secrets(
    root: Path, *, suffixes: tuple[str, ...] = (".py", ".md", ".json", ".txt", ".iss", ".spec")
) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    if not root.is_dir():
        return findings
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in suffixes:
            continue
        if "test" in p.parts and "secret" in p.name:
            continue
        hits = scan_file_for_secrets(p)
        if hits:
            findings[str(p)] = hits
    return findings
