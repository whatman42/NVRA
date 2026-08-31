#!/usr/bin/env bash
# Install NVRA headless service on Oracle Linux / Ubuntu-style hosts.
# Run as root. Does not embed secrets. Does not enable LIVE by default.
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
  "$REPO_SRC"/ "$INSTALL_ROOT"/

python3 -m venv "$INSTALL_ROOT/venv"
"$INSTALL_ROOT/venv/bin/pip" install --upgrade pip
if [[ -f "$INSTALL_ROOT/requirements.txt" ]]; then
  if [[ -f "$INSTALL_ROOT/constraints.txt" ]]; then
    "$INSTALL_ROOT/venv/bin/pip" install -r "$INSTALL_ROOT/requirements.txt" -c "$INSTALL_ROOT/constraints.txt"
  else
    "$INSTALL_ROOT/venv/bin/pip" install -r "$INSTALL_ROOT/requirements.txt"
  fi
fi

install -m 0644 "$(dirname "$0")/nvra.service" /etc/systemd/system/nvra.service
if [[ ! -f /etc/nvra/nvra.env ]]; then
  install -m 0600 "$(dirname "$0")/env.example" /etc/nvra/nvra.env
  chown root:root /etc/nvra/nvra.env
fi

systemctl daemon-reload
systemctl enable nvra.service
echo "Installed $PRODUCT (Developed by $DEVELOPER)."
echo "Start with: systemctl start nvra"
echo "Configure administrative policy under $DATA_DIR after first-run enrollment."
echo "LIVE remains fail-closed until policy + prechecks PASS."
