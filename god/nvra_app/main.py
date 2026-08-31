"""NVRAFX product CLI helpers (shared with scripts/nvrafx_entry.py).

Paper/headless only. LIVE capital remains blocked.
Product distributed binary name: NVRAFX.exe
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from god.runtime.version import format_version_text

PRODUCT_NAME = "NVRAFX"
PRODUCT_VERSION = "1.0.0"
RUNTIME_VERSION = "1.0.0"
BUILD_ID = "nvrafx-onefile"


def _version_text() -> str:
    return format_version_text(
        product_name=PRODUCT_NAME,
        product_version=PRODUCT_VERSION,
        runtime_version=RUNTIME_VERSION,
        build_id=BUILD_ID,
        executable="NVRAFX.exe",
    )


def cmd_version() -> int:
    sys.stdout.write(_version_text())
    return 0


def cmd_health() -> int:
    payload = {
        "product": PRODUCT_NAME,
        "state": "READY",
        "gui_required": False,
        "live_trading_enabled": False,
        "live_authorized": False,
        "broker_orders_submitted": 0,
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
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
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
        return 0 if res.status == ConfigValidationStatus.VALID else 1
    except Exception as exc:
        out = {
            "status": "ERROR",
            "reasons": [str(exc)],
            "live_trading_enabled": False,
            "live_authorized": False,
            "broker_orders_submitted": 0,
        }
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
        return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="NVRAFX",
        description="NVRAFX — paper/headless runtime (N.U.N.G. architecture)",
    )
    p.add_argument("--version", action="store_true", help="Show product/runtime version")
    p.add_argument("--health", action="store_true", help="Report health (no secrets)")
    p.add_argument("--check-config", action="store_true", help="Validate configuration")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        return cmd_version()
    if args.health:
        return cmd_health()
    if args.check_config:
        return cmd_check_config()

    code = cmd_version()
    cfg_code = cmd_check_config()
    return code if cfg_code == 0 else cfg_code


if __name__ == "__main__":
    raise SystemExit(main())
