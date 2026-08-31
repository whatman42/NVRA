# FINAL ORACLE FREE TIER DEPLOYMENT VALIDATION

**Product:** NVRA  
**Developer / Publisher:** NUNG (identity only — not a credential)  
**Commit tested:** `05864970a70d0eec6cc4ebcbe397cff917a0d59b`  
**Date:** 2026-08-31  

## Question answered

> Apakah NVRA siap dideploy ke Oracle Free Tier sebagai autonomous headless **PAPER/DEMO**?

**Answer:** **YES — with warnings** (deployment contract + local Linux headless verified).  
Oracle Free Tier **actual VM runtime** is **NOT VERIFIED**.  
**Real-capital LIVE** is **NOT READY**.

---

## 1. Repository integrity

| Check | Result |
|-------|--------|
| HEAD matches target | **PASS** `0586497` |
| Linux/Oracle deploy files on HEAD | **PASS** |
| Packaging diff vs Windows baseline `b52076d` | **PASS** (no packaging/workflow change) |
| Strategy/risk/execution code changed for this validation | **PASS** (no such change required) |

Commits after Windows baseline: Linux requirements, oracle install/unit, entry `NVRA_DATA_DIR` only.

---

## 2. Commands executed

```bash
git checkout main   # 05864970a70d0eec6cc4ebcbe397cff917a0d59b
export PYTHONPATH=".:src"
python -m compileall -q .
python -m pip check
bash -n deploy/oracle/install.sh
bash -n deploy/oracle/uninstall.sh
python -m pytest tests/test_linux_deployment_contract.py tests/test_autonomous_trading.py tests/crypto/registry/test_registry.py -q
python -m pytest -q
# plus local headless lifecycle simulation (PAPER / SAFE_MODE matrix)
```

---

## 3. Test results

| Suite | Result |
|-------|--------|
| compileall | **PASS** |
| pip check | **PASS** (no broken requirements) |
| bash -n install/uninstall | **PASS** |
| deployment contract + autonomous + registry | **34 passed** |
| full pytest | **817 passed, 1 skipped** (~20s) |
| skip reason | Windows integration marker (host not win32) |

---

## 4. Linux dependency parity

| Item | Result |
|------|--------|
| `requirements-linux.txt` | **PASS** — no MetaTrader5 / PySide6 / PyInstaller install lines |
| Full `requirements.txt` | MT5 platform-gated Windows; PySide6/PyInstaller for GUI/build |
| Headless entry imports | **PASS** — no GUI init on `--autostart --headless` |

### Resource WARNING (Oracle Free Tier)

| Factor | Assessment |
|--------|------------|
| torch + full ML stack | **WARNING** — heavy for ~1 GB Free Tier RAM if fully installed/loaded |
| Autonomous PAPER core | Does not require loading all ML models at boot if unused |
| Recommendation | Prefer `requirements-linux.txt`; monitor RSS after first start on real VM |

---

## 5. Systemd / deploy audit (static)

| Check | Result |
|-------|--------|
| Section syntax [Unit]/[Service]/[Install] | **PASS** |
| StartLimit* in [Unit] | **PASS** |
| User=nvra (non-root) | **PASS** |
| Restart=on-failure, RestartSec=30 | **PASS** |
| ExecStart `--autostart --headless` | **PASS** |
| NVRA_DATA_DIR=/var/lib/nvra | **PASS** |
| EnvironmentFile optional `/etc/nvra/nvra.env` | **PASS** |
| No secrets in unit Environment= | **PASS** |
| install.sh 0700 data / 0600 env | **PASS** |
| env.example no passwords/api keys | **PASS** |
| systemd-analyze on host | **NOT VERIFIED** (not available / not Oracle) |

---

## 6. Headless startup (local Linux simulation)

| Scenario | Result |
|----------|--------|
| PAPER → RUNNING | **PASS** (simulated) |
| Process restart + policy reload | **PASS** (simulated) |
| No GUI / no DISPLAY required | **PASS** |
| NVRA_DATA_DIR honored | **PASS** (code path) |

**Oracle Free Tier actual process start:** **NOT VERIFIED**

---

## 7. SAFE_MODE / fail-closed (simulated)

| Failure injection | Result |
|-------------------|--------|
| broker unavailable | SAFE_MODE |
| credentials invalid | SAFE_MODE |
| reconciliation fail | SAFE_MODE |
| risk/governor fail | SAFE_MODE |
| license fail | SAFE_MODE |
| corrupt policy | load → None (fail-closed) |
| missing policy | load → None |

**Status:** **PASS** (simulation only)

---

## 8. Autonomous persistence

| Check | Result |
|-------|--------|
| Policy stores mode without secrets | **PASS** |
| FORBIDDEN_KEYS includes password/api_key/token/… | **PASS** |
| LIVE not auto-enabled by restart alone | **PASS** (design + sim) |

---

## 9. LIVE safety (read-only)

| Check | Result |
|-------|--------|
| LiveCapitalGate default blocked | **PASS** (`blocked=True`) |
| No LIVE bypass env/CLI added | **PASS** |
| Real capital orders | **NOT READY** / not attempted |

---

## 10. Security scan (lightweight)

| Check | Result |
|-------|--------|
| env.example secrets | **PASS** (none) |
| unit file secrets | **PASS** (none) |
| curl \| bash installer | **PASS** (not used) |
| world-writable runtime dirs in scripts | **PASS** (0700/0600) |

---

## 11. Reproducibility (clean checkout)

```bash
git clone https://github.com/whatman42/nvra.git
cd nvra
git checkout 05864970a70d0eec6cc4ebcbe397cff917a0d59b
# On Oracle Linux Free Tier (operator):
sudo bash deploy/oracle/install.sh
sudo systemctl enable --now nvra
journalctl -u nvra -f
```

Actual execution of install on Oracle VM: **NOT VERIFIED**

---

## 12. Status separation

| Layer | Status |
|-------|--------|
| Local Linux runtime (this host) | **PASS** |
| Oracle deployment contract (static) | **PASS** |
| Oracle Free Tier **actual** runtime | **NOT VERIFIED** |
| Windows NVRA.exe baseline | **LOCKED / PASS** (run 33392852207) |
| Real-capital LIVE | **NOT READY** |

---

## 13. Final decision table

| Area | Result | Evidence | Risk |
|------|--------|----------|------|
| Linux headless local | PASS | pytest + sim | Low |
| requirements-linux | PASS | file audit | Low |
| systemd unit static | PASS | unit parse | Low until real enable |
| permissions design | PASS | install.sh | Low |
| SAFE_MODE sim | PASS | matrix | Low |
| LIVE fail-closed design | PASS | gate + policy | Medium if mis-operated |
| ML footprint on Free Tier | PASS WITH WARNINGS | torch heavy | Medium RAM |
| Oracle real VM | NOT VERIFIED | no VM | High until install |
| Real-capital LIVE | NOT READY | not tested | High if forced |

---

## FINAL VERDICT

**PRODUCTION READY WITH WARNINGS** for **Oracle Free Tier autonomous headless PAPER/DEMO deployment packaging**.

- **Ready to attempt** operator install on a real Free Tier VM using `deploy/oracle/install.sh`.  
- **Not** claiming the VM already ran successfully.  
- **Not** ready for real-capital LIVE.

> NVRA — Developed by NUNG  
> Same core on Linux local and Oracle target · fail-closed LIVE · MT5 Windows-only  
