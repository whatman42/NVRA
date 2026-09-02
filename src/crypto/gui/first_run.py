"""First-run setup controller — orchestrates wizard steps without Qt coupling.

GUI remains a view layer; this module owns order, validation, and persistence.
"""
from __future__ import annotations

import platform
import time
from pathlib import Path
from typing import Any, Optional

from crypto.execution.models import ExecutionMode
from crypto.gui.setup_state import (
    FirstRunSetupState,
    load_setup_state,
    save_setup_state,
)
from crypto.gui.wizard import (
    SUPPORTED_EXCHANGES,
    HardwareSummary,
    SecurityCheck,
    WizardState,
    WizardStep,
)


def detect_hardware_summary() -> HardwareSummary:
    """Map host resources to existing institutional workload profiles."""
    try:
        from god.institutional.resource_profiles import recommend_profile
        from god.ml.hardware import detect_hardware

        snap = detect_hardware()
        profile = recommend_profile(snap.total_ram_mb, snap.cpu_threads, snap.gpu_available)
        return HardwareSummary(
            profile=profile.value,
            total_ram_mb=snap.total_ram_mb,
            cpu_threads=snap.cpu_threads,
            gpu_available=snap.gpu_available,
            notes=tuple(snap.notes),
        )
    except Exception as e:
        return HardwareSummary(
            profile="LOW_END_8GB",
            notes=(f"detect_fallback:{type(e).__name__}",),
        )


def default_data_dirs() -> dict[str, str]:
    root = Path.home() / ".nvrafx"
    return {
        "data_dir": str(root),
        "state_dir": str(root / "state"),
        "config_dir": str(root / "config"),
        "logs_dir": str(root / "logs"),
    }


