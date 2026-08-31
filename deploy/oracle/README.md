# NVRA on Oracle Free Tier (Linux headless)

**Product:** NVRA  
**Developer / Publisher:** NUNG  

NUNG is the **developer identity only**. It is **not** a default username, password, or credential.

## Install

```bash
sudo bash deploy/oracle/install.sh
sudo systemctl start nvra
sudo systemctl status nvra
```

## Auto-start after reboot

```bash
sudo systemctl enable nvra
```

Flow: systemd → NVRA --autostart --headless → policy → prechecks → RUNNING  
or SAFE_MODE if preconditions fail.

## Paths

| Path | Mode | Purpose |
|------|------|---------|
| `/opt/nvra` | 0755 | App + venv |
| `/var/lib/nvra` | 0700 | Data / policy |
| `/etc/nvra/nvra.env` | 0600 | Environment (no secrets in git) |

LIVE remains fail-closed until administrative policy + all safety prechecks PASS.
