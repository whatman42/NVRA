"""TAHAP 8 — MT5 detection and connection state (typed, fail-safe).

LIVE capital remains BLOCKED by default via safety gate.
This module does not place broker orders.
"""
from __future__ import annotations

from .states import MT5ConnectionState, AccountMode, TerminalSnapshot
from .detect import detect_mt5, DetectionResult
from .safety_gate import LiveCapitalGate, LIVE_CAPITAL_BLOCKED

__all__ = [
    "MT5ConnectionState",
    "AccountMode",
    "TerminalSnapshot",
    "detect_mt5",
    "DetectionResult",
    "LiveCapitalGate",
    "LIVE_CAPITAL_BLOCKED",
]
