#!/usr/bin/env bash
# Install NVRA headless service on Oracle Linux / Ubuntu-style hosts.
# Product: NVRA | Developer: NUNG
# Run as root. Does not embed secrets. Does not enable LIVE by default.
# Idempotent: safe to re-run (preserves /etc/nvra/nvra.env and data).
set -euo pipefail

PRODUCT="NVRA"
DEVELOPER="NUNG"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/nvra}"
DATA_DIR="${DATA_DIR:-/var/lib/nvra}"
LOG_DIR="${LOG_DIR:-/var/log/nvra}"
SERVICE_USER="${SERVICE_USER:-nvra}"
REPO_SRC="${REPO_SRC:-$(cd "$(dirname "$0")/../.." && pwd)}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root" >&2
  exit 1
fi

id -u "$SERVICE_USER" &>/dev/null || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"

mkdir -p "$INSTALL_ROOT" "$DATA_DIR" "$LOG_DIR" /etc/nvra
chmod 0755 "$INSTALL_ROOT"
chmod 0700 "$DATA_DIR" /etc/nvra
chmod 0755 "$LOG_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR" "$LOG_DIR"

rsync -a --delete \
  --exclude '.git' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude 'dist' \
  --exclude '.pytest_cache' \
  --exclude '*.pyc' \
  "$REPO_SRC"/ "$INSTALL_ROOT"/

python3 -m venv "$INSTALL_ROOT/venv"
"$INSTALL_ROOT/venv/bin/pip" install --upgrade pip

REQ="$INSTALL_ROOT/requirements-linux.txt"
if [[ ! -f "$REQ" ]]; then
  REQ="$INSTALL_ROOT/requirements.txt"
fi
if [[ -f "$REQ" ]]; then
  if [[ -f "$INSTALL_ROOT/constraints.txt" ]]; then
    "$INSTALL_ROOT/venv/bin/pip" install -r "$REQ" -c "$INSTALL_ROOT/constraints.txt"
  else
    "$INSTALL_ROOT/venv/bin/pip" install -r "$REQ"
  fi
fi

install -m 0644 "$(dirname "$0")/nvra.service" /etc/systemd/system/nvra.service
if [[ ! -f /etc/nvra/nvra.env ]]; then
  install -m 0600 "$(dirname "$0")/env.example" /etc/nvra/nvra.env
  chown root:root /etc/nvra/nvra.env
else
  chmod 0600 /etc/nvra/nvra.env
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
chmod 0700 "$DATA_DIR"

systemctl daemon-reload
systemctl enable nvra.service

echo "Installed $PRODUCT (Developed by $DEVELOPER)."
echo "  App:     $INSTALL_ROOT"
echo "  Data:    $DATA_DIR (0700, user $SERVICE_USER)"
echo "  Env:     /etc/nvra/nvra.env (0600)"
echo "  Service: nvra.service (headless --autostart --headless)"
echo ""
echo "Start:   systemctl start nvra"
echo "Status:  systemctl status nvra"
echo "Logs:    journalctl -u nvra -f"
echo ""
echo "LIVE remains fail-closed until policy + prechecks PASS."
echo "MT5 terminal is Windows-only; Linux uses CCXT/other non-MT5 adapters."
