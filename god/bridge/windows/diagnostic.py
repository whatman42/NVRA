"""Windows environment diagnostic — safe, redacted, injectable.

Never logs credentials, tokens, or broker passwords.
"""

from __future__ import annotations

import os
import platform
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence


@dataclass
class WindowsDiagnosticReport:
    """Machine-readable diagnostic (no secrets)."""

    os_name: str
    os_release: str
    architecture: str
    python_version: str
    is_windows: bool
    hostname: str
    username: str
    cwd: str
    path_entries: int
    has_powershell: bool
    has_cmd: bool
    has_where: bool
    registry_available: bool
    localhost_ok: bool
    terminal_candidates: list[dict] = field(default_factory=list)
    metaeditor_candidates: list[dict] = field(default_factory=list)
    process_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "os_name": self.os_name,
            "os_release": self.os_release,
            "architecture": self.architecture,
            "python_version": self.python_version,
            "is_windows": self.is_windows,
            "hostname": self.hostname,
            "username": self.username,
            "cwd": self.cwd,
            "path_entries": self.path_entries,
            "has_powershell": self.has_powershell,
            "has_cmd": self.has_cmd,
            "has_where": self.has_where,
            "registry_available": self.registry_available,
            "localhost_ok": self.localhost_ok,
            "terminal_candidates": list(self.terminal_candidates),
            "metaeditor_candidates": list(self.metaeditor_candidates),
            "process_hints": list(self.process_hints),
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }


class WindowsDiagnostic:
    """Collect host diagnostics with injectable probes (Linux-safe)."""

    def __init__(
        self,
        *,
        system: Optional[str] = None,
        which: Optional[Callable[[str], Optional[str]]] = None,
        process_scanner: Optional[Callable[[], list[dict]]] = None,
        registry_available: Optional[bool] = None,
        path_probe: Optional[Callable[[str], bool]] = None,
        localhost_check: Optional[Callable[[], bool]] = None,
        terminal_discover: Optional[Callable[[], Sequence[Any]]] = None,
        metaeditor_discover: Optional[Callable[[], Sequence[Any]]] = None,
    ) -> None:
        self._system = system or platform.system()
        self._which = which or _default_which
        self._scan = process_scanner
        self._registry_available = registry_available
        self._probe = path_probe or (lambda p: Path(p).exists())
        self._localhost = localhost_check or _default_localhost
        self._terminal_discover = terminal_discover
        self._metaeditor_discover = metaeditor_discover

    def run(self) -> WindowsDiagnosticReport:
        is_win = self._system == "Windows"
        notes: list[str] = []
        if not is_win:
            notes.append("WINDOWS_UNAVAILABLE: host is not Windows; real MT verification pending")

        reg = self._registry_available
        if reg is None:
            reg = is_win

        terminals: list[dict] = []
        if self._terminal_discover is not None:
            for t in self._terminal_discover():
                terminals.append(_terminal_summary(t))
        else:
            notes.append("terminal discovery not injected; use TerminalDiscovery separately")

        editors: list[dict] = []
        if self._metaeditor_discover is not None:
            for e in self._metaeditor_discover():
                editors.append(_editor_summary(e))

        procs: list[str] = []
        if self._scan is not None:
            for p in self._scan():
                name = str(p.get("name") or "")
                if name:
                    procs.append(name.lower())

        return WindowsDiagnosticReport(
            os_name=self._system,
            os_release=platform.release(),
            architecture=platform.machine(),
            python_version=sys.version.split()[0],
            is_windows=is_win,
            hostname=_safe_hostname(),
            username=_safe_username(),
            cwd=str(Path.cwd()),
            path_entries=len(os.environ.get("PATH", "").split(os.pathsep)),
            has_powershell=bool(self._which("powershell") or self._which("pwsh")),
            has_cmd=bool(self._which("cmd") or self._which("cmd.exe")),
            has_where=bool(self._which("where") or self._which("where.exe")),
            registry_available=bool(reg),
            localhost_ok=bool(self._localhost()),
            terminal_candidates=terminals,
            metaeditor_candidates=editors,
            process_hints=sorted(set(procs))[:50],
            notes=notes,
        )


def _default_which(cmd: str) -> Optional[str]:
    from shutil import which

    return which(cmd)


def _default_localhost() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 9), timeout=0.3):
            return True
    except OSError:
        try:
            socket.getaddrinfo("localhost", None)
            return True
        except OSError:
            return False


def _safe_hostname() -> str:
    try:
        return socket.gethostname() or "unknown"
    except Exception:
        return "unknown"


def _safe_username() -> str:
    try:
        return os.getlogin()
    except Exception:
        return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def _terminal_summary(t: Any) -> dict:
    if isinstance(t, dict):
        return {k: t.get(k) for k in ("terminal_id", "platform", "executable_path", "data_path", "experts_path")}
    return {
        "terminal_id": getattr(t, "terminal_id", None),
        "platform": str(getattr(t, "platform", None)),
        "executable_path": getattr(t, "executable_path", None),
        "data_path": getattr(t, "data_path", None),
        "experts_path": getattr(t, "experts_path", None),
    }


def _editor_summary(e: Any) -> dict:
    if isinstance(e, dict):
        return dict(e)
    return {
        "path": getattr(e, "path", None),
        "status": str(getattr(e, "status", None)),
        "version": getattr(e, "version", None),
    }
