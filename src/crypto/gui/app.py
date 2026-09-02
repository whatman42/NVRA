"""PySide6 desktop dashboard — read-only control/observability surface.

The GUI never bypasses RiskEngine or enables exchange trading by itself.
"""
from __future__ import annotations

from typing import Any

from crypto.gui.first_run import FirstRunController
from crypto.gui.state import GuiSnapshot, SnapshotBus
from crypto.gui.wizard import WizardState


def pyside6_available() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


class GuiApp:
    """Informative dashboard controller with a bounded 2 Hz refresh rate."""

    def __init__(self, bus: SnapshotBus, *, refresh_ms: int = 1000) -> None:
        self.bus = bus
        self.refresh_ms = max(500, refresh_ms)
        self._app: Any = None
        self._window: Any = None
        self._timer: Any = None
        self.wizard = WizardState()
        self.first_run = FirstRunController(self.wizard)

    def start(self) -> bool:
        if not pyside6_available():
            return False

        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import (
            QApplication,
            QGridLayout,
            QLabel,
            QMainWindow,
            QVBoxLayout,
            QWidget,
        )

        self._app = QApplication.instance() or QApplication([])
        self._window = QMainWindow()
        self._window.setWindowTitle("CRYPTO — Adaptive Trading Control Center")
        self._window.setMinimumSize(920, 600)

        root = QWidget()
        outer = QVBoxLayout(root)
        title = QLabel("CRYPTO  |  Adaptive Trading Control Center")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        outer.addWidget(title)

        self._status = QLabel()
        self._status.setStyleSheet("font-size: 15px;")
        outer.addWidget(self._status)

        grid = QGridLayout()
        self._labels: dict[str, QLabel] = {}
        fields = (
            ("mode", "Mode"),
            ("safety", "Safety"),
            ("governor", "Governor"),
            ("hardware", "Hardware"),
            ("hw_score", "HW score"),
            ("cpu", "CPU"),
            ("ram", "RAM"),
            ("ml", "ML active"),
            ("ml_loaded", "ML loaded"),
            ("freshness", "Market data"),
            ("equity", "Equity"),
            ("available", "Available"),
            ("daily_loss", "Daily loss"),
            ("drawdown", "Drawdown"),
            ("orders", "Orders F/P/U"),
            ("opportunity", "Top opportunity"),
        )
        for row, (key, label) in enumerate(fields):
            caption = QLabel(f"{label}:")
            value = QLabel("-")
            value.setTextInteractionFlags(
                __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.TextSelectableByMouse
            )
            grid.addWidget(caption, row // 2, (row % 2) * 2)
            grid.addWidget(value, row // 2, (row % 2) * 2 + 1)
            self._labels[key] = value

        outer.addLayout(grid)
        self._selection = QLabel()
        self._selection.setWordWrap(True)
        self._selection.setStyleSheet("font-size: 12px;")
        outer.addWidget(self._selection)

        self._window.setCentralWidget(root)

        timer = QTimer(self._window)
        timer.setInterval(self.refresh_ms)
        timer.timeout.connect(self._refresh)
        timer.start()
        self._timer = timer
        self._refresh()
        self._window.show()
        return True

    def _refresh(self) -> None:
        snap = self.bus.get()
        setv = self._labels.get if hasattr(self, "_labels") else lambda _: None
        values = {
            "mode": snap.trading_mode,
            "safety": snap.safety_mode,
            "governor": snap.governor_state,
            "hardware": snap.hardware_profile,
            "hw_score": f"{snap.hardware_score:.1f}/100",
            "cpu": self._pct(snap.cpu_usage),
            "ram": self._pct(snap.ram_usage),
            "ml": ", ".join(snap.ml_active) or "-",
            "ml_loaded": ", ".join(snap.ml_loaded) or "-",
            "freshness": snap.data_freshness,
            "equity": f"{snap.equity:,.2f}",
            "available": f"{snap.available_balance:,.2f}",
            "daily_loss": f"{snap.daily_loss_pct:.2f}%",
            "drawdown": f"{snap.drawdown_pct:.2f}%",
            "orders": f"{snap.orders_filled}/{snap.orders_pending}/{snap.orders_unknown}",
            "opportunity": snap.top_opportunity or "-",
        }
        for key, value in values.items():
            label = setv(key)
            if label is not None:
                label.setText(str(value))
        if hasattr(self, "_status"):
            self._status.setText(
                "● LIVE ARMED" if snap.trading_mode == "LIVE" and not snap.emergency_stop
                else "● PAPER / SAFE"
            )
        if hasattr(self, "_selection"):
            self._selection.setText(
                "ML Governor: "
                + (snap.ml_selection_reason or "waiting for model selection")
            )

    @staticmethod
    def _pct(value: float | None) -> str:
        return "-" if value is None else f"{value * 100.0:.1f}%"

    def run(self) -> int:
        if self._app is None:
            return 1
        return int(self._app.exec())
