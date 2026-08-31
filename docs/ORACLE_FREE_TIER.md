# Oracle Free Tier — NVRA Headless

**Product:** NVRA · **Developer:** NUNG

```bash
sudo bash deploy/oracle/install.sh
sudo systemctl enable --now nvra
journalctl -u nvra -f
```

Service user `nvra`, data `/var/lib/nvra` (0700), env `/etc/nvra/nvra.env` (0600).  
No secrets in repository. LIVE fail-closed until policy + prechecks PASS.
