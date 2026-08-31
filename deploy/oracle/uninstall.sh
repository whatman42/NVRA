#!/usr/bin/env bash
# Remove NVRA systemd unit. Does NOT delete /var/lib/nvra or /opt/nvra by default.
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi
systemctl stop nvra.service 2>/dev/null || true
systemctl disable nvra.service 2>/dev/null || true
rm -f /etc/systemd/system/nvra.service
systemctl daemon-reload
echo "NVRA service unit removed."
echo "Data retained: /var/lib/nvra  App retained: /opt/nvra"
echo "To purge data: rm -rf /var/lib/nvra   (irreversible)"
