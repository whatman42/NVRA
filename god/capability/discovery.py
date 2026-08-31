"""Capability Discovery Engine.

Discovers available tools, browsers, shells, hardware, and OS features
at startup and on demand. Produces entries for the CapabilityRegistry.

Design rules (from GOD requirements):
- Never hardcode executable locations as mandatory.
- Use PATH, where.exe / which, Registry (Windows), known install locations,
  process inspection, and environment variables.
- Discovery is dynamic: a later rescan can mark newly installed tools as available.
"""

from __future__ import annotations

import logging
import os
import platform
import time
from pathlib import Path
from typing import Optional

from .models import CapabilityProvider, CapabilityType
from .registry import CapabilityRegistry
from . import probes

logger = logging.getLogger(__name__)

# Known browser relative locations (Windows). Used only as *candidates*,
# never as sole source of truth.
_WIN_BROWSER_CANDIDATES = {
    "Microsoft Edge": [
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
        r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe",
    ],
    "Google Chrome": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ],
    "Mozilla Firefox": [
        r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
        r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
    ],
    "Brave": [
        r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
    "Chromium": [
        r"%LOCALAPPDATA%\Chromium\Application\chrome.exe",
    ],
}

_LINUX_BROWSER_NAMES = [
    ("google-chrome", "Google Chrome"),
    ("google-chrome-stable", "Google Chrome"),
    ("chromium", "Chromium"),
    ("chromium-browser", "Chromium"),
    ("firefox", "Mozilla Firefox"),
    ("microsoft-edge", "Microsoft Edge"),
    ("brave-browser", "Brave"),
]

_SHELL_CANDIDATES = {
    "Windows": [
        ("powershell", "PowerShell", ["-Command", "$PSVersionTable.PSVersion.ToString()"]),
        ("pwsh", "PowerShell Core", ["-Command", "$PSVersionTable.PSVersion.ToString()"]),
        ("cmd", "CMD", ["/c", "ver"]),
        ("wt", "Windows Terminal", ["--version"]),
    ],
    "Linux": [
        ("bash", "Bash", ["--version"]),
        ("zsh", "Zsh", ["--version"]),
        ("sh", "sh", ["--version"]),
        ("fish", "Fish", ["--version"]),
    ],
    "Darwin": [
        ("zsh", "Zsh", ["--version"]),
        ("bash", "Bash", ["--version"]),
    ],
}

_CLI_TOOLS = [
    # (command, display_name, capability_type, version_args)
    ("git", "Git", CapabilityType.VCS, ["--version"]),
    ("gh", "GitHub CLI", CapabilityType.VCS, ["--version"]),
    ("python", "Python", CapabilityType.LANGUAGE_RUNTIME, ["--version"]),
    ("python3", "Python3", CapabilityType.LANGUAGE_RUNTIME, ["--version"]),
    ("pip", "pip", CapabilityType.PACKAGE_MANAGER, ["--version"]),
    ("pip3", "pip3", CapabilityType.PACKAGE_MANAGER, ["--version"]),
    ("conda", "Conda", CapabilityType.PACKAGE_MANAGER, ["--version"]),
    ("node", "Node.js", CapabilityType.LANGUAGE_RUNTIME, ["--version"]),
    ("npm", "npm", CapabilityType.PACKAGE_MANAGER, ["--version"]),
    ("docker", "Docker", CapabilityType.CONTAINER, ["--version"]),
    ("docker-compose", "Docker Compose", CapabilityType.CONTAINER, ["--version"]),
    ("7z", "7-Zip", CapabilityType.ARCHIVE, ["--help"]),
    ("7za", "7-Zip", CapabilityType.ARCHIVE, ["--help"]),
    ("tar", "tar", CapabilityType.ARCHIVE, ["--version"]),
    ("curl", "curl", CapabilityType.CLI_UTILITY, ["--version"]),
    ("wget", "wget", CapabilityType.CLI_UTILITY, ["--version"]),
    ("ssh", "OpenSSH", CapabilityType.CLI_UTILITY, ["-V"]),
    ("gcc", "GCC", CapabilityType.COMPILER, ["--version"]),
    ("cl", "MSVC cl", CapabilityType.COMPILER, []),
    ("rustc", "Rust", CapabilityType.COMPILER, ["--version"]),
    ("go", "Go", CapabilityType.LANGUAGE_RUNTIME, ["version"]),
    ("wsl", "WSL", CapabilityType.VIRTUALIZATION, ["--status"]),
    ("code", "VS Code", CapabilityType.CLI_UTILITY, ["--version"]),
]