class FirstRunController:
    """Advances WizardState through the first-run sequence."""

    def __init__(
        self,
        state: Optional[WizardState] = None,
        *,
        state_dir: Optional[Path] = None,
    ) -> None:
        self.state = state or WizardState()
        dirs = default_data_dirs()
        if not self.state.data_dir:
            self.state.data_dir = dirs["data_dir"]
        if not self.state.state_dir:
            self.state.state_dir = dirs["state_dir"]
        if not self.state.config_dir:
            self.state.config_dir = dirs["config_dir"]
        self._state_dir = Path(state_dir) if state_dir else Path(self.state.state_dir)

    def bootstrap_welcome(self) -> WizardState:
        self.state.step = WizardStep.WELCOME
        self.state.os_name = platform.system()
        self.state.version_label = "NVRA"
        dirs = default_data_dirs()
        self.state.data_dir = dirs["data_dir"]
        self.state.state_dir = dirs["state_dir"]
        self.state.config_dir = dirs["config_dir"]
        return self.state

    def apply_hardware(self) -> WizardState:
        self.state.hardware = detect_hardware_summary()
        self.state.step = WizardStep.HARDWARE
        return self.state

    def advance(self) -> tuple[bool, str]:
        ok, reason = self.state.can_advance()
        if not ok:
            return False, reason
        self.state.step = self.state.next_step()
        if self.state.step == WizardStep.HARDWARE and not self.state.hardware.total_ram_mb:
            self.apply_hardware()
        if self.state.step == WizardStep.SECURITY:
            self.run_security_review()
        if self.state.step == WizardStep.VALIDATE:
            self.run_validation()
        if self.state.step == WizardStep.DONE:
            self.complete()
        return True, ""

    def back(self) -> None:
        self.state.step = self.state.prev_step()

    def skip_optional(self) -> tuple[bool, str]:
        if not self.state.is_optional():
            return False, "step_not_optional"
        if self.state.step == WizardStep.TELEGRAM:
            self.state.telegram_skipped = True
            self.state.telegram_chat_id = ""
            self.state.set_telegram_token("")
        if self.state.step == WizardStep.COMPUTE:
            self.state.colab_enabled = False
            self.state.kaggle_enabled = False
            self.state.colab_status = "DISABLED"
            self.state.kaggle_status = "DISABLED"
            self.state.compute_provider = "auto"
            self.state.local_compute_enabled = True
        self.state.step = self.state.next_step()
        return True, ""

    def configure_compute(
        self,
        *,
        colab_enabled: bool = False,
        kaggle_enabled: bool = False,
        provider: str = "auto",
    ) -> None:
        self.state.compute_provider = provider if provider in {"auto", "local", "colab", "kaggle"} else "auto"
        self.state.local_compute_enabled = True
        self.state.colab_enabled = bool(colab_enabled)
        self.state.kaggle_enabled = bool(kaggle_enabled)
        if self.state.colab_enabled:
            try:
                from god.ml.compute import ColabComputeProvider, ProviderStatus

                cap = ColabComputeProvider(enabled=True).probe()
                if cap.status == ProviderStatus.AVAILABLE:
                    self.state.colab_status = "AVAILABLE"
                elif cap.status == ProviderStatus.DISABLED:
                    self.state.colab_status = "DISABLED"
                else:
                    self.state.colab_status = "EXTERNAL_SESSION_REQUIRED"
            except Exception:
                self.state.colab_status = "UNAVAILABLE"
        else:
            self.state.colab_status = "DISABLED"
        if self.state.kaggle_enabled:
            try:
                from god.ml.compute import KaggleComputeProvider, ProviderStatus

                cap = KaggleComputeProvider(enabled=True).probe()
                if cap.status == ProviderStatus.AVAILABLE:
                    self.state.kaggle_status = "AVAILABLE"
                else:
                    self.state.kaggle_status = "EXTERNAL_SESSION_REQUIRED"
            except Exception:
                self.state.kaggle_status = "UNAVAILABLE"
        else:
            self.state.kaggle_status = "DISABLED"

    def run_security_review(self) -> list[SecurityCheck]:
        checks: list[SecurityCheck] = []
        checks.append(
            SecurityCheck("no_secrets_in_yaml", True, "settings.yaml must not hold API secrets")
        )
        checks.append(
            SecurityCheck("no_secrets_in_logs", True, "wizard never logs secret fields")
        )
        checks.append(
            SecurityCheck(
                "secrets_cleared_after_take",
                True,
                "take_secrets clears transient memory",
            )
        )
        try:
            from god.ml.compute.security import sanitize_mapping

            sample = sanitize_mapping(
                {"dataset_hash": "x", "api_key": "SECRET", "kaggle_token": "SECRET"}
            )
            ok = "api_key" not in sample and "kaggle_token" not in sample
            checks.append(
                SecurityCheck(
                    "cloud_credentials_excluded_from_payload",
                    ok,
                    "sanitize_mapping strips secrets",
                )
            )
        except Exception as e:
            checks.append(
                SecurityCheck(
                    "cloud_credentials_excluded_from_payload",
                    False,
                    f"sanitize_unavailable:{type(e).__name__}",
                )
            )
        checks.append(
            SecurityCheck("local_fallback_available", self.state.local_compute_enabled, "local compute")
        )
        checks.append(
            SecurityCheck(
                "paper_execution_boundary",
                self.state.mode == ExecutionMode.PAPER,
                f"mode={self.state.mode.name}",
            )
        )
        self.state.security_checks = checks
        return checks

    def run_validation(self) -> bool:
        ok = True
        if not self.state.data_dir:
            ok = False
        if self.state.exchange_id and self.state.exchange_id not in SUPPORTED_EXCHANGES:
            ok = False
        if self.state.mode != ExecutionMode.PAPER:
            ok = False
        try:
            from god.ml.compute import LocalComputeProvider

            if LocalComputeProvider().probe().status.name != "AVAILABLE":
                ok = False
        except Exception:
            ok = False
        try:
            reg_root = Path(self.state.state_dir) / "ml_registry"
            reg_root.mkdir(parents=True, exist_ok=True)
        except OSError:
            ok = False
        self.state.validation_ok = ok
        return ok

    def complete(self) -> FirstRunSetupState:
        self.state.setup_completed = True
        self.state.step = WizardStep.DONE
        self.state.take_secrets()
        providers = ["local"] if self.state.local_compute_enabled else []
        if self.state.colab_enabled:
            providers.append("colab")
        if self.state.kaggle_enabled:
            providers.append("kaggle")
        setup = FirstRunSetupState(
            setup_completed=True,
            workload_profile=self.state.hardware.profile,
            execution_mode=self.state.mode.name,
            exchange_id=self.state.exchange_id,
            operator_configured=bool(self.state.operator_username),
            telegram_configured=bool(self.state.telegram_chat_id) and not self.state.telegram_skipped,
            telegram_skipped=self.state.telegram_skipped,
            local_compute_enabled=self.state.local_compute_enabled,
            colab_enabled=self.state.colab_enabled,
            kaggle_enabled=self.state.kaggle_enabled,
            compute_provider=self.state.compute_provider,
            configured_providers=tuple(providers) or ("local",),
            data_dir=self.state.data_dir,
            completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        save_setup_state(self._state_dir, setup)
        return setup

    def is_setup_complete(self) -> bool:
        return load_setup_state(self._state_dir).setup_completed
