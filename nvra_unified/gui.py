from __future__ import annotations
import sys, json
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,
    QLabel,QLineEdit,QPushButton,QTabWidget,QComboBox,QPlainTextEdit,
    QMessageBox,QSpinBox,QDoubleSpinBox,QSystemTrayIcon,QMenu
)
from PySide6.QtGui import QAction

from .auth import (
    enrollment_required,
    enroll_first_user,
    create_account,
    login as auth_login,
    verify_default_login,
    registration_secret_configured,
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
        self.setWindowTitle("NVRA Unified — Autonomous Trading Control Center")
        self.resize(1320, 860)
        self._build()
        self._setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def _build(self):
        tabs=QTabWidget()
        tabs.addTab(self.dashboard_tab(),"Dashboard")
        tabs.addTab(self.crypto_tab(),"Crypto / Brokers")
        tabs.addTab(self.forex_tab(),"Forex / MT5")
        tabs.addTab(self.idx_tab(),"IDX Signal")
        tabs.addTab(self.telegram_tab(),"Telegram")
        tabs.addTab(self.ml_tab(),"ML / Risk / Engine")
        tabs.addTab(self.settings_tab(),"Settings")
        self.setCentralWidget(tabs)

    def dashboard_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        self.login_label=QLabel("LOCKED — login required")
        l.addWidget(self.login_label)
        g=QFormLayout()
        self.fields={}
        for k,n in [("running","Runtime"),("crypto","Crypto"),("forex","Forex/MT5"),("idx","IDX"),("telegram","Telegram"),
                    ("hardware","Hardware"),("ml_engine","ML engine"),("risk","Risk"),("cycles","Cycles")]:
            v=QLabel("-"); self.fields[k]=v; g.addRow(n,v)
        l.addLayout(g)
        row=QHBoxLayout()
        self.login_user=QLineEdit(""); self.login_pass=QLineEdit(); self.login_pass.setEchoMode(QLineEdit.Password)
        row.addWidget(QLabel("User")); row.addWidget(self.login_user); row.addWidget(QLabel("Password")); row.addWidget(self.login_pass)
        b=QPushButton("Login"); b.clicked.connect(self.login); row.addWidget(b)
        self.enroll_btn=QPushButton("Create Account"); self.enroll_btn.setToolTip("First-run local enrollment (offline). No default password."); self.enroll_btn.clicked.connect(self.enroll); row.addWidget(self.enroll_btn)
        google=QPushButton("Sign in with Google"); google.clicked.connect(self.google_login); row.addWidget(google)
        l.addLayout(row)
        mfa=QPushButton("Set up Google Authenticator"); mfa.clicked.connect(self.setup_totp); l.addWidget(mfa)
        row2=QHBoxLayout()
        self.start_btn=QPushButton("START"); self.start_btn.clicked.connect(self.start_runtime)
        self.stop_btn=QPushButton("GRACEFUL STOP"); self.stop_btn.clicked.connect(self.grace_stop)
        self.force_btn=QPushButton("FORCE STOP"); self.force_btn.clicked.connect(self.force_stop)
        for b in (self.start_btn,self.stop_btn,self.force_btn): row2.addWidget(b)
        l.addLayout(row2)
        self.audit=QPlainTextEdit(); self.audit.setReadOnly(True); l.addWidget(self.audit)
        return w

    def crypto_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        f=QFormLayout()
        self.broker=QComboBox(); self.broker.addItems(["binance","tokocrypto","indodax"])
        self.account=QLineEdit("default"); self.api_key=QLineEdit(); self.api_secret=QLineEdit(); self.api_secret.setEchoMode(QLineEdit.Password)
        f.addRow("Broker",self.broker); f.addRow("Account ID",self.account); f.addRow("API Key",self.api_key); f.addRow("API Secret",self.api_secret)
        l.addLayout(f)
        save=QPushButton("Save broker credentials securely"); save.clicked.connect(self.save_exchange); l.addWidget(save)
        self.crypto_info=QPlainTextEdit(); self.crypto_info.setReadOnly(True); l.addWidget(self.crypto_info)
        l.addWidget(QLabel("Credentials are stored in Windows Credential Manager/keyring. Withdrawal permissions should remain disabled."))
        return w

    def forex_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(QLabel("Forex uses the installed MetaTrader 5 terminal. No broker credentials are stored here."))
        self.mt5_info=QPlainTextEdit(); self.mt5_info.setReadOnly(True); l.addWidget(self.mt5_info)
        b=QPushButton("Detect MT5 terminal now"); b.clicked.connect(self.refresh); l.addWidget(b)
        return w

    def idx_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(QLabel("IDX mode is SIGNAL-ONLY via Telegram. Portfolio uses simulated IDR balance."))
        f=QFormLayout()
        self.idx_balance=QDoubleSpinBox(); self.idx_balance.setMaximum(10_000_000_000); self.idx_balance.setValue(self.config.idx_initial_balance)
        f.addRow("Simulated balance (IDR)",self.idx_balance); l.addLayout(f)
        row=QHBoxLayout()
        save=QPushButton("Save balance"); save.clicked.connect(self.save_idx); reset=QPushButton("Reset to 10,000,000 IDR"); reset.clicked.connect(self.reset_idx)
        row.addWidget(save); row.addWidget(reset); l.addLayout(row)
        self.idx_info=QPlainTextEdit(); self.idx_info.setReadOnly(True); l.addWidget(self.idx_info)
        return w

    def telegram_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        f=QFormLayout()
        self.tg_token=QLineEdit(); self.tg_token.setEchoMode(QLineEdit.Password); self.tg_chat=QLineEdit()
        f.addRow("Bot token",self.tg_token); f.addRow("Chat ID",self.tg_chat); l.addLayout(f)
        b=QPushButton("Save Telegram securely"); b.clicked.connect(self.save_telegram); l.addWidget(b)
        self.cash_broker=QComboBox(); self.cash_broker.addItems(["tokocrypto","binance","indodax"])
        self.cash_amount=QDoubleSpinBox(); self.cash_amount.setMaximum(1_000_000_000_000); self.cash_amount.setSuffix(" IDR")
        cash=QPushButton("Create cashout request (verified capability required)"); cash.clicked.connect(self.cashout)
        cf=QFormLayout(); cf.addRow("Broker",self.cash_broker); cf.addRow("Amount",self.cash_amount); l.addLayout(cf); l.addWidget(cash)
        l.addWidget(QLabel("Cashout is fail-closed: existing CRYPTO adapters explicitly disable withdrawal, so no money is moved by this build."))
        return w

    def ml_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(QLabel("Unified engine: adaptive resource governor + ML ensemble + risk gate."))
        self.ml_info=QPlainTextEdit(); self.ml_info.setReadOnly(True); l.addWidget(self.ml_info)
        return w

    def settings_tab(self):
        w=QWidget(); l=QVBoxLayout(w)
        f=QFormLayout()
        self.grace=QSpinBox(); self.grace.setRange(2,300); self.grace.setValue(self.config.grace_stop_seconds)
        f.addRow("Graceful stop seconds",self.grace); l.addLayout(f)
        b=QPushButton("Save settings"); b.clicked.connect(self.save_settings); l.addWidget(b)
        drive=QPushButton("Backup encrypted state to Google Drive"); drive.clicked.connect(self.backup_drive); l.addWidget(drive)
        reg=QLabel("Registration secret: CONFIGURED" if registration_secret_configured() else "Registration secret: NOT CONFIGURED (set NVRA_REGISTRATION_SECRET)")
        l.addWidget(reg)
        l.addWidget(QLabel("Data persists under %s. GUI close hides to tray; runtime remains active until Graceful Stop." % self.runtime.snapshot()["home"]))
        return w

    def _setup_tray(self):
        self.tray=QSystemTrayIcon(self)
        self.tray.setToolTip("NVRA Unified")
        menu=QMenu()
        show=QAction("Open",self); show.triggered.connect(self.showNormal); menu.addAction(show)
        stop=QAction("Graceful Stop",self); stop.triggered.connect(self.grace_stop); menu.addAction(stop)
        quit_=QAction("Stop + Exit",self); quit_.triggered.connect(self._quit); menu.addAction(quit_)
        self.tray.setContextMenu(menu); self.tray.show()

    def enroll(self):
        """Create Account — first-run local enrollment only."""
        result = create_account(self.login_user.text(), self.login_pass.text())
        if result.ok:
            self.logged_in = False
            self.login_label.setText("LOCKED — account created; please log in")
            self.login_pass.clear()
            QMessageBox.information(self, "Create Account", result.message)
            return
        QMessageBox.warning(self, "Create Account", result.message)

    def login(self):
        result = auth_login(self.login_user.text(), self.login_pass.text())
        if result.ok:
            self.logged_in = True
            self.login_label.setText("AUTHENTICATED — ENROLLED OPERATOR")
            self.login_pass.clear()
            self.start_runtime()
            return
        self.logged_in = False
        self.login_label.setText("LOCKED — login required")
        QMessageBox.warning(self, "Login failed", result.message)

    def google_login(self):
        if enrollment_required():
            QMessageBox.warning(self, "Enrollment required", "Complete Create Account (first-run enrollment) before using Google sign-in.")
            return
        try:
            client_file = self.config.google_oauth_client_file.strip()
            if not client_file:
                raise GoogleOAuthError("Configure google_oauth_client_file first")
            result = GoogleOAuth(client_file, self.runtime.secrets.google_oauth_token, self.runtime.secrets.set_google_oauth_token).login()
            if not result.get("verified_email") or not result.get("email"):
                raise GoogleOAuthError("Google account is not verified")
            self.config.google_account_email = result["email"]
            self.config.save()
            self.logged_in = True
            self.login_label.setText(f"GOOGLE AUTHENTICATED — {result['email']}")
            self.audit.appendPlainText("Google OAuth authentication succeeded.")
            self.start_runtime()
        except Exception as exc:
            QMessageBox.warning(self, "Google login failed", str(exc))

    def setup_totp(self):
        if not self._guard(): return
        secret = generate_totp_secret()
        self.runtime.secrets.set_totp_secret(secret)
        uri = otpauth_uri(secret, self.config.google_account_email or "NVRA-user")
        QMessageBox.information(self, "Google Authenticator", "Add this account to Google Authenticator:\n\n" + uri + "\n\nSecret: " + secret)

    def _guard(self):
        if not self.logged_in:
            QMessageBox.warning(self,"Locked","Login first."); return False
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
        broker=self.broker.currentText(); account=self.account.text().strip()
        if not self.api_key.text() or not self.api_secret.text():
            QMessageBox.warning(self,"Missing","API key and secret are required."); return
        self.runtime.secrets.set_exchange(broker,account,self.api_key.text(),self.api_secret.text())
        if not any(a.broker==broker and a.account_id==account for a in self.config.crypto_accounts):
            self.config.crypto_accounts.append(BrokerAccount(broker,account))
        self.config.save(); self.api_key.clear(); self.api_secret.clear()
        self.crypto_info.setPlainText(json.dumps(self.runtime.portfolio_snapshot(),indent=2))
        QMessageBox.information(self,"Saved","Credentials stored securely.")

    def save_telegram(self):
        if not self._guard(): return
        if not self.tg_token.text() or not self.tg_chat.text(): return
        self.runtime.secrets.set_telegram(self.tg_token.text(),self.tg_chat.text())
        self.config.telegram_enabled=True; self.config.telegram_chat_id=self.tg_chat.text(); self.config.save()
        self.tg_token.clear(); QMessageBox.information(self,"Saved","Telegram credentials stored securely.")

    def save_idx(self):
        if not self._guard(): return
        self.config.idx_initial_balance=self.idx_balance.value(); self.config.save()

    def reset_idx(self):
        if not self._guard(): return
        self.idx_balance.setValue(self.runtime.reset_idx_balance())

    def cashout(self):
        if not self._guard(): return
        result=self.runtime.cashout_request(self.cash_broker.currentText(),self.cash_amount.value())
        QMessageBox.information(self,"Cashout",json.dumps(result,indent=2))

    def backup_drive(self):
        if not self._guard(): return
        try:
            result = self.runtime.backup_to_google_drive()
            QMessageBox.information(self, "Google Drive backup", json.dumps(result, indent=2))
        except Exception as exc:
            QMessageBox.warning(self, "Google Drive backup failed", str(exc))

    def save_settings(self):
        self.config.grace_stop_seconds=self.grace.value(); self.config.save()

    def refresh(self):
        s=self.runtime.snapshot()
        for k,v in s.items():
            if k in self.fields: self.fields[k].setText(str(v))
        self.idx_info.setPlainText(json.dumps(self.runtime.portfolio_snapshot(),indent=2))
        self.crypto_info.setPlainText(json.dumps({"accounts":[a.__dict__ for a in self.config.crypto_accounts],
                                                  "portfolio":self.runtime.portfolio_snapshot()},indent=2))
        self.ml_info.setPlainText(json.dumps({"engine":s["ml_engine"],"risk":s["risk"],"hardware":s["hardware"],
                                               "principle":"ML evidence -> risk gate -> execution"},indent=2))
        self.mt5_info.setPlainText(json.dumps({"status":s["forex"],"auto_detect":self.config.forex_auto_detect_mt5},indent=2))

    def closeEvent(self,event):
        event.ignore(); self.hide(); self.tray.showMessage("NVRA Unified","GUI closed to tray; runtime remains active.",QSystemTrayIcon.Information,2000)

    def _quit(self):
        self.runtime.request_grace_stop(self.config.grace_stop_seconds)
        QTimer.singleShot((self.config.grace_stop_seconds+2)*1000, QApplication.quit)

def run_gui() -> int:
    app=QApplication.instance() or QApplication(sys.argv)
    runtime=UnifiedRuntime()
    win=NVRAUnifiedWindow(runtime); win.show()
    return app.exec()
