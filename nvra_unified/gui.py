from __future__ import annotations
import sys, json, os
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QComboBox, QPlainTextEdit,
    QMessageBox, QSpinBox, QDoubleSpinBox, QSystemTrayIcon, QMenu, QFileDialog,
    QGroupBox, QGridLayout, QFrame
)
from PySide6.QtGui import QAction

from .auth import (
    enrollment_required,
    create_account,
    login as auth_login,
    registration_secret_configured,
    user_data_dir,
)
from god.security import GoogleOAuth, GoogleOAuthError, generate_totp_secret, otpauth_uri
from .config import BrokerAccount
from .runtime import UnifiedRuntime


class NVRAUnifiedWindow(QMainWindow):
    def __init__(self, runtime: UnifiedRuntime):
        super().__init__()
        self.runtime = runtime
        self.config = runtime.config
        self.logged_in = False
        self._current_user = ""
        self.setWindowTitle("NVRA Unified — Autonomous Trading Control Center")
        self.resize(1380, 900)
        self._build()
        self._setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def _build(self):
        tabs = QTabWidget()
        self.tabs = tabs
        tabs.addTab(self.dashboard_tab(), "Dashboard")
        tabs.addTab(self.client_setup_tab(), "Client Setup")
        tabs.addTab(self.crypto_tab(), "Crypto / Brokers")
        tabs.addTab(self.forex_tab(), "Forex / MT5")
        tabs.addTab(self.idx_tab(), "IDX Signal")
        tabs.addTab(self.telegram_tab(), "Telegram")
        tabs.addTab(self.ml_tab(), "ML / Risk / Engine")
        tabs.addTab(self.settings_tab(), "Settings")
        self.setCentralWidget(tabs)

    def dashboard_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.login_label = QLabel("LOCKED — login required")
        l.addWidget(self.login_label)
        g = QFormLayout()
        self.fields = {}
        for k, n in [("running", "Runtime"), ("crypto", "Crypto"), ("forex", "Forex/MT5"), ("idx", "IDX"), ("telegram", "Telegram"), ("hardware", "Hardware"), ("ml_engine", "ML engine"), ("risk", "Risk"), ("cycles", "Cycles")]:
            v = QLabel("-"); self.fields[k] = v; g.addRow(n, v)
        l.addLayout(g)
        row = QHBoxLayout()
        self.login_user = QLineEdit(""); self.login_pass = QLineEdit(); self.login_pass.setEchoMode(QLineEdit.Password)
        row.addWidget(QLabel("User")); row.addWidget(self.login_user); row.addWidget(QLabel("Password")); row.addWidget(self.login_pass)
        b = QPushButton("Login"); b.clicked.connect(self.login); row.addWidget(b)
        self.enroll_btn = QPushButton("Create Account"); self.enroll_btn.setToolTip("First-run local enrollment (offline). No default password."); self.enroll_btn.clicked.connect(self.enroll); row.addWidget(self.enroll_btn)
        google = QPushButton("Sign in with Google"); google.clicked.connect(self.google_login); row.addWidget(google)
        l.addLayout(row)
        mfa = QPushButton("Set up Google Authenticator (MFA)"); mfa.clicked.connect(self.setup_totp); l.addWidget(mfa)
        row2 = QHBoxLayout()
        self.start_btn = QPushButton("START"); self.start_btn.clicked.connect(self.start_runtime)
        self.stop_btn = QPushButton("GRACEFUL STOP"); self.stop_btn.clicked.connect(self.grace_stop)
        self.force_btn = QPushButton("FORCE STOP"); self.force_btn.clicked.connect(self.force_stop)
        for btn in (self.start_btn, self.stop_btn, self.force_btn): row2.addWidget(btn)
        l.addLayout(row2)
        self.audit = QPlainTextEdit(); self.audit.setReadOnly(True); l.addWidget(self.audit)
        return w

    def client_setup_tab(self):
        w = QWidget(); root = QVBoxLayout(w)
        status_box = QGroupBox("Setup Status (actual checks)"); sg = QGridLayout(status_box)
        self.status_labels = {}
        items = [("account", "Account"), ("license", "License"), ("device", "Device"), ("mfa", "MFA"), ("crypto", "Crypto"), ("telegram", "Telegram"), ("gemini", "Gemini"), ("google", "Google"), ("gdrive", "Google Drive"), ("mt5_python", "MT5 Python"), ("mt5_terminal", "MT5 Terminal")]
        for i, (key, title) in enumerate(items):
            sg.addWidget(QLabel(title), i // 3, (i % 3) * 2)
            lab = QLabel("—"); lab.setFrameStyle(QFrame.Panel | QFrame.Sunken)
            self.status_labels[key] = lab; sg.addWidget(lab, i // 3, (i % 3) * 2 + 1)
        root.addWidget(status_box)
        row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Status"); refresh_btn.clicked.connect(self.refresh_setup_status)
        test_all_btn = QPushButton("Test All (safe / no live orders)"); test_all_btn.clicked.connect(self.test_all_safe)
        row.addWidget(refresh_btn); row.addWidget(test_all_btn); root.addLayout(row)
        acc = QGroupBox("Account"); af = QFormLayout(acc)
        self.setup_user_lbl = QLabel("—"); self.setup_role_lbl = QLabel("CLIENT"); self.setup_login_lbl = QLabel("NOT LOGGED IN")
        af.addRow("Username", self.setup_user_lbl); af.addRow("Role", self.setup_role_lbl); af.addRow("Login", self.setup_login_lbl)
        root.addWidget(acc)
        gem = QGroupBox("Gemini API Key (secure storage — never written to config.json)"); gf = QFormLayout(gem)
        self.gemini_key = QLineEdit(); self.gemini_key.setEchoMode(QLineEdit.Password); self.gemini_key.setPlaceholderText("Paste Gemini API key here")
        gf.addRow("API Key", self.gemini_key); self.gemini_status = QLabel("NOT CONFIGURED"); gf.addRow("Status", self.gemini_status)
        grow = QHBoxLayout()
        save_g = QPushButton("Save Securely"); save_g.clicked.connect(self.save_gemini)
        test_g = QPushButton("Test Connection"); test_g.clicked.connect(self.test_gemini)
        clear_g = QPushButton("Clear Key"); clear_g.clicked.connect(self.clear_gemini)
        grow.addWidget(save_g); grow.addWidget(test_g); grow.addWidget(clear_g); gf.addRow(grow); root.addWidget(gem)
        goog = QGroupBox("Google OAuth / Drive"); gof = QFormLayout(goog)
        self.google_client_path = QLineEdit(); self.google_client_path.setReadOnly(True); self.google_client_path.setPlaceholderText("Select OAuth client JSON…")
        pick = QPushButton("Select Google OAuth Client JSON…"); pick.clicked.connect(self.pick_google_client)
        gof.addRow("Client file", self.google_client_path); gof.addRow(pick)
        self.google_email_lbl = QLabel("—"); gof.addRow("Verified email", self.google_email_lbl)
        self.google_status = QLabel("NOT CONFIGURED"); gof.addRow("Status", self.google_status)
        grow2 = QHBoxLayout()
        save_go = QPushButton("Save configuration"); save_go.clicked.connect(self.save_google_client)
        glogin = QPushButton("Google Login"); glogin.clicked.connect(self.google_login)
        gdrive = QPushButton("Test Google Drive backup"); gdrive.clicked.connect(self.backup_drive)
        grow2.addWidget(save_go); grow2.addWidget(glogin); grow2.addWidget(gdrive); gof.addRow(grow2); root.addWidget(goog)
        mfa_box = QGroupBox("MFA (Google Authenticator)"); mf = QFormLayout(mfa_box)
        self.mfa_status = QLabel("NOT CONFIGURED"); mf.addRow("Status", self.mfa_status)
        mfa_btn = QPushButton("Set up / rotate Google Authenticator"); mfa_btn.clicked.connect(self.setup_totp); mf.addRow(mfa_btn); root.addWidget(mfa_box)
        note = QLabel("All secrets use Windows Credential Manager / keyring. Nothing is written to config.json, logs, or status text. Admin / Control Plane is not accessible from this client GUI.")
        note.setWordWrap(True); root.addWidget(note); root.addStretch(1); return w

    def crypto_tab(self):
        w = QWidget(); l = QVBoxLayout(w); f = QFormLayout()
        self.broker = QComboBox(); self.broker.addItems(["binance", "tokocrypto", "indodax"])
        self.account = QLineEdit("default"); self.api_key = QLineEdit(); self.api_key.setEchoMode(QLineEdit.Password)
        self.api_secret = QLineEdit(); self.api_secret.setEchoMode(QLineEdit.Password)
        f.addRow("Broker", self.broker); f.addRow("Account ID", self.account); f.addRow("API Key", self.api_key); f.addRow("API Secret", self.api_secret); l.addLayout(f)
        row = QHBoxLayout()
        save = QPushButton("Save Securely"); save.clicked.connect(self.save_exchange)
        test = QPushButton("Test Connection (read-only)"); test.clicked.connect(self.test_exchange)
        clear = QPushButton("Remove / Clear Credential"); clear.clicked.connect(self.clear_exchange)
        row.addWidget(save); row.addWidget(test); row.addWidget(clear); l.addLayout(row)
        self.crypto_status = QLabel("Status: —"); l.addWidget(self.crypto_status)
        self.crypto_info = QPlainTextEdit(); self.crypto_info.setReadOnly(True); l.addWidget(self.crypto_info)
        l.addWidget(QLabel("Credentials stored in Windows Credential Manager / keyring only. Withdrawal is disabled. Risk ceiling cannot be changed by client."))
        return w

    def forex_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("Forex uses the installed MetaTrader 5 terminal. No broker password or API key is stored in NVRA."))
        self.mt5_python_status = QLabel("Python module: —"); self.mt5_terminal_status = QLabel("Terminal: —"); self.mt5_init_status = QLabel("Initialized: —")
        l.addWidget(self.mt5_python_status); l.addWidget(self.mt5_terminal_status); l.addWidget(self.mt5_init_status)
        self.mt5_info = QPlainTextEdit(); self.mt5_info.setReadOnly(True); l.addWidget(self.mt5_info)
        row = QHBoxLayout()
        detect = QPushButton("Detect MT5 now"); detect.clicked.connect(self.detect_mt5)
        test = QPushButton("Test MT5 (no orders)"); test.clicked.connect(self.test_mt5)
        row.addWidget(detect); row.addWidget(test); l.addLayout(row); return w

    def idx_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("IDX mode is SIGNAL-ONLY via Telegram. Portfolio uses simulated IDR balance."))
        f = QFormLayout(); self.idx_balance = QDoubleSpinBox(); self.idx_balance.setMaximum(10_000_000_000); self.idx_balance.setValue(self.config.idx_initial_balance)
        f.addRow("Simulated balance (IDR)", self.idx_balance); l.addLayout(f)
        row = QHBoxLayout()
        save = QPushButton("Save balance"); save.clicked.connect(self.save_idx)
        reset = QPushButton("Reset to 10,000,000 IDR"); reset.clicked.connect(self.reset_idx)
        row.addWidget(save); row.addWidget(reset); l.addLayout(row)
        self.idx_info = QPlainTextEdit(); self.idx_info.setReadOnly(True); l.addWidget(self.idx_info); return w

    def telegram_tab(self):
        w = QWidget(); l = QVBoxLayout(w); f = QFormLayout()
        self.tg_token = QLineEdit(); self.tg_token.setEchoMode(QLineEdit.Password); self.tg_chat = QLineEdit()
        f.addRow("Bot token", self.tg_token); f.addRow("Chat ID", self.tg_chat); l.addLayout(f)
        self.tg_status = QLabel("Status: NOT CONFIGURED"); l.addWidget(self.tg_status)
        row = QHBoxLayout()
        save = QPushButton("Save Securely"); save.clicked.connect(self.save_telegram)
        test = QPushButton("Test Telegram"); test.clicked.connect(self.test_telegram)
        clear = QPushButton("Clear Credential"); clear.clicked.connect(self.clear_telegram)
        row.addWidget(save); row.addWidget(test); row.addWidget(clear); l.addLayout(row)
        self.cash_broker = QComboBox(); self.cash_broker.addItems(["tokocrypto", "binance", "indodax"])
        self.cash_amount = QDoubleSpinBox(); self.cash_amount.setMaximum(1_000_000_000_000); self.cash_amount.setSuffix(" IDR")
        cash = QPushButton("Create cashout request (verified capability required)"); cash.clicked.connect(self.cashout)
        cf = QFormLayout(); cf.addRow("Broker", self.cash_broker); cf.addRow("Amount", self.cash_amount); l.addLayout(cf); l.addWidget(cash)
        l.addWidget(QLabel("Cashout is fail-closed. Token is never written to config.json.")); return w

    def ml_tab(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("Unified engine: adaptive resource governor + ML ensemble + risk gate."))
        self.ml_info = QPlainTextEdit(); self.ml_info.setReadOnly(True); l.addWidget(self.ml_info); return w

    def settings_tab(self):
        w = QWidget(); l = QVBoxLayout(w); f = QFormLayout()
        self.grace = QSpinBox(); self.grace.setRange(2, 300); self.grace.setValue(self.config.grace_stop_seconds)
        f.addRow("Graceful stop seconds", self.grace); l.addLayout(f)
        b = QPushButton("Save settings"); b.clicked.connect(self.save_settings); l.addWidget(b)
        drive = QPushButton("Backup encrypted state to Google Drive"); drive.clicked.connect(self.backup_drive); l.addWidget(drive)
        reg = QLabel("Registration secret: CONFIGURED" if registration_secret_configured() else "Registration secret: NOT CONFIGURED (set NVRA_REGISTRATION_SECRET)")
        l.addWidget(reg)
        l.addWidget(QLabel("Data persists under %s. GUI close hides to tray; runtime remains active until Graceful Stop." % self.runtime.snapshot()["home"]))
        return w

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self); self.tray.setToolTip("NVRA Unified")
        menu = QMenu()
        show = QAction("Open", self); show.triggered.connect(self.showNormal); menu.addAction(show)
        stop = QAction("Graceful Stop", self); stop.triggered.connect(self.grace_stop); menu.addAction(stop)
        quit_ = QAction("Stop + Exit", self); quit_.triggered.connect(self._quit); menu.addAction(quit_)
        self.tray.setContextMenu(menu); self.tray.show()

    def enroll(self):
        result = create_account(self.login_user.text(), self.login_pass.text())
        if result.ok:
            self.logged_in = False; self._current_user = ""
            self.login_label.setText("LOCKED — account created; please log in"); self.login_pass.clear()
            QMessageBox.information(self, "Create Account", result.message); self.refresh_setup_status(); return
        QMessageBox.warning(self, "Create Account", result.message)

    def login(self):
        result = auth_login(self.login_user.text(), self.login_pass.text())
        if result.ok:
            self.logged_in = True; self._current_user = self.login_user.text().strip()
            self.login_label.setText("AUTHENTICATED — CLIENT OPERATOR"); self.login_pass.clear()
            self.start_runtime(); self.refresh_setup_status(); return
        self.logged_in = False; self._current_user = ""
        self.login_label.setText("LOCKED — login required")
        QMessageBox.warning(self, "Login failed", result.message); self.refresh_setup_status()

    def google_login(self):
        if not self._guard(): return
        if enrollment_required():
            QMessageBox.warning(self, "Enrollment required", "Complete Create Account (first-run enrollment) before using Google sign-in."); return
        try:
            client_file = self.config.google_oauth_client_file.strip()
            if not client_file: raise GoogleOAuthError("Select and save Google OAuth Client JSON first (Client Setup tab).")
            result = GoogleOAuth(client_file, self.runtime.secrets.google_oauth_token, self.runtime.secrets.set_google_oauth_token).login()
            if not result.get("verified_email") or not result.get("email"): raise GoogleOAuthError("Google account is not verified")
            self.config.google_account_email = result["email"]; self.config.save()
            self.logged_in = True; self.login_label.setText(f"GOOGLE AUTHENTICATED — {result['email']}")
            self.audit.appendPlainText("Google OAuth authentication succeeded."); self.start_runtime(); self.refresh_setup_status()
        except Exception as exc:
            QMessageBox.warning(self, "Google login failed", str(exc))

    def setup_totp(self):
        if not self._guard(): return
        secret = generate_totp_secret(); self.runtime.secrets.set_totp_secret(secret)
        self.config.totp_enabled = True; self.config.save()
        uri = otpauth_uri(secret, self.config.google_account_email or self._current_user or "NVRA-user")
        QMessageBox.information(self, "Google Authenticator", "Add this account to Google Authenticator:\n\n" + uri + "\n\nSecret: " + secret)
        self.refresh_setup_status()

    def _guard(self) -> bool:
        if not self.logged_in:
            QMessageBox.warning(self, "Locked", "Login first."); return False
        return True

    def start_runtime(self):
        if not self._guard(): return
        self.runtime.start(); self.audit.appendPlainText("Runtime started.")

    def grace_stop(self):
        if not self._guard(): return
        self.runtime.request_grace_stop(self.grace.value()); self.audit.appendPlainText("Graceful stop requested.")

    def force_stop(self):
        if not self._guard(): return
        self.runtime.force_stop(); self.audit.appendPlainText("Force stop executed.")

    def save_exchange(self):
        if not self._guard(): return
        broker = self.broker.currentText(); account = self.account.text().strip() or "default"
        if not self.api_key.text() or not self.api_secret.text():
            QMessageBox.warning(self, "Missing", "API key and secret are required."); return
        self.runtime.secrets.set_exchange(broker, account, self.api_key.text(), self.api_secret.text())
        if not any(a.broker == broker and a.account_id == account for a in self.config.crypto_accounts):
            self.config.crypto_accounts.append(BrokerAccount(broker, account))
        self.config.save(); self.api_key.clear(); self.api_secret.clear()
        self.crypto_status.setText(f"Status: CONFIGURED ({broker}/{account})")
        self.crypto_info.setPlainText(json.dumps(self.runtime.portfolio_snapshot(), indent=2))
        QMessageBox.information(self, "Saved", "Credentials stored securely (keyring)."); self.refresh_setup_status()

    def test_exchange(self):
        if not self._guard(): return
        broker = self.broker.currentText(); account = self.account.text().strip() or "default"
        k, s = self.runtime.secrets.exchange(broker, account)
        if not k or not s:
            self.crypto_status.setText("Status: NOT CONFIGURED"); QMessageBox.warning(self, "Test", "No credentials stored for this broker/account."); return
        self.crypto_status.setText(f"Status: CONFIGURED (keys present, no live order)")
        QMessageBox.information(self, "Test Connection", f"Credentials present for {broker}/{account}.\nNetwork authentication is performed by the exchange adapter in PAPER/read-only mode only.\nNo orders and no withdrawals are issued from this test.")

    def clear_exchange(self):
        if not self._guard(): return
        broker = self.broker.currentText(); account = self.account.text().strip() or "default"
        self.runtime.secrets.delete_exchange(broker, account)
        self.config.crypto_accounts = [a for a in self.config.crypto_accounts if not (a.broker == broker and a.account_id == account)]
        self.config.save(); self.api_key.clear(); self.api_secret.clear()
        self.crypto_status.setText("Status: NOT CONFIGURED")
        QMessageBox.information(self, "Cleared", f"Credentials removed for {broker}/{account}."); self.refresh_setup_status()

    def save_telegram(self):
        if not self._guard(): return
        if not self.tg_token.text() or not self.tg_chat.text():
            QMessageBox.warning(self, "Missing", "Bot token and Chat ID are required."); return
        self.runtime.secrets.set_telegram(self.tg_token.text(), self.tg_chat.text())
        self.config.telegram_enabled = True; self.config.telegram_chat_id = self.tg_chat.text(); self.config.save()
        self.tg_token.clear(); self.tg_status.setText("Status: CONFIGURED")
        QMessageBox.information(self, "Saved", "Telegram credentials stored securely."); self.refresh_setup_status()

    def test_telegram(self):
        if not self._guard(): return
        tok, chat = self.runtime.secrets.telegram()
        if not tok or not chat:
            self.tg_status.setText("Status: NOT CONFIGURED"); QMessageBox.warning(self, "Test", "Telegram not configured."); return
        self.tg_status.setText("Status: CONFIGURED (credentials present)")
        QMessageBox.information(self, "Test Telegram", "Bot token and Chat ID are present in secure storage.\nLive send is intentionally not performed from this GUI test to avoid accidental messages.")

    def clear_telegram(self):
        if not self._guard(): return
        self.runtime.secrets.delete_telegram()
        self.config.telegram_enabled = False; self.config.telegram_chat_id = ""; self.config.save()
        self.tg_token.clear(); self.tg_chat.clear(); self.tg_status.setText("Status: NOT CONFIGURED")
        QMessageBox.information(self, "Cleared", "Telegram credentials removed."); self.refresh_setup_status()

    def save_gemini(self):
        if not self._guard(): return
        key = self.gemini_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing", "Gemini API key is required."); return
        self.runtime.secrets.set_gemini_api_key(key); self.gemini_key.clear(); self.gemini_status.setText("CONFIGURED")
        QMessageBox.information(self, "Saved", "Gemini API key stored securely (keyring). Never written to config.json."); self.refresh_setup_status()

    def test_gemini(self):
        if not self._guard(): return
        from god.comms.gemini_cs import GeminiCustomerService
        key = self.runtime.secrets.gemini_api_key()
        if not key:
            self.gemini_status.setText("NOT CONFIGURED"); QMessageBox.warning(self, "Test", "No Gemini key configured (keyring or GEMINI_API_KEY). Local fallback will be used."); return
        cs = GeminiCustomerService(api_key=key)
        resp = cs.ask("status check — reply with a short hello only")
        if resp.source == "gemini" and resp.ok:
            self.gemini_status.setText("CONNECTION OK"); QMessageBox.information(self, "Test Gemini", "CONNECTION OK (Gemini responded).")
        else:
            self.gemini_status.setText("CONNECTION FAILED (local fallback available)")
            QMessageBox.warning(self, "Test Gemini", f"CONNECTION FAILED or fallback used (source={resp.source}).\nLocal fallback remains available.")
        self.refresh_setup_status()

    def clear_gemini(self):
        if not self._guard(): return
        self.runtime.secrets.delete_gemini_api_key(); self.gemini_key.clear(); self.gemini_status.setText("NOT CONFIGURED")
        QMessageBox.information(self, "Cleared", "Gemini API key removed from secure storage."); self.refresh_setup_status()

    def pick_google_client(self):
        if not self._guard(): return
        path, _ = QFileDialog.getOpenFileName(self, "Select Google OAuth Client JSON", str(Path.home()), "JSON files (*.json);;All files (*)")
        if path: self.google_client_path.setText(path)

    def save_google_client(self):
        if not self._guard(): return
        path = self.google_client_path.text().strip()
        if not path or not Path(path).is_file():
            QMessageBox.warning(self, "Missing", "Select a valid Google OAuth client JSON file first."); return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not (isinstance(data, dict) and ("installed" in data or "web" in data)): raise ValueError("Not a Google OAuth client secrets JSON")
        except Exception as exc:
            QMessageBox.warning(self, "Invalid file", f"Could not validate JSON: {exc}"); return
        self.config.google_oauth_client_file = path; self.config.google_drive_enabled = True; self.config.save()
        self.google_status.setText("CONFIGURED")
        QMessageBox.information(self, "Saved", "Google OAuth client path saved (path only; tokens stay in keyring)."); self.refresh_setup_status()

    def detect_mt5(self):
        if not self._guard(): return
        self._update_mt5_status(); QMessageBox.information(self, "MT5 Detect", "Detection complete. See status labels and details panel.")

    def test_mt5(self):
        if not self._guard(): return
        self._update_mt5_status()
        QMessageBox.information(self, "Test MT5", "MT5 test is diagnostic only (no orders).\nPython module availability is independent of terminal presence.")

    def _update_mt5_status(self):
        py_status = "UNAVAILABLE"
        try:
            import MetaTrader5  # noqa: F401
            py_status = "AVAILABLE"
        except Exception:
            py_status = "UNAVAILABLE"
        self.mt5_python_status.setText(f"Python module: {py_status}")
        term = "NOT FOUND"; init = "NOT ATTEMPTED"; detail = {}
        try:
            from god.mt5_runtime.detect import detect_mt5
            result = detect_mt5()
            term = "FOUND" if getattr(result, "found", False) else "NOT FOUND"
            detail["detect"] = {"found": getattr(result, "found", False), "path": str(getattr(result, "path", "") or "")}
        except Exception as exc:
            detail["detect_error"] = type(exc).__name__; term = "UNAVAILABLE"
        self.mt5_terminal_status.setText(f"Terminal: {term}"); self.mt5_init_status.setText(f"Initialized: {init}")
        detail["python_module"] = py_status; detail["terminal"] = term
        detail["note"] = "No orders issued. LIVE remains gated by Risk/ProductionGate."
        self.mt5_info.setPlainText(json.dumps(detail, indent=2)); return py_status, term

    def refresh_setup_status(self):
        self.setup_user_lbl.setText(self._current_user or "—"); self.setup_role_lbl.setText("CLIENT")
        self.setup_login_lbl.setText("AUTHENTICATED" if self.logged_in else "NOT LOGGED IN")
        self.status_labels["account"].setText("OK" if self.logged_in else "LOCKED")
        try:
            dev = self.runtime.device_status()
            self.status_labels["device"].setText(str(dev.get("status", "UNKNOWN")))
            self.status_labels["license"].setText("ACTIVE" if dev.get("allowed", True) else str(dev.get("status", "BLOCKED")))
        except Exception:
            self.status_labels["device"].setText("UNKNOWN"); self.status_labels["license"].setText("UNKNOWN")
        mfa_ok = self.runtime.secrets.totp_configured()
        self.status_labels["mfa"].setText("CONFIGURED" if mfa_ok else "NOT CONFIGURED"); self.mfa_status.setText("CONFIGURED" if mfa_ok else "NOT CONFIGURED")
        any_crypto = any(self.runtime.secrets.exchange_configured(a.broker, a.account_id) for a in self.config.crypto_accounts) or any(self.runtime.secrets.exchange_configured(b) for b in ("binance", "tokocrypto", "indodax"))
        self.status_labels["crypto"].setText("CONFIGURED" if any_crypto else "NOT CONFIGURED")
        if hasattr(self, "crypto_status"): self.crypto_status.setText("Status: CONFIGURED" if any_crypto else "Status: NOT CONFIGURED")
        tg_ok = self.runtime.secrets.telegram_configured()
        self.status_labels["telegram"].setText("CONFIGURED" if tg_ok else "NOT CONFIGURED")
        if hasattr(self, "tg_status"): self.tg_status.setText("Status: CONFIGURED" if tg_ok else "Status: NOT CONFIGURED")
        gem_ok = self.runtime.secrets.gemini_configured()
        self.status_labels["gemini"].setText("CONFIGURED" if gem_ok else "NOT CONFIGURED")
        if hasattr(self, "gemini_status") and self.gemini_status.text() not in ("CONNECTION OK", "CONNECTION FAILED (local fallback available)"):
            self.gemini_status.setText("CONFIGURED" if gem_ok else "NOT CONFIGURED")
        gpath = (self.config.google_oauth_client_file or "").strip()
        self.google_client_path.setText(gpath); self.google_email_lbl.setText(self.config.google_account_email or "—")
        goog_ok = bool(gpath and Path(gpath).is_file())
        self.status_labels["google"].setText("CONFIGURED" if goog_ok else "NOT CONFIGURED")
        if hasattr(self, "google_status"): self.google_status.setText("CONFIGURED" if goog_ok else "NOT CONFIGURED")
        self.status_labels["gdrive"].setText("READY" if (goog_ok and self.config.google_drive_enabled) else "NOT CONFIGURED")
        py, term = self._update_mt5_status()
        self.status_labels["mt5_python"].setText(py); self.status_labels["mt5_terminal"].setText(term)

    def test_all_safe(self):
        if not self._guard(): return
        self.refresh_setup_status()
        QMessageBox.information(self, "Test All", "Safe diagnostic complete.\n- Secrets presence checked\n- MT5 module/terminal distinguished\n- No live orders, no withdrawals, no risk-ceiling changes\nSee status panel for results.")

    def save_idx(self):
        if not self._guard(): return
        self.config.idx_initial_balance = self.idx_balance.value(); self.config.save()

    def reset_idx(self):
        if not self._guard(): return
        self.idx_balance.setValue(self.runtime.reset_idx_balance())

    def cashout(self):
        if not self._guard(): return
        result = self.runtime.cashout_request(self.cash_broker.currentText(), self.cash_amount.value())
        QMessageBox.information(self, "Cashout", json.dumps(result, indent=2))

    def backup_drive(self):
        if not self._guard(): return
        try:
            result = self.runtime.backup_to_google_drive()
            QMessageBox.information(self, "Google Drive backup", json.dumps(result, indent=2))
        except Exception as exc:
            QMessageBox.warning(self, "Google Drive backup failed", str(exc))
        self.refresh_setup_status()

    def save_settings(self):
        self.config.grace_stop_seconds = self.grace.value(); self.config.save()

    def refresh(self):
        s = self.runtime.snapshot()
        for k, v in s.items():
            if k in self.fields: self.fields[k].setText(str(v))
        if hasattr(self, "idx_info"): self.idx_info.setPlainText(json.dumps(self.runtime.portfolio_snapshot(), indent=2))
        if hasattr(self, "crypto_info"):
            self.crypto_info.setPlainText(json.dumps({"accounts": [a.__dict__ for a in self.config.crypto_accounts], "portfolio": self.runtime.portfolio_snapshot()}, indent=2))
        if hasattr(self, "ml_info"):
            self.ml_info.setPlainText(json.dumps({"engine": s["ml_engine"], "risk": s["risk"], "hardware": s["hardware"], "principle": "ML evidence -> risk gate -> execution"}, indent=2))

    def closeEvent(self, event):
        event.ignore(); self.hide()
        self.tray.showMessage("NVRA Unified", "GUI closed to tray; runtime remains active.", QSystemTrayIcon.Information, 2000)

    def _quit(self):
        self.runtime.request_grace_stop(self.config.grace_stop_seconds)
        QTimer.singleShot((self.config.grace_stop_seconds + 2) * 1000, QApplication.quit)


def run_gui() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    runtime = UnifiedRuntime()
    win = NVRAUnifiedWindow(runtime)
    win.show()
    return app.exec()
