"""GUI layer (Phase 11) — optional PySide6 + first-run setup."""

from crypto.gui.app import GuiApp, pyside6_available
from crypto.gui.first_run import FirstRunController, default_data_dirs, detect_hardware_summary
from crypto.gui.setup_state import FirstRunSetupState, load_setup_state, save_setup_state
from crypto.gui.state import GuiSnapshot, SnapshotBus
from crypto.gui.wizard import (
    OPTIONAL_STEPS,
    SUPPORTED_EXCHANGES,
    WIZARD_ORDER,
    SecurityCheck,
    WizardState,
    WizardStep,
)

__all__ = [
    "GuiApp",
    "GuiSnapshot",
    "SnapshotBus",
    "WizardState",
    "WizardStep",
    "WIZARD_ORDER",
    "OPTIONAL_STEPS",
    "SUPPORTED_EXCHANGES",
    "SecurityCheck",
    "FirstRunController",
    "FirstRunSetupState",
    "load_setup_state",
    "save_setup_state",
    "default_data_dirs",
    "detect_hardware_summary",
    "pyside6_available",
]
