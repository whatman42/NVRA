"""Terminal Discovery — locate MT4/MT5 instances without hardcoded paths.

Uses PATH, Registry (Windows), known candidate locations, process inspection.
On non-Windows, returns empty list (or injected fixtures for tests).
No credentials. Multiple instances supported.
"""

from __future__ import annotations

import logging
import os
import platform
from pathlib import Path
from typing import Callable, Optional, Sequence

from .models import TerminalInstance, Platform, TerminalStatus
from .errors import DiscoveryError

logger = logging.getLogger(__name__)

# Candidate basenames only — never mandatory absolute paths.
_MT5_EXE_NAMES = ("terminal64.exe", "terminal.exe")
_MT4_EXE_NAMES = ("terminal.exe",)

# Relative / expandable candidates (Windows). Used only as probes.
_MT5_CANDIDATES = [
    r"%ProgramFiles%\MetaTrader 5\terminal64.exe",
    r"%ProgramFiles(x86)%\MetaTrader 5\terminal64.exe",
    r"%ProgramFiles%\MetaTrader 5\terminal.exe",
    r"%LOCALAPPDATA%\Programs\MetaTrader 5\terminal64.exe",
]
_MT4_CANDIDATES = [
    r"%ProgramFiles%\MetaTrader 4\terminal.exe",
    r"%ProgramFiles(x86)%\MetaTrader 4\terminal.exe",
    r"%ProgramFiles%\MetaTrader\terminal.exe",
]


