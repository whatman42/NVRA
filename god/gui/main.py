"""NVRAFX modern desktop operator GUI.

Presentation/control surface only. Existing backend, execution, risk and
readiness gates remain authoritative and are not bypassed here.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit,
    QRadioButton, QStackedWidget, QVBoxLayout, QWidget,
)

from god.app import NungApplication
from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.gui import autostart
from god.gui.notifications import NotificationSound
from crypto.runtime.startup import StartupState, get_startup_state

APP_TITLE = "NVRAFX"
ACCENT = "#4DE0FF"
ACCENT_2 = "#7C5CFF"
BG = "#080C16"
PANEL = "#101827"
PANEL_2 = "#141E30"
TEXT = "#F4F7FB"
MUTED = "#8C9AB2"
BORDER = "#243149"
SUCCESS = "#43D19E"


def _asset(name: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / name


class NVRAFXWindow(QMainWindow):
    def __init__(self, *, autostart_mode: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} — Institutional Control")
        self.setMinimumSize(1120, 720)
        self.resize(1280, 820)
        self.setWindowIcon(QIcon(str(_asset("nvra.ico"))))
        self.data_dir = Path.home() / ".nvrafx"
        self.app_controller = NungApplication(self.data_dir)
        self.adapter = MT5ExecutionAdapter(MT5ConnectionConfig.from_environment())
        self.notifier = NotificationSound(self.data_dir)
        self.crypto_mode = "PAPER"

        self.status_label = QLabel("CRYPTO PAPER  ·  FOREX MT5  ·  IDX SIGNAL")
        self.account_label = QLabel("UNKNOWN")
        self.equity_label = QLabel("—")
        self.positions_label = QLabel("0")
        self.health_label = QLabel("NOT CONNECTED")
        self.forex_mode_label = QLabel("MT5 UNKNOWN")
        self.mode_label = QLabel("CRYPTO PAPER")
        self.idx_mode_label = QLabel("SIGNAL ONLY / PORTFOLIO")
        self.cycle_label = QLabel("0")
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.exec_output = QPlainTextEdit(); self.exec_output.setReadOnly(True)
        self._nav_buttons: list[QPushButton] = []
        self._pages = QStackedWidget()

        self._build_ui()
        self._configure_first_run_autostart()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self._startup_timer = QTimer(self)
        self._startup_timer.timeout.connect(self._refresh_startup_status)
        self._startup_timer.start(500)

        if autostart_mode:
            self._start_autostart_runtime()
        self.refresh()

    def _configure_first_run_autostart(self) -> None:
        if (autostart.is_supported() and not autostart.is_enabled()
                and not autostart.is_disabled_by_user(self.data_dir)):
            try:
                autostart.enable()
                self.autostart_box.setChecked(True)
                self._notify("Windows startup: ENABLED (HKCU Run / standard user scope)")
            except OSError as exc:
                self.autostart_box.setChecked(False)
                self._notify(f"Windows startup registration failed: {exc}")
        else:
            self.autostart_box.setChecked(autostart.is_enabled())

    def _build_ui(self) -> None:
        root = QWidget(); root.setObjectName("root")
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar); side.setContentsMargins(18, 24, 18, 18); side.setSpacing(10)
        brand = QLabel(); brand.setPixmap(QIcon(str(_asset("nvra_logo.png"))).pixmap(174, 62)); brand.setAlignment(Qt.AlignCenter); side.addWidget(brand)
        product = QLabel("INSTITUTIONAL CONTROL"); product.setObjectName("eyebrow"); product.setAlignment(Qt.AlignCenter); side.addWidget(product); side.addSpacing(18)
        for title, index in (("Overview", 0), ("Account", 1), ("Execution", 2), ("Settings", 3)):
            button = QPushButton(title); button.setCheckable(True); button.clicked.connect(lambda checked, i=index: self._select_page(i)); self._nav_buttons.append(button); side.addWidget(button)
        self._nav_buttons[0].setChecked(True); side.addStretch(1)
        safe = QLabel("●  DOMAIN-SAFE / FAIL-CLOSED"); safe.setObjectName("safeBadge"); safe.setAlignment(Qt.AlignCenter); side.addWidget(safe)
        version = QLabel("NVRAFX 1.0.0"); version.setObjectName("muted"); version.setAlignment(Qt.AlignCenter); side.addWidget(version)
        outer.addWidget(sidebar)

        content = QWidget(); main = QVBoxLayout(content); main.setContentsMargins(28, 24, 28, 24); main.setSpacing(18); main.addWidget(self._topbar())
        self._pages.addWidget(self._dashboard_page()); self._pages.addWidget(self._auth_page()); self._pages.addWidget(self._execution_page()); self._pages.addWidget(self._settings_page())
        main.addWidget(self._pages, 1); outer.addWidget(content, 1); self.setCentralWidget(root)

    def _topbar(self) -> QWidget:
        w = QWidget(); row = QHBoxLayout(w); row.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout(); title_box.setSpacing(2)
        title = QLabel("NVRAFX Command Center"); title.setObjectName("title")
        subtitle = QLabel("Autonomous quant control surface · existing safety gates preserved"); subtitle.setObjectName("muted")
        title_box.addWidget(title); title_box.addWidget(subtitle); row.addLayout(title_box); row.addStretch(1)
        self.header_status = QLabel("●  STARTUP INIT"); self.header_status.setObjectName("statusPill"); row.addWidget(self.header_status)
        return w

    def _dashboard_page(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(16)
        cards = QHBoxLayout(); cards.setSpacing(12)
        for label, widget in (("DOMAIN STATUS", self.status_label), ("MT5", self.health_label), ("ACCOUNT", self.account_label), ("EQUITY", self.equity_label)):
            cards.addWidget(self._metric_card(label, widget))
        layout.addLayout(cards)

        middle = QHBoxLayout(); middle.setSpacing(12)
        runtime = self._panel("Runtime status")
        rf = QFormLayout(); rf.setVerticalSpacing(13); rf.addRow("Crypto", self.mode_label); rf.addRow("Forex", self.forex_mode_label); rf.addRow("IDX", self.idx_mode_label); rf.addRow("Open positions", self.positions_label); rf.addRow("Cycles", self.cycle_label); runtime.layout().addLayout(rf)
        actions = QHBoxLayout()
        for text, slot in (("Refresh", self.refresh), ("Connect MT5", self.connect_mt5), ("Disconnect", self.disconnect_mt5)):
            b = QPushButton(text); b.clicked.connect(slot); actions.addWidget(b)
        runtime.layout().addLayout(actions); middle.addWidget(runtime, 1)

        safety = self._panel("Domain posture")
        sl = QVBoxLayout(); sl.setSpacing(8)
        for text in ("Crypto  ·  PAPER / LIVE", "Forex  ·  follows MT5 account", "IDX  ·  SIGNAL ONLY + PORTFOLIO", "Execution gates  ·  preserved"):
            item = QLabel("✓  " + text); item.setObjectName("safetyLine"); sl.addWidget(item)
        safety.layout().addLayout(sl); middle.addWidget(safety, 1); layout.addLayout(middle)

        log_panel = self._panel("Audit & diagnostics"); log_panel.layout().addWidget(self.log); layout.addWidget(log_panel, 1)
        return w

    def _auth_page(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(0, 0, 0, 0)
        g = self._panel("Client account"); f = QFormLayout(); f.setVerticalSpacing(12)
        self.user = QLineEdit(); self.user.setPlaceholderText("Username")
        self.password = QLineEdit(); self.password.setPlaceholderText("Password"); self.password.setEchoMode(QLineEdit.Password)
        self.display = QLineEdit(); self.display.setPlaceholderText("Optional display name")
        f.addRow("Username", self.user); f.addRow("Password", self.password); f.addRow("Display name", self.display); g.layout().addLayout(f)
        row = QHBoxLayout(); register = QPushButton("Create client account"); login = QPushButton("Login"); register.clicked.connect(self.register); login.clicked.connect(self.login); row.addWidget(register); row.addWidget(login); row.addStretch(1); g.layout().addLayout(row)
        note = QLabel("Root-admin initialization and license administration remain cryptographically gated."); note.setObjectName("muted"); g.layout().addWidget(note)
        layout.addWidget(g); layout.addStretch(1); return w

    def _execution_page(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(12)
        crypto = self._panel("CRYPTO")
        crypto.layout().addWidget(QLabel("Execution modes: PAPER and LIVE. Selecting LIVE here does not bypass existing production gates."))
        row = QHBoxLayout(); self.crypto_paper = QRadioButton("PAPER"); self.crypto_live = QRadioButton("LIVE"); self.crypto_paper.setChecked(True)
        self.crypto_paper.toggled.connect(lambda checked: self._set_crypto_mode("PAPER") if checked else None); self.crypto_live.toggled.connect(lambda checked: self._set_crypto_mode("LIVE") if checked else None)
        row.addWidget(self.crypto_paper); row.addWidget(self.crypto_live); row.addStretch(1); crypto.layout().addLayout(row); layout.addWidget(crypto)

        forex = self._panel("FOREX / MT5")
        forex.layout().addWidget(QLabel("No Demo/Real selector. NVRA follows the account currently logged into the MT5 terminal through the bridge."))
        mtrow = QHBoxLayout(); mtrow.addWidget(QLabel("Detected account:")); mtrow.addWidget(self.forex_mode_label); mtrow.addStretch(1); forex.layout().addLayout(mtrow)
        b = QPushButton("Connect / Refresh MT5"); b.clicked.connect(self.connect_mt5); forex.layout().addWidget(b); layout.addWidget(forex)

        idx = self._panel("IDX")
        idx.layout().addWidget(QLabel("SIGNAL ONLY. No broker order execution; IDX signals remain integrated with the unified portfolio."))
        ir = QHBoxLayout(); ir.addWidget(QLabel("Mode:")); ir.addWidget(self.idx_mode_label); ir.addStretch(1); idx.layout().addLayout(ir); layout.addWidget(idx)

        out = self._panel("Diagnostics"); out.layout().addWidget(self.exec_output); layout.addWidget(out, 1)
        return w

    def _settings_page(self) -> QWidget:
        w = QWidget(); layout = QVBoxLayout(w); layout.setContentsMargins(0, 0, 0, 0)
        g = self._panel("Application settings")
        self.autostart_box = QCheckBox("Start NVRAFX with Windows"); self.autostart_box.setToolTip("Uses HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run. No service or scheduled task is installed."); self.autostart_box.toggled.connect(self._toggle_autostart); g.layout().addWidget(self.autostart_box)
        self.mute_box = QCheckBox("Mute notification sounds"); self.mute_box.setChecked(self.notifier.muted); self.mute_box.toggled.connect(self._toggle_sound); g.layout().addWidget(self.mute_box)
        sound_test = QPushButton("Test notification sound"); sound_test.clicked.connect(lambda: self._notify("Notification sound test")); g.layout().addWidget(sound_test)
        note = QLabel("Auto-start launches the bot shell. Crypto supports PAPER/LIVE; Forex follows the MT5 account; IDX is signal-only with portfolio integration."); note.setWordWrap(True); note.setObjectName("muted"); g.layout().addWidget(note)
        self.settings = QPlainTextEdit(); self.settings.setReadOnly(True); g.layout().addWidget(self.settings, 1); self._refresh_settings(); layout.addWidget(g, 1); return w

    def _metric_card(self, label: str, value: QLabel) -> QFrame:
        card = QFrame(); card.setObjectName("metricCard"); l = QVBoxLayout(card); l.setContentsMargins(16, 14, 16, 14); l.setSpacing(5); a = QLabel(label); a.setObjectName("cardLabel"); value.setObjectName("metricValue"); l.addWidget(a); l.addWidget(value); return card

    def _panel(self, title: str) -> QGroupBox:
        box = QGroupBox(title); box.setObjectName("panel"); box.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold)); box.setLayout(QVBoxLayout()); box.layout().setContentsMargins(16, 18, 16, 16); box.layout().setSpacing(12); return box

    def _select_page(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        for i, button in enumerate(self._nav_buttons): button.setChecked(i == index)
        if index == 3: self._refresh_settings()

    def _start_autostart_runtime(self) -> None:
        try:
            result = self.app_controller.start_trial()
            self._notify(f"AUTO-START: bot shell {'started' if result.get('ok') else 'blocked'}")
        except Exception:
            self._notify("AUTO-START ERROR"); self._append(traceback.format_exc())

    def _toggle_sound(self, muted: bool) -> None:
        self.notifier.set_muted(muted); self._append(f"Notification sound: {'MUTED' if muted else 'ENABLED'}")
        if not muted: self.notifier.play()
        self._refresh_settings()

    def _notify(self, message: str) -> None:
        self._append(message); self.notifier.play()

    def _set_crypto_mode(self, mode: str) -> None:
        if mode == self.crypto_mode: return
        self.crypto_mode = mode; self.mode_label.setText(f"CRYPTO {mode}"); self._notify(f"CRYPTO mode changed: {mode}"); self._refresh_settings()

    def _toggle_autostart(self, enabled: bool) -> None:
        if not autostart.is_supported():
            self.autostart_box.blockSignals(True); self.autostart_box.setChecked(False); self.autostart_box.blockSignals(False); self._append("Windows startup: not supported on this OS"); return
        try:
            if enabled:
                autostart.clear_disabled_marker(self.data_dir); autostart.enable(); self._notify("Windows startup: ENABLED")
            else:
                autostart.disable(); autostart.mark_disabled(self.data_dir); self._notify("Windows startup: DISABLED")
        except OSError as exc: self._notify(f"Windows startup change failed: {exc}")
        self._refresh_settings()

    def _refresh_settings(self) -> None:
        self.settings.setPlainText(json.dumps({
            "product": "NVRAFX", "version": "1.0.0",
            "crypto_execution_modes": ["PAPER", "LIVE"], "crypto_selected_mode": self.crypto_mode,
            "forex_execution_mode": "MT5_ACCOUNT", "idx_execution_mode": "SIGNAL_ONLY_PORTFOLIO_INTEGRATED",
            "notification_sound_muted": self.notifier.muted,
            "startup_supported": autostart.is_supported(), "startup_enabled": autostart.is_enabled(),
            "startup_mechanism": "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            "mt5_path_configured": bool(self.adapter.config.path), "mt5_login_configured": self.adapter.config.login is not None,
            "server_configured": bool(self.adapter.config.server),
        }, indent=2))

    def _append(self, message: str) -> None:
        self.log.appendPlainText(message)

    def refresh(self) -> None:
        try:
            state = self.app_controller.dashboard()
            self.cycle_label.setText(str(state.get("cycle_count", 0)))
            self.mode_label.setText(f"CRYPTO {self.crypto_mode}")
            if self.adapter._connected:
                acct = self.adapter.account_state(); mode = self.adapter.account_mode().value
                self.health_label.setText(self.adapter.health().value); self.forex_mode_label.setText(f"MT5 {mode}")
                self.account_label.setText(f"{acct.account_id} / {acct.server}"); self.equity_label.setText(f"{acct.currency} {acct.equity:,.2f}" if acct.equity is not None else "—"); self.positions_label.setText(str(len(self.adapter.open_positions())))
            else:
                self.health_label.setText("NOT CONNECTED"); self.forex_mode_label.setText("MT5 UNKNOWN"); self.account_label.setText("UNKNOWN"); self.equity_label.setText("—"); self.positions_label.setText("0")
            self.idx_mode_label.setText("SIGNAL ONLY / PORTFOLIO")
            self.status_label.setText(f"CRYPTO {self.crypto_mode}  ·  FOREX {self.forex_mode_label.text()}  ·  IDX SIGNAL")
            self._refresh_startup_status(); self._refresh_settings()
        except Exception as exc: self._append(f"refresh error: {exc}")

    def _refresh_startup_status(self) -> None:
        state = get_startup_state()
        labels = {
            StartupState.INIT: "STARTUP INIT",
            StartupState.LICENSE_CHECK: "LICENSE CHECK",
            StartupState.LOAD_STATE: "LOADING STATE",
            StartupState.BROKER_CONNECT: "BROKER CONNECT",
            StartupState.RECONCILIATION: "RECONCILIATION",
            StartupState.RISK_GOVERNOR: "RISK / GOVERNOR",
            StartupState.READY: "READY",
            StartupState.RUNNING: "RUNNING",
            StartupState.SAFE_MODE: "SAFE MODE",
            StartupState.FAILED: "FAILED",
        }
        label = labels.get(state, state.name)
        self.header_status.setText(f"●  {label}")
        self.header_status.setProperty("startupState", state.name)
        self.header_status.style().unpolish(self.header_status)
        self.header_status.style().polish(self.header_status)

    def connect_mt5(self) -> None:
        ok = self.adapter.connect(); self._notify(f"MT5 connect: {'PASS' if ok else 'FAIL'} {self.adapter.last_error}"); self.refresh()

    def disconnect_mt5(self) -> None:
        self.adapter.disconnect(); self._notify("MT5 disconnected"); self.refresh()

    def register(self) -> None:
        result = self.app_controller.register_client(self.user.text().strip(), self.password.text(), self.display.text().strip()); QMessageBox.information(self, "Registration", json.dumps(result, indent=2))

    def login(self) -> None:
        result = self.app_controller.login(self.user.text().strip(), self.password.text()); QMessageBox.information(self, "Login", json.dumps(result, indent=2)); self.refresh()

    def closeEvent(self, event) -> None:
        try: self.adapter.disconnect()
        finally: event.accept()


def _apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(f"""
        QWidget {{ color: {TEXT}; font-family: 'Segoe UI'; font-size: 10pt; }} QMainWindow, #root {{ background: {BG}; }}
        #sidebar {{ background: #0B111E; border-right: 1px solid {BORDER}; }} #title {{ font-size: 21pt; font-weight: 700; }}
        #eyebrow, #cardLabel {{ color: {MUTED}; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }} #muted, QLabel#muted {{ color: {MUTED}; }}
        QPushButton {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 9px; padding: 9px 13px; }} QPushButton:hover {{ border-color: {ACCENT}; background: #17243A; }} QPushButton:checked {{ background: #18283A; border-color: {ACCENT}; color: {ACCENT}; }}
        #statusPill, #safeBadge {{ color: {SUCCESS}; background: #10261F; border: 1px solid #1E5947; border-radius: 12px; padding: 7px 11px; font-weight: 700; }}
        #metricCard, #panel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 13px; }} #metricCard {{ min-height: 82px; }} #metricValue {{ font-size: 14pt; font-weight: 700; }}
        #safetyLine {{ color: {SUCCESS}; padding: 3px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 13px; padding: 0 6px; color: {TEXT}; }}
        QLineEdit, QPlainTextEdit {{ background: #0B1220; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px; selection-background-color: {ACCENT_2}; }} QPlainTextEdit {{ font-family: 'Cascadia Mono', 'Consolas'; font-size: 9pt; }}
        QCheckBox::indicator, QRadioButton::indicator {{ width: 18px; height: 18px; }} QCheckBox, QRadioButton {{ spacing: 8px; padding: 5px 0; }}
    """)


def run_gui(*, autostart_mode: bool = False) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    _apply_theme(app); window = NVRAFXWindow(autostart_mode=autostart_mode); window.show(); return app.exec()
