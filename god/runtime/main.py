"""Phase 7B — NVRA brain headless entrypoint.

Product: NVRA · Architecture: N.U.N.G.
Default: PAPER · LIVE not auto-enabled · GUI not required.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from god.production import default_paper_config, validate_config
from god.production.validation import ConfigValidationStatus
from god.runtime.version import format_version_text
from god.windows_runtime import (
    PRODUCT_NAME,
    RUNTIME_VERSION,
    RuntimeEnvironment,
    RuntimeMode,
    WindowsRuntime,
    build_paths,
)

BUILD_ID = "7b-local"
PRODUCT_VERSION = "0.7.0"


def _version_text() -> str:
    return format_version_text(
        product_name="NVRA Brain",
        product_version=PRODUCT_VERSION,
        runtime_version=RUNTIME_VERSION,
        build_id=BUILD_ID,
    )


def cmd_version() -> int:
    sys.stdout.write(_version_text())
    return 0


def cmd_check_config() -> int:
    cfg = default_paper_config()
    res = validate_config(cfg)
    out = {
        "status": res.status.value,
        "reasons": list(res.reasons),
        "live_trading_enabled": False,
    }
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0 if res.status == ConfigValidationStatus.VALID else 1


def cmd_health(runtime: Optional[WindowsRuntime] = None) -> int:
    if runtime is None:
        # ephemeral health without long-running start
        rt = WindowsRuntime(
            environment=RuntimeEnvironment.PAPER,
            mode=RuntimeMode.HEADLESS,
        )
        # don't hold lock forever for --health alone
        m = rt.manifest()
        payload = {
            "product": PRODUCT_NAME,
            "state": m.state.value,
            "gui_required": m.gui_required,
            "live_trading_enabled": m.live_trading_enabled,
            "paths_root": m.paths_root or str(build_paths().root),
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0
    m = runtime.manifest()
    sys.stdout.write(json.dumps(m.to_dict(), indent=2) + "\n")
    return 0


def cmd_paper() -> int:
    """Start paper runtime briefly then stop (safe CLI smoke)."""
    rt = WindowsRuntime(
        environment=RuntimeEnvironment.PAPER,
        mode=RuntimeMode.HEADLESS,
    )
    started = rt.start()
    if started.state.value == "FAILED":
        sys.stderr.write("startup_failed\n")
        return 1
    stopped = rt.stop()
    sys.stdout.write(
        json.dumps(
            {
                "started": started.state.value,
                "stopped": stopped.state.value,
                "live_trading_enabled": False,
                "gui_required": False,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


def cmd_shutdown() -> int:
    # best-effort: start if needed then stop
    rt = WindowsRuntime(mode=RuntimeMode.HEADLESS)
    rt.stop()
    sys.stdout.write(json.dumps({"state": "STOPPED"}, indent=2) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="brain",
        description="NVRA Brain — headless autonomous runtime (N.U.N.G. architecture)",
    )
    p.add_argument("--version", action="store_true", help="Show product/runtime version")
    p.add_argument("--health", action="store_true", help="Report health (no secrets)")
    p.add_argument("--check-config", action="store_true", help="Validate configuration")
    p.add_argument("--paper", action="store_true", help="Paper-mode smoke start/stop")
    p.add_argument("--shutdown", action="store_true", help="Request graceful shutdown")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        return cmd_version()
    if args.check_config:
        return cmd_check_config()
    if args.health:
        return cmd_health()
    if args.paper:
        return cmd_paper()
    if args.shutdown:
        return cmd_shutdown()

    # default: version banner + check-config (fail-closed, no autonomous LIVE)
    code = cmd_version()
    cfg_code = cmd_check_config()
    return code if cfg_code == 0 else cfg_code


if __name__ == "__main__":
    raise SystemExit(main())
