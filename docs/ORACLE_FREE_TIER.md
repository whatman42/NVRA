# Oracle Free Tier — NVRA Headless

**Product:** NVRA · **Developer:** NUNG  

```bash
sudo bash deploy/oracle/install.sh
sudo systemctl enable --now nvra
```

Data: `/var/lib/nvra` (0700). Env: `/etc/nvra/nvra.env` (0600).  
LIVE fail-closed. MT5 not available on Linux.
