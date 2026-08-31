# Oracle Production Validation — NVRA

**Product:** NVRA · **Developer:** NUNG  

Oracle Free Tier is a **Linux deployment** of the same NVRA core. It is not a separate trading engine.

## Verified on audit host (Linux)

- `requirements-linux.txt` + `pip check`
- headless entry `--autostart --headless`
- autonomous PAPER → RUNNING; broker fail → SAFE_MODE
- deployment contract pytest
- systemd unit static review (non-root, Restart=on-failure, NVRA_DATA_DIR)

## NOT VERIFIED without Oracle VM

- actual `install.sh` on Free Tier
- reboot persistence on Oracle
- 24h soak
- LIVE capital

## Install

```bash
sudo bash deploy/oracle/install.sh
sudo systemctl enable --now nvra
journalctl -u nvra -f
```

## Broker

Linux/Oracle: CCXT / non-MT5 only. MetaTrader5 is Windows-only.
