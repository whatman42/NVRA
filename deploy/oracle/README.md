# NVRA on Oracle Free Tier (Linux headless)

**Product:** NVRA  
**Developer / Publisher:** NUNG  

NUNG is the **developer identity only** — never a default username, password, or API key.

Oracle runs the **same** Python core as local Linux (not a separate trading engine).

## Broker note

| Platform | Broker path |
|----------|-------------|
| Windows | MetaTrader5 + CCXT |
| Linux / Oracle | **CCXT / non-MT5 only** — no Windows MT5 terminal |

## Install

```bash
sudo bash deploy/oracle/install.sh
sudo systemctl enable --now nvra
systemctl status nvra
journalctl -u nvra -f
```

## Paths

| Path | Mode | Purpose |
|------|------|---------|
| `/opt/nvra` | 0755 | App + venv |
| `/var/lib/nvra` | 0700 | `NVRA_DATA_DIR` |
| `/etc/nvra/nvra.env` | 0600 | Environment (no secrets in git) |

LIVE is fail-closed until administrative policy + all safety prechecks PASS.
