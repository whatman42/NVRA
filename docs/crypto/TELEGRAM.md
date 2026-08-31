# Telegram

Menu: SALDO, PORTFOLIO, POSITIONS, ORDERS, ML, OPPORTUNITIES, SYSTEM HEALTH, RISK, RECOVERY, CASHOUT, EMERGENCY STOP, SETTINGS.

Passive commands: authorized chat id. Critical: PIN (PBKDF2 verifier, lockout, session timeout). Never send PIN in `/cashout … PIN:123456`.

Notifications via `NotifyQueue` priorities P0–P3; aggregation; rate limit; Retry-After. Telegram outage does not stop trading.
