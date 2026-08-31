#!/usr/bin/env python3
"""NUNG application entry (dev). Packaging builds NUNG.exe from this entry.

LIVE capital is BLOCKED by default.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from getpass import getpass

# Allow running from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from god.app import NungApplication


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="NUNG")
    parser.add_argument("--data-dir", default=str(Path.home() / ".nung"))
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

    def _token(value: str | None) -> str:
        if value:
            return value.strip()
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
            app.require_auth(_token(None))
        except Exception as e:
            print(json.dumps({"ok": False, "reason": str(e)}))
            return 1
        print(json.dumps(app.dashboard()))
        return 0
    if args.cmd == "start":
        print(json.dumps(app.start(_token(None))))
        return 0
    if args.cmd == "stop":
        print(json.dumps(app.stop(_token(None))))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