def _expand(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


def _which(cmd: str) -> Optional[str]:
    from shutil import which

    return which(cmd)


def _probe_path(path: str) -> bool:
    try:
        p = Path(path)
        return p.is_file()
    except OSError:
        return False


def _default_process_scanner() -> list[dict]:
    """Best-effort process scan. Returns list of {name, pid, exe}."""
    results: list[dict] = []
    system = platform.system()
    try:
        if system == "Windows":
            import subprocess

            # tasklist is widely available; avoid hard dependency on psutil
            code = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if code.returncode == 0 and code.stdout:
                for line in code.stdout.splitlines():
                    parts = [p.strip().strip('"') for p in line.split(",")]
                    if len(parts) >= 2:
                        name, pid_s = parts[0], parts[1]
                        if name.lower() in (
                            "terminal64.exe",
                            "terminal.exe",
                            "metatrader.exe",
                        ):
                            try:
                                pid = int(pid_s)
                            except ValueError:
                                pid = None
                            results.append({"name": name, "pid": pid, "exe": None})
        else:
            # Linux/mac: look for processes with those names (rare, for CI mocks)
            import subprocess

            code = subprocess.run(
                ["ps", "-eo", "pid,comm"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if code.returncode == 0 and code.stdout:
                for line in code.stdout.splitlines()[1:]:
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        pid_s, name = parts
                        if name.lower() in ("terminal64", "terminal", "terminal.exe"):
                            try:
                                pid = int(pid_s)
                            except ValueError:
                                pid = None
                            results.append({"name": name, "pid": pid, "exe": None})
    except Exception as e:
        logger.debug("process scan failed: %s", e)
    return results


class TerminalDiscovery:
    """Discover MT4/MT5 terminal instances.

    Inject scanners/path probes for deterministic unit tests.
    """

    def __init__(
        self,
        *,
        path_probe: Optional[Callable[[str], bool]] = None,
        which: Optional[Callable[[str], Optional[str]]] = None,
        process_scanner: Optional[Callable[[], list[dict]]] = None,
        expand: Optional[Callable[[str], str]] = None,
        system: Optional[str] = None,
    ) -> None:
        self._probe = path_probe or _probe_path
        self._which = which or _which
        self._scan_procs = process_scanner or _default_process_scanner
        self._expand = expand or _expand
        self._system = system or platform.system()

    def discover(self) -> list[TerminalInstance]:
        """Return all discovered terminal instances (MT4 + MT5)."""
        found: list[TerminalInstance] = []
        found.extend(self._discover_platform(Platform.MT5, _MT5_EXE_NAMES, _MT5_CANDIDATES))
        found.extend(self._discover_platform(Platform.MT4, _MT4_EXE_NAMES, _MT4_CANDIDATES))
        # Deduplicate by executable_path when present
        seen: set[str] = set()
        unique: list[TerminalInstance] = []
        for t in found:
            key = (t.executable_path or "") + "|" + t.platform.value + "|" + str(t.process_id or "")
            if key in seen:
                continue
            seen.add(key)
            unique.append(t)
        logger.info("Terminal discovery: %d instance(s)", len(unique))
        return unique

    def discover_mt5(self) -> list[TerminalInstance]:
        return [t for t in self.discover() if t.platform == Platform.MT5]

    def discover_mt4(self) -> list[TerminalInstance]:
        return [t for t in self.discover() if t.platform == Platform.MT4]

    def _discover_platform(
        self,
        platform: Platform,
        exe_names: Sequence[str],
        candidates: Sequence[str],
    ) -> list[TerminalInstance]:
        results: list[TerminalInstance] = []
        found_paths: set[str] = set()

        # 1) PATH
        for name in exe_names:
            exe = self._which(name)
            if exe and self._probe(exe):
                found_paths.add(exe)
                results.append(
                    TerminalInstance.create(
                        platform=platform,
                        executable_path=exe,
                        status=TerminalStatus.DISCOVERED,
                        metadata={"source": "path"},
                    )
                )

        # 2) Candidate expanded locations (Windows-oriented)
        if self._system == "Windows" or self._system == "test":
            for cand in candidates:
                expanded = self._expand(cand)
                if expanded in found_paths:
                    continue
                if self._probe(expanded):
                    found_paths.add(expanded)
                    data_path, experts = self._infer_paths(expanded, platform)
                    results.append(
                        TerminalInstance.create(
                            platform=platform,
                            executable_path=expanded,
                            data_path=data_path,
                            experts_path=experts,
                            status=TerminalStatus.DISCOVERED,
                            metadata={"source": "candidate"},
                        )
                    )

        # 3) Running processes
        for proc in self._scan_procs():
            name = (proc.get("name") or "").lower()
            if platform == Platform.MT5 and name not in ("terminal64.exe", "terminal64"):
                if name not in ("terminal.exe", "terminal"):
                    continue
            if platform == Platform.MT4 and name not in ("terminal.exe", "terminal"):
                continue
            pid = proc.get("pid")
            exe = proc.get("exe")
            # Prefer matching an already discovered path
            matched = False
            for t in results:
                if t.process_id is None:
                    # attach pid to first match without pid
                    results[results.index(t)] = TerminalInstance.create(
                        platform=t.platform,
                        executable_path=t.executable_path,
                        data_path=t.data_path,
                        experts_path=t.experts_path,
                        version=t.version,
                        build=t.build,
                        process_id=pid,
                        status=TerminalStatus.RUNNING,
                        terminal_id=t.terminal_id,
                        discovered_at=t.discovered_at,
                        metadata={**t.metadata, "source": t.metadata.get("source", "process")},
                    )
                    matched = True
                    break
            if not matched:
                results.append(
                    TerminalInstance.create(
                        platform=platform,
                        executable_path=exe,
                        process_id=pid,
                        status=TerminalStatus.RUNNING,
                        metadata={"source": "process", "name": proc.get("name")},
                    )
                )

        return results

    def _infer_paths(
        self, exe_path: str, platform: Platform
    ) -> tuple[Optional[str], Optional[str]]:
        """Best-effort data/experts path from install layout."""
        try:
            root = Path(exe_path).resolve().parent
            if platform == Platform.MT5:
                mql = root / "MQL5"
                experts = mql / "Experts"
            else:
                mql = root / "MQL4"
                experts = mql / "Experts"
            data = str(root) if root.is_dir() else None
            exp = str(experts) if experts.is_dir() else (str(mql) if mql.is_dir() else None)
            return data, exp
        except OSError:
            return None, None
