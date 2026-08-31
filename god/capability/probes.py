"""Low-level probes used by discovery.

All probes are defensive: they never raise uncaught exceptions and
return None / empty results when a tool or path is unavailable.
Paths are discovered dynamically — never assumed.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"


def which(cmd: str) -> Optional[str]:
    """Locate executable on PATH (cross-platform)."""
    try:
        return shutil.which(cmd)
    except Exception:
        return None


def run_cmd(
    args: list[str],
    *,
    timeout: float = 8.0,
    env: Optional[dict] = None,
) -> tuple[int, str, str]:
    """Run command, return (exit_code, stdout, stderr). Never raises."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=max(0.1, float(timeout)),
            env=env or os.environ.copy(),
            shell=False,
        )
        stdout = (proc.stdout or "")[:65536].strip()
        stderr = (proc.stderr or "")[:65536].strip()
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", "not_found"
    except Exception as e:
        return -1, "", str(e)


def get_version(executable: str, version_args: list[str] | None = None) -> Optional[str]:
    """Try to extract a version string from an executable."""
    args_candidates = version_args or ["--version", "-version", "-V", "/version"]
    deadline = __import__("time").monotonic() + 3.0
    for flag in args_candidates:
        remaining = deadline - __import__("time").monotonic()
        if remaining <= 0:
            break
        code, out, err = run_cmd([executable, flag], timeout=min(1.0, remaining))
        text = out or err
        if code == 0 and text:
            # Take first line, strip common prefixes
            line = text.splitlines()[0].strip()
            # Extract something that looks like a version
            m = re.search(r"(\d+\.\d+[\w.\-+]*)", line)
            if m:
                return m.group(1)
            if len(line) < 80:
                return line
    return None


def probe_path(path: str | Path) -> bool:
    p = Path(path)
    try:
        return p.is_file() and os.access(str(p), os.X_OK)
    except Exception:
        return False




def windows_registry_query(key: str, value_name: str = "") -> Optional[str]:
    """Query Windows Registry via reg.exe. Returns None on non-Windows or failure."""
    if not IS_WINDOWS:
        return None
    args = ["reg", "query", key]
    if value_name:
        args += ["/v", value_name]
    code, out, _ = run_cmd(args, timeout=5.0)
    if code != 0 or not out:
        return None
    # Parse REG_SZ / REG_EXPAND_SZ lines
    for line in out.splitlines():
        if "REG_" in line:
            parts = line.split(None, 2)
            if len(parts) >= 3:
                return parts[2].strip()
    return None


def expand_windows_path(path: str) -> str:
    if not IS_WINDOWS:
        return path
    try:
        return os.path.expandvars(path)
    except Exception:
        return path


def python_info() -> dict:
    return {
        "executable": sys.executable,
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "prefix": sys.prefix,
    }


def os_info() -> dict:
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
        "platform": platform.platform(),
        "python": python_info(),
    }
    if IS_WINDOWS:
        # Try to get more precise Windows version
        code, out, _ = run_cmd(["cmd", "/c", "ver"], timeout=3.0)
        if code == 0 and out:
            info["windows_ver"] = out
        # Product name from registry
        product = windows_registry_query(
            r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            "ProductName",
        )
        if product:
            info["product_name"] = product
    return info


def cpu_info() -> dict:
    info: dict = {
        "machine": platform.machine(),
        "processor": platform.processor() or "",
        "count": os.cpu_count() or 0,
    }
    if IS_LINUX:
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        info["model"] = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    elif IS_WINDOWS:
        name = windows_registry_query(
            r"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            "ProcessorNameString",
        )
        if name:
            info["model"] = name
    return info


def memory_info() -> dict:
    info: dict = {}
    if IS_LINUX:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        info["total_mb"] = kb // 1024
                    elif line.startswith("MemAvailable:"):
                        kb = int(line.split()[1])
                        info["available_mb"] = kb // 1024
        except Exception:
            pass
    elif IS_WINDOWS:
        code, out, _ = run_cmd(
            ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory", "/value"],
            timeout=5.0,
        )
        if code == 0 and out:
            for line in out.splitlines():
                if line.startswith("TotalPhysicalMemory="):
                    try:
                        total = int(line.split("=", 1)[1].strip())
                        info["total_mb"] = total // (1024 * 1024)
                    except ValueError:
                        pass
    return info


def disk_info() -> list[dict]:
    drives: list[dict] = []
    if IS_WINDOWS:
        code, out, _ = run_cmd(["wmic", "logicaldisk", "get", "DeviceID,FreeSpace,Size,FileSystem", "/format:csv"], timeout=8.0)
        if code == 0 and out:
            lines = [l for l in out.splitlines() if l.strip()]
            if len(lines) >= 2:
                headers = [h.strip() for h in lines[0].split(",")]
                for line in lines[1:]:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) != len(headers):
                        continue
                    row = dict(zip(headers, parts))
                    try:
                        size = int(row.get("Size") or 0)
                        free = int(row.get("FreeSpace") or 0)
                        drives.append({
                            "device": row.get("DeviceID", ""),
                            "filesystem": row.get("FileSystem", ""),
                            "total_mb": size // (1024 * 1024) if size else 0,
                            "free_mb": free // (1024 * 1024) if free else 0,
                        })
                    except ValueError:
                        continue
    else:
        # POSIX: use df
        code, out, _ = run_cmd(["df", "-k", "-P"], timeout=5.0)
        if code == 0 and out:
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        drives.append({
                            "device": parts[0],
                            "total_mb": int(parts[1]) // 1024,
                            "used_mb": int(parts[2]) // 1024,
                            "free_mb": int(parts[3]) // 1024,
                            "mount": parts[5],
                        })
                    except ValueError:
                        continue
    return drives


def network_interfaces() -> list[dict]:
    interfaces: list[dict] = []
    if IS_WINDOWS:
        code, out, _ = run_cmd(["ipconfig", "/all"], timeout=8.0)
        if code == 0 and out:
            current: dict = {}
            for line in out.splitlines():
                line = line.rstrip()
                if line and not line.startswith(" ") and not line.startswith("\t"):
                    if current.get("name"):
                        interfaces.append(current)
                    current = {"name": line.rstrip(":")}
                elif "IPv4" in line and ":" in line:
                    current["ipv4"] = line.split(":", 1)[1].strip().split("(")[0].strip()
                elif "Physical Address" in line and ":" in line:
                    current["mac"] = line.split(":", 1)[1].strip()
            if current.get("name"):
                interfaces.append(current)
    else:
        code, out, _ = run_cmd(["ip", "-o", "addr", "show"], timeout=5.0)
        if code != 0:
            code, out, _ = run_cmd(["ifconfig"], timeout=5.0)
        if code == 0 and out:
            # Best-effort parse
            for line in out.splitlines():
                if ":" in line and ("inet " in line or "inet6 " in line):
                    parts = line.split()
                    name = parts[1].rstrip(":") if len(parts) > 1 else "unknown"
                    interfaces.append({"name": name, "raw": line.strip()})
    return interfaces


def proxy_config() -> dict:
    """Detect proxy from environment (cross-platform) and Windows system settings."""
    cfg: dict = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "NO_PROXY"):
        val = os.environ.get(key)
        if val:
            cfg[key] = val
    if IS_WINDOWS:
        enabled = windows_registry_query(
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "ProxyEnable",
        )
        server = windows_registry_query(
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            "ProxyServer",
        )
        if enabled is not None:
            cfg["windows_proxy_enable"] = enabled
        if server:
            cfg["windows_proxy_server"] = server
    return cfg
