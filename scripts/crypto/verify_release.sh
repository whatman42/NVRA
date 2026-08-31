#!/usr/bin/env bash
# Pre-release verification on any host (dev/CI). Does not produce Windows EXE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

echo "== ruff =="
python3 -m ruff check src tests
python3 -m ruff format --check src tests
echo "== mypy =="
python3 -m mypy src
echo "== pytest =="
python3 -m pytest -q
echo "== smoke entrypoint =="
CRYPTO_HOME="$(mktemp -d /tmp/crypto-rel.XXXXXX)"
export CRYPTO_HOME
python3 -m crypto --version
python3 -m crypto --paths
python3 -m crypto --smoke
echo "== secret scan =="
python3 - <<'PY'
from pathlib import Path
from crypto.production.security import scan_tree_for_secrets
findings = scan_tree_for_secrets(Path("src"))
findings.update(scan_tree_for_secrets(Path("packaging")))
findings.update(scan_tree_for_secrets(Path("scripts")))
# filter false positives in tests if any
if findings:
    for k,v in findings.items():
        print("HIT", k, v)
    raise SystemExit(1)
print("no secrets in src/packaging/scripts")
PY
echo "== production gate software =="
python3 - <<'PY'
from crypto.production import ProductionGate, LiveDecision
g = ProductionGate(
    db_integrity=lambda: True,
    model_ok=lambda: True,
    recovery_ok=lambda: True,
    governor_ok=lambda: True,
    risk_ok=lambda: True,
    control_ok=lambda: True,
    withdrawal_status="DISABLED",
)
r = g.evaluate(exchange_verified=False)
assert r.software_green, r.summary_lines()
assert r.live_decision is LiveDecision.NOT_VERIFIED
assert g.default_mode().name == "PAPER"
print("SOFTWARE GREEN; PRODUCTION LIVE NOT_VERIFIED; default PAPER")
PY
echo "VERIFY OK"
