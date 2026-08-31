#!/usr/bin/env python3
"""Secret material scanner — value-based; skips detector-regex definitions."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [".github", "god", "tests", "packaging", "tools", "scripts"]
# also top-level files
TOP_GLOBS = ["*.py", "*.md", "*.txt", "*.yml", "*.yaml", "*.toml", "*.cfg", "*.ini", "*.env*"]

PATTERNS = [
    (re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"), "github_pat_classic"),
    (re.compile(r"\bgithub_pat_[0-9A-Za-z_]{22,}\b"), "github_pat_fine_grained"),
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"), "private_key_header"),
]
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build"}
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".zip", ".exe", ".so", ".dll"}


def _is_false_positive_line(line: str) -> bool:
    if "ghp_[" in line or "github_pat_[" in line:
        return True
    if re.search(r"ghp_\[A-Za-z0-9\]", line) or re.search(r"github_pat_\[[0-9A-Za-z_]", line):
        return True
    if "PRIVATE KEY" in line and "-----BEGIN" not in line:
        return True
    return False


def _iter_files(root: Path):
    for name in SCAN_ROOTS:
        d = root / name
        if not d.exists():
            continue
        for path in d.rglob("*"):
            if not path.is_file():
                continue
            if any(p in SKIP_DIRS for p in path.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            yield path
    for g in TOP_GLOBS:
        for path in root.glob(g):
            if path.is_file():
                yield path


def scan(root: Path = ROOT) -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    seen = set()
    for path in _iter_files(root):
        rp = str(path.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if _is_false_positive_line(line):
                continue
            for rx, kind in PATTERNS:
                if rx.search(line):
                    try:
                        rel = str(path.relative_to(root))
                    except ValueError:
                        rel = str(path)
                    hits.append((rel, i, kind, line.strip()[:120]))
    return hits


def main() -> int:
    hits = scan()
    if hits:
        print("FAIL: secret material detected")
        for path, line_no, kind, snippet in hits[:50]:
            print(f"  {path}:{line_no} [{kind}] {snippet}")
        return 1
    print("Security scan PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
