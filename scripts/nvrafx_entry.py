#!/usr/bin/env python3
"""NVRAFX — single product entry (one-file Windows EXE).

Internal modules remain god.* / N.U.N.G. architecture.
Distributed binary name is only NVRAFX.exe (not NUNG.exe, not NVRA.exe).

LIVE capital is BLOCKED by default.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from getpass import getpass
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRODUCT_NAME = "NVRAFX"
PRODUCT_VERSION = "1.0.0"
RUNTIME_VERSION = "1.0.0"
BUILD_ID = "nvrafx-onefile"


def _cli_write(text: str, *, stream: str = "stdout") -> None:
    """Write CLI text without crashing on windowed (console=False) PyInstaller builds.

    On Windows GUI-subsystem executables, stdout/stderr may be detached or
    invalid. Best-effort write; never raise for missing stream handles.
    """
    target = sys.stdout if stream == "stdout" else sys.stderr
    try:
        if target is None:
            return
        target.write(text)
        try:
            target.flush()
        except (OSError, ValueError, AttributeError):
            pass
    except (OSError, ValueError, AttributeError):
        # Detached / closed / invalid handle — ignore for CLI smoke paths.
        if stream == "stdout":
            try:
                err = sys.stderr
                if err is not None:
                    err.write(text)
                    try:
                        err.flush()
                    except (OSError, ValueError, AttributeError):
                        pass
            except (OSError, ValueError, AttributeError):
                pass


def _version_text() -> str:
    return (
        f"NVRAFX\n"
        f"Product Version: {PRODUCT_VERSION}\n"
        f"Runtime Version: {RUNTIME_VERSION}\n"
        f"Build ID: {BUILD_ID}\n"
        f"Architecture: N.U.N.G. / GOD (internal)\n"
        f"Default mode: PAPER\n"
        f"Live trading: disabled by default\n"
        f"Executable: NVRAFX.exe (single product binary)\n"
    )


def cmd_version() -> int:
    _cli_write(_version_text())
    return 0


def cmd_health() -> int:
    payload = {
        "product": PRODUCT_NAME,
        "state": "READY",
        "gui_required": False,
        "live_trading_enabled": False,
        "live_authorized": False,
        "broker_orders_submitted": 0,
        "executable": "NVRAFX.exe",
    }
    _cli_write(json.dumps(payload, indent=2) + "\n")
    return 0


def cmd_check_config() -> int:
    try:
        from god.production import default_paper_config, validate_config
        from god.production.validation import ConfigValidationStatus

        cfg = default_paper_config()
        res = validate_config(cfg)
        out = {
            "status": res.status.value,
            "reasons": list(res.reasons),
            "live_trading_enabled": False,
            "live_authorized": False,
            "broker_orders_submitted": 0,
            "product": PRODUCT_NAME,
        }
        _cli_write(json.dumps(out, indent=2) + "\n")
        return 0 if res.status == ConfigValidationStatus.VALID else 1
    except Exception as exc:
        out = {
            "status": "ERROR",
            "reasons": [str(exc)],
            "live_trading_enabled": False,
            "live_authorized": False,
            "broker_orders_submitted": 0,
            "product": PRODUCT_NAME,
        }
        _cli_write(json.dumps(out, indent=2) + "\n")
        return 1


def _run_nung_app(argv: list[str]) -> int:
    """Optional NUNG application subcommands (register/login/status/start/stop)."""
    from god.app import NungApplication

    parser = argparse.ArgumentParser(prog="NVRAFX")
    parser.add_argument("--data-dir", default=str(Path.home() / ".nvrafx"))
    sub = parser.add_subparsers(dest="cmd")

    p_reg = sub.add_parser("register", help="Register using hidden password prompt; password is never stored in argv")
    p_reg.add_argument("username")
    p_reg.add_argument("--display-name", default="")

    p_login = sub.add_parser("login", help="Login using hidden password prompt; password is never stored in argv")
    p_login.add_argument("username")

    p_status = sub.add_parser("status")
    p_status.add_argument("--token-file", help="Read session token from a protected file")

    p_start = sub.add_parser("start")
    p_start.add_argument("--token-file", help="Read session token from a protected file")

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("--token-file", help="Read session token from a protected file")

    args = parser.parse_args(argv)

    def _token() -> str:
        path = getattr(args, "token_file", None)
        if path:
            return Path(path).read_text(encoding="utf-8").strip()
        env = os.environ.get("NVRA_SESSION_TOKEN", "").strip()
        if env:
            return env
        parser.error("a token file or NVRA_SESSION_TOKEN is required")
        return ""

    def _password() -> str:
        return getpass("Password: ")
    app = NungApplication(Path(args.data_dir))

    if args.cmd == "register":
        print(json.dumps(app.register(args.username, _password(), args.display_name)))
        return 0
    if args.cmd == "login":
        print(json.dumps(app.login(args.username, _password())))
        return 0
    if args.cmd == "status":
        try:
            app.require_auth(_token())
        except Exception as e:
            print(json.dumps({"ok": False, "reason": str(e)}))
            return 1
        print(json.dumps(app.dashboard()))
        return 0
    if args.cmd == "start":
        print(json.dumps(app.start(_token())))
        return 0
    if args.cmd == "stop":
        print(json.dumps(app.stop(_token())))
        return 0

    parser.print_help()
    return 1


def _run_gui(*, autostart_mode: bool = False) -> int:
    try:
        from god.gui.main import run_gui
        return run_gui(autostart_mode=autostart_mode)
    except Exception as exc:
        _cli_write(f"GUI startup failed: {exc}\n", stream="stderr")
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="NVRAFX",
        description="NVRAFX — single product runtime (N.U.N.G. architecture, paper/DEMO)",
    )
    p.add_argument("--version", action="store_true", help="Show product/runtime version")
    p.add_argument("--health", action="store_true", help="Report health (no secrets)")
    p.add_argument("--check-config", action="store_true", help="Validate configuration")
    p.add_argument("--gui", action="store_true", help="Launch the desktop GUI")
    p.add_argument("--autostart", action="store_true", help="Launch the GUI and start safe PAPER/TRIAL runtime")
    p.add_argument(
        "--help-full",
        action="store_true",
        help="Show extended help including app subcommands",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # App subcommands (register/login/...) when first token is a known cmd
    if argv and argv[0] in ("register", "login", "status", "start", "stop"):
        return _run_nung_app(argv)

    parser = build_parser()
    args, _unknown = parser.parse_known_args(argv)

    if args.autostart:
        return _run_gui(autostart_mode=True)
    if args.gui:
        return _run_gui()
    if args.version:
        return cmd_version()
    if args.health:
        return cmd_health()
    if args.check_config:
        return cmd_check_config()
    if args.help_full:
        parser.print_help()
        print("\nApp subcommands: register | login | status | start | stop")
        return 0

    if not argv:
        return _run_gui()

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
