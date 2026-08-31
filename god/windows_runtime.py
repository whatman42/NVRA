"""Compatibility facade for the legacy :mod:`god.runtime.main` entrypoint.

The active NVRAFX control plane remains in ``nvra_unified.runtime``.  This
module only restores the small runtime API expected by the legacy headless
entrypoint; it does not add a second execution path.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from nvra_unified.auth import user_data_dir
from nvra_unified.runtime import UnifiedRuntime


PRODUCT_NAME = "NVRAFX"
RUNTIME_VERSION = "1.0.0"


class RuntimeEnvironment(str, Enum):
    PAPER = "PAPER"


class RuntimeMode(str, Enum):
    HEADLESS = "HEADLESS"
    GUI = "GUI"


class RuntimeState(str, Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RuntimePaths:
    root: Path


def build_paths() -> RuntimePaths:
    return RuntimePaths(root=user_data_dir())


@dataclass(frozen=True)
class RuntimeManifest:
    state: RuntimeState
    gui_required: bool
    live_trading_enabled: bool
    paths_root: str
    environment: str = RuntimeEnvironment.PAPER.value
    mode: str = RuntimeMode.HEADLESS.value

    def to_dict(self) -> dict[str, object]:
        return {
            "product": PRODUCT_NAME,
            "state": self.state.value,
            "gui_required": self.gui_required,
            "live_trading_enabled": self.live_trading_enabled,
            "paths_root": self.paths_root,
            "environment": self.environment,
            "mode": self.mode,
        }


class WindowsRuntime:
    """Legacy-compatible paper runtime wrapper.

    All runtime work is delegated to the existing unified supervisor.  No live
    execution capability is introduced by this compatibility layer.
    """

    def __init__(
        self,
        *,
        environment: RuntimeEnvironment = RuntimeEnvironment.PAPER,
        mode: RuntimeMode = RuntimeMode.HEADLESS,
    ) -> None:
        if environment is not RuntimeEnvironment.PAPER:
            raise ValueError("only PAPER environment is supported by this runtime facade")
        self.environment = environment
        self.mode = mode
        self._runtime = UnifiedRuntime()
        self._state = RuntimeState.STOPPED

    def manifest(self) -> RuntimeManifest:
        snapshot = self._runtime.snapshot()
        state = RuntimeState.RUNNING if snapshot["running"] else self._state
        return RuntimeManifest(
            state=state,
            gui_required=self.mode is RuntimeMode.GUI,
            live_trading_enabled=False,
            paths_root=str(build_paths().root),
            environment=self.environment.value,
            mode=self.mode.value,
        )

    def start(self) -> RuntimeManifest:
        try:
            self._runtime.start()
            self._state = RuntimeState.RUNNING
            return self.manifest()
        except Exception:
            self._state = RuntimeState.FAILED
            return self.manifest()

    def stop(self) -> RuntimeManifest:
        try:
            self._runtime.force_stop()
            self._state = RuntimeState.STOPPED
            return self.manifest()
        except Exception:
            self._state = RuntimeState.FAILED
            return self.manifest()
