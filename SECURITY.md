# NVRA Security Notes

- Local control API binds to 127.0.0.1 only
- Trade routes (BUY/SELL/ORDER/ENABLE_LIVE) rejected by default gates
- No GH_PAT, broker passwords, or private keys in package
- LIVE authorization remains DENIED by default until explicit ARM + preflight PASS
- GUI is observability/control only — not execution authority