class CapabilityDiscovery:
    """Discover and register host capabilities."""

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry or CapabilityRegistry()
        self._system = platform.system()

    def scan(self, *, full: bool = True) -> CapabilityRegistry:
        """Run discovery pass and update registry.

        Args:
            full: If True, also probe hardware, network, drives, proxy.
        """
        t0 = time.time()
        logger.info("Capability discovery started (system=%s)", self._system)

        providers: list[CapabilityProvider] = []
        providers.extend(self._discover_os())
        providers.extend(self._discover_shells())
        providers.extend(self._discover_browsers())
        providers.extend(self._discover_cli_tools())
        providers.extend(self._discover_python())

        if full:
            providers.extend(self._discover_hardware())
            providers.extend(self._discover_filesystem())
            providers.extend(self._discover_network())
            providers.extend(self._discover_proxy())

        self.registry.register_many(providers)
        self.registry.mark_scan_complete()

        elapsed = (time.time() - t0) * 1000
        available = sum(1 for p in providers if p.available)
        logger.info(
            "Capability discovery finished: %d providers (%d available) in %.0f ms",
            len(providers),
            available,
            elapsed,
        )
        return self.registry

    # ── OS ───────────────────────────────────────────────────────────────

    def _discover_os(self) -> list[CapabilityProvider]:
        info = probes.os_info()
        return [
            CapabilityProvider.create(
                name=info.get("product_name") or info.get("system", "Unknown"),
                capability=CapabilityType.OS,
                available=True,
                version=info.get("release"),
                interface="system",
                metadata=info,
            )
        ]

    # ── Shells ───────────────────────────────────────────────────────────

    def _discover_shells(self) -> list[CapabilityProvider]:
        results: list[CapabilityProvider] = []
        candidates = _SHELL_CANDIDATES.get(self._system, _SHELL_CANDIDATES.get("Linux", []))
        for cmd, name, ver_args in candidates:
            exe = probes.which(cmd)
            available = exe is not None
            version = None
            if available and exe:
                # Version probe
                if cmd in ("powershell", "pwsh") and probes.IS_WINDOWS:
                    code, out, _ = probes.run_cmd([exe] + ver_args, timeout=8.0)
                    version = out.splitlines()[0].strip() if out else None
                else:
                    version = probes.get_version(exe, ver_args[:1] if ver_args else None)
            results.append(
                CapabilityProvider.create(
                    name=name,
                    capability=CapabilityType.SHELL,
                    available=available,
                    executable=exe,
                    version=version,
                    interface="shell_exec",
                    metadata={"command": cmd},
                )
            )
        return results

    # ── Browsers ─────────────────────────────────────────────────────────

    def _discover_browsers(self) -> list[CapabilityProvider]:
        results: list[CapabilityProvider] = []

        if probes.IS_WINDOWS:
            for name, candidates in _WIN_BROWSER_CANDIDATES.items():
                exe = None
                # 1) PATH
                basename = Path(candidates[0]).name if candidates else None
                if basename:
                    exe = probes.which(basename.replace(".exe", ""))
                    if not exe:
                        exe = probes.which(basename)
                # 2) Known locations (expanded)
                if not exe:
                    for cand in candidates:
                        expanded = probes.expand_windows_path(cand)
                        if probes.probe_path(expanded):
                            exe = expanded
                            break
                # 3) Registry App Paths (common for browsers)
                if not exe and basename:
                    reg_val = probes.windows_registry_query(
                        rf"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{basename}",
                        "",
                    )
                    if reg_val and probes.probe_path(reg_val):
                        exe = reg_val

                available = exe is not None
                version = probes.get_version(exe) if exe else None
                results.append(
                    CapabilityProvider.create(
                        name=name,
                        capability=CapabilityType.BROWSER,
                        available=available,
                        executable=exe,
                        version=version,
                        interface="browser_automation",
                        metadata={"chromium_based": name not in ("Mozilla Firefox",)},
                    )
                )
        else:
            seen_names: set[str] = set()
            for cmd, name in _LINUX_BROWSER_NAMES:
                if name in seen_names:
                    continue
                exe = probes.which(cmd)
                if exe:
                    seen_names.add(name)
                    version = probes.get_version(exe)
                    results.append(
                        CapabilityProvider.create(
                            name=name,
                            capability=CapabilityType.BROWSER,
                            available=True,
                            executable=exe,
                            version=version,
                            interface="browser_automation",
                            metadata={"command": cmd},
                        )
                    )
            # Also register known names as unavailable if not found
            for _, name in _LINUX_BROWSER_NAMES:
                if name not in seen_names:
                    results.append(
                        CapabilityProvider.create(
                            name=name,
                            capability=CapabilityType.BROWSER,
                            available=False,
                            interface="browser_automation",
                        )
                    )
                    seen_names.add(name)

        return results

    # ── CLI tools ────────────────────────────────────────────────────────

    def _discover_cli_tools(self) -> list[CapabilityProvider]:
        results: list[CapabilityProvider] = []
        for cmd, name, cap_type, ver_args in _CLI_TOOLS:
            exe = probes.which(cmd)
            available = exe is not None
            version = None
            if available and exe:
                if ver_args:
                    version = probes.get_version(exe, ver_args)
                else:
                    version = probes.get_version(exe)
            results.append(
                CapabilityProvider.create(
                    name=name,
                    capability=cap_type,
                    available=available,
                    executable=exe,
                    version=version,
                    interface="cli",
                    metadata={"command": cmd},
                )
            )
        return results

    # ── Python (always available — we are running in it) ─────────────────

    def _discover_python(self) -> list[CapabilityProvider]:
        info = probes.python_info()
        return [
            CapabilityProvider.create(
                name="Python",
                capability=CapabilityType.PYTHON,
                available=True,
                executable=info["executable"],
                version=info["version"],
                path=info["executable"],
                interface="python_runtime",
                metadata=info,
            )
        ]

    # ── Hardware ─────────────────────────────────────────────────────────

    def _discover_hardware(self) -> list[CapabilityProvider]:
        results: list[CapabilityProvider] = []
        cpu = probes.cpu_info()
        results.append(
            CapabilityProvider.create(
                name="CPU",
                capability=CapabilityType.HARDWARE,
                available=True,
                version=cpu.get("model") or cpu.get("processor") or None,
                interface="hardware",
                metadata=cpu,
            )
        )
        mem = probes.memory_info()
        results.append(
            CapabilityProvider.create(
                name="RAM",
                capability=CapabilityType.HARDWARE,
                available=bool(mem),
                interface="hardware",
                metadata=mem,
            )
        )
        # GPU — best-effort
        gpu_meta: dict = {}
        if probes.IS_WINDOWS:
            code, out, _ = probes.run_cmd(
                ["wmic", "path", "win32_VideoController", "get", "name", "/value"],
                timeout=6.0,
            )
            if code == 0 and out:
                names = [
                    line.split("=", 1)[1].strip()
                    for line in out.splitlines()
                    if line.lower().startswith("name=") and "=" in line
                ]
                gpu_meta["adapters"] = names
        else:
            code, out, _ = probes.run_cmd(["lspci"], timeout=5.0)
            if code == 0 and out:
                gpus = [l for l in out.splitlines() if "VGA" in l or "3D" in l]
                gpu_meta["adapters"] = gpus
        results.append(
            CapabilityProvider.create(
                name="GPU",
                capability=CapabilityType.HARDWARE,
                available=bool(gpu_meta.get("adapters")),
                interface="hardware",
                metadata=gpu_meta,
            )
        )
        return results

    # ── Filesystem / drives ──────────────────────────────────────────────

    def _discover_filesystem(self) -> list[CapabilityProvider]:
        drives = probes.disk_info()
        return [
            CapabilityProvider.create(
                name="Disk",
                capability=CapabilityType.FILESYSTEM,
                available=bool(drives),
                interface="filesystem",
                metadata={"drives": drives},
            )
        ]

    # ── Network ──────────────────────────────────────────────────────────

    def _discover_network(self) -> list[CapabilityProvider]:
        ifaces = probes.network_interfaces()
        return [
            CapabilityProvider.create(
                name="NetworkInterfaces",
                capability=CapabilityType.NETWORK,
                available=bool(ifaces),
                interface="network",
                metadata={"interfaces": ifaces},
            )
        ]

    # ── Proxy ────────────────────────────────────────────────────────────

    def _discover_proxy(self) -> list[CapabilityProvider]:
        cfg = probes.proxy_config()
        return [
            CapabilityProvider.create(
                name="Proxy",
                capability=CapabilityType.PROXY,
                available=bool(cfg),
                interface="proxy",
                metadata=cfg,
            )
        ]
