"""Telegram menu definitions and command mapping."""

from __future__ import annotations

MENU_BUTTONS: list[tuple[str, str]] = [
    ("💰 SALDO", "saldo"),
    ("📊 PORTFOLIO", "portfolio"),
    ("📈 POSITIONS", "positions"),
    ("📋 ORDERS", "orders"),
    ("🤖 ML STATUS", "ml_status"),
    ("🔎 OPPORTUNITIES", "opportunities"),
    ("❤️ SYSTEM HEALTH", "system_health"),
    ("🛡️ RISK STATUS", "risk_status"),
    ("🔄 RECOVERY STATUS", "recovery_status"),
    ("💸 CASHOUT", "cashout"),
    ("🚨 EMERGENCY STOP", "emergency_stop"),
    ("⚙️ SETTINGS", "settings_view"),
]


def parse_command(text: str) -> str | None:
    """Map user text / callback to control command id."""
    t = (text or "").strip().lower()
    if t.startswith("/"):
        t = t[1:]
    aliases = {
        "saldo": "saldo",
        "balance": "saldo",
        "portfolio": "portfolio",
        "positions": "positions",
        "orders": "orders",
        "ml": "ml_status",
        "ml_status": "ml_status",
        "opportunities": "opportunities",
        "health": "system_health",
        "system_health": "system_health",
        "risk": "risk_status",
        "risk_status": "risk_status",
        "recovery": "recovery_status",
        "recovery_status": "recovery_status",
        "cashout": "cashout",
        "emergency": "emergency_stop",
        "emergency_stop": "emergency_stop",
        "settings": "settings_view",
        "start": "system_health",
        "help": "settings_view",
    }
    # button labels
    for label, cmd in MENU_BUTTONS:
        if t == label.lower() or cmd in t:
            return cmd
    return aliases.get(t)
