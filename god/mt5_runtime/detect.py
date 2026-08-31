"""MT5 terminal detection — deterministic, non-crashing when absent."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .states import MT5ConnectionState, TerminalSnapshot, AccountMode


@dataclass
class DetectionResult:
    found: bool
    paths: List[str]
    snapshot: TerminalSnapshot


def _candidate_paths() -> List[Path]:
    paths: List[Path] = []
    env = os.environ.get("MT5_TERMINAL_PATH") or os.environ.get("NUNG_MT5_PATH")
    if env:
        paths.append(Path(env))
    if sys.platform == "win32":
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        for base in (pf, pf86):
            paths.append(Path(base) / "MetaTrader 5")
            paths.append(Path(base) / "MetaTrader 5 terminal")
    # Linux/mac: optional wine or explicit path only
    return paths


def detect_mt5() -> DetectionResult:
    """Locate MT5 install. Never raises; returns MT5_NOT_FOUND if absent."""
    found_paths: List[str] = []
    for p in _candidate_paths():
        try:
            if p.exists() and p.is_dir():
                # Prefer presence of terminal executable markers when available
                markers = ["terminal64.exe", "terminal.exe", "metatester64.exe"]
                if any((p / m).exists() for m in markers) or sys.platform != "win32":
                    found_paths.append(str(p.resolve()))
                elif (p / "MQL5").exists():
                    found_paths.append(str(p.resolve()))
        except OSError:
            continue
    if not found_paths:
        snap = TerminalSnapshot(
            state=MT5ConnectionState.MT5_NOT_FOUND,
            message="MetaTrader 5 installation not found",
        )
        return DetectionResult(found=False, paths=[], snapshot=snap)
    snap = TerminalSnapshot(
        state=MT5ConnectionState.MT5_DISCONNECTED,
        terminal_path=found_paths[0],
        account_mode=AccountMode.UNKNOWN,
        message="MT5 path detected; not connected",
    )
    return DetectionResult(found=True, paths=found_paths, snapshot=snap)
