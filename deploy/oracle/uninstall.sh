#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi
systemctl stop nvra.service 2>/dev/null || true
systemctl disable nvra.service 2>/dev/null || true
rm -f /etc/systemd/system/nvra.service
systemctl daemon-reload
echo "NVRA service unit removed. Data under /var/lib/nvra retained."
