"""Windows-safe application entrypoint.

Must call multiprocessing.freeze_support() before any other work when frozen.
"""

from __future__ import annotations

import multiprocessing
import sys
import traceback
from collections.abc import Sequence

from crypto.runtime.paths import (
    PathResolver,
    env_override_root,
    is_frozen,
    set_resolver,
)


def _configure_paths() -> PathResolver:
    root = env_override_root()
    resolver = PathResolver(root) if root is not None else PathResolver()
    set_resolver(resolver)
    return resolver


def _startup_banner(resolver: PathResolver) -> None:
    # Lightweight — no secrets
    print(f"CRYPTO starting (frozen={is_frozen()})")
    print(f"application_root={resolver.root}")


def run_application(argv: Sequence[str] | None = None) -> int:
    """Main application body. Returns process exit code."""
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    resolver = _configure_paths()
    _startup_banner(resolver)

    # CLI modes for smoke / CI (never place live orders)
    if "--smoke" in argv:
        return _smoke(resolver)
    if "--version" in argv:
        from crypto import __version__

        print(__version__)
        return 0
    if "--paths" in argv:
        for k, v in resolver.as_dict().items():
            print(f"{k}={v}")
        return 0

    # Default: initialize core subsystems in PAPER-safe order
    return _boot(resolver, argv)


def _smoke(resolver: PathResolver) -> int:
    """Packaging smoke test — no network orders."""
    errors: list[str] = []
    # Paths
    if not resolver.state_dir.is_dir():
        errors.append("state_dir missing")
    # Core imports
    try:
        from crypto.exchanges.factory import create_exchange_adapter  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        errors.append(f"exchange factory: {type(exc).__name__}")
    for name in ("binance", "tokocrypto", "indodax"):
        try:
            mod = __import__(f"crypto.exchanges.{name}", fromlist=["*"])
            assert mod is not None
        except Exception as exc:  # noqa: BLE001
            errors.append(f"adapter {name}: {type(exc).__name__}")
    try:
        from crypto.control import ControlPlane
        from crypto.governor import GovernorThresholds, ResourceGovernor
        from crypto.hardware import build_snapshot
        from crypto.ml.fallback import FallbackModel  # noqa: F401
        from crypto.recovery import Supervisor

        snap = build_snapshot()
        budget = snap.budget
        ResourceGovernor(budget, GovernorThresholds())
        Supervisor()
        ControlPlane()
        # Risk isolation: profile must not alter policy
        from crypto.risk.policy import RiskPolicy

        p1 = RiskPolicy()
        p2 = RiskPolicy()
        assert p1.max_position_pct == p2.max_position_pct
    except Exception as exc:  # noqa: BLE001
        errors.append(f"subsystem: {type(exc).__name__}: {exc}")

    # SQLite in user data dir
    try:
        from crypto.recovery.storage import (
            ensure_recovery_schema,
            integrity_check,
            open_hardened_db,
        )

        db = resolver.sqlite_path("smoke.db")
        conn = open_hardened_db(db)
        ensure_recovery_schema(conn)
        assert integrity_check(conn) == "OK"
        conn.close()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"sqlite: {type(exc).__name__}")

    if errors:
        print("SMOKE FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("SMOKE OK")
    return 0


def _boot(resolver: PathResolver, argv: list[str]) -> int:
    """Run the explicit startup composition root (PAPER-safe by default)."""
    try:
        from crypto.execution.models import ExecutionMode
        from crypto.gui import GuiApp, GuiSnapshot, SnapshotBus
        from crypto.runtime.startup import run_startup

        result = run_startup(resolver, argv)
        if not result.ok:
            print("STARTUP failed — SAFE MODE")
            for error in result.context.errors:
                print(f" - {error}")
            return 2

        mode = ExecutionMode.LIVE if "--live" in argv else ExecutionMode.PAPER
        hw = result.context.hardware
        gov = result.context.governor.evaluate() if result.context.governor is not None else None
        print(f"mode={mode.name} profile={hw.profile.name if hw is not None else 'UNKNOWN'}")
        if gov is not None:
            print(f"governor={gov.state.name} ml_profile={gov.adaptive.ml_profile_name}")
        print("LIVE remains locked until ProductionGate + real exchange canary return GO.")

        if "--no-gui" not in argv:
            import os

            can_show = sys.platform == "win32" or bool(
                os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
            )
            if can_show and hw is not None and gov is not None:
                bus = SnapshotBus()
                bus.publish(
                    GuiSnapshot(
                        trading_mode=mode.name,
                        safety_mode="NORMAL",
                        governor_state=gov.state.name,
                        hardware_profile=hw.profile.name,
                        hardware_score=hw.scores.overall,
                        cpu_usage=gov.cpu_usage,
                        ram_usage=gov.ram_usage,
                        ml_models=gov.adaptive.max_ml_models,
                        ml_active=(),
                        ml_loaded=(),
                        ml_selection_reason=(
                            "Startup composition initialized the runtime; "
                            "model activation remains a runtime concern."
                        ),
                    )
                )
                gui = GuiApp(bus)
                if gui.start():
                    return gui.run()

        if "--serve" in argv:
            print("service orchestration is not enabled; exiting safely")
        return 0
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Public entry. Always call freeze_support first when appropriate."""
    # Critical for PyInstaller on Windows — prevents recursive spawn
    multiprocessing.freeze_support()
    # Guard: child processes must not re-enter full app
    if multiprocessing.current_process().name != "MainProcess":
        return 0
    try:
        return run_application(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 1
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
