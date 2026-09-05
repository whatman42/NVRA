# Stage 10 — PC Deployment Verification (PAPER / Software Only)

**Canonical binary:** `NVRA.exe`  
**Qualified HEAD:** `63727c870d003dbd75706462d90eb69c4e9a9522`  
**Windows Actions run:** [33937427462](https://github.com/whatman42/nvra/actions/runs/33937427462)  
**Artifact ID:** `9960916455`  
**Expected SHA-256:** `73E647E74866D8C4B828FE5084055CB6F7A117B00CFDBB2DE3B4A8A7CA4B57FF`

> **Scope:** software deployment verification on a real Windows PC.  
> **Out of scope:** real broker credentials, real orders, LIVE trading.  
> **Real capital:** remains **BLOCKED**.  
> **Do not** claim Production Ready for LIVE from this checklist alone.

---

## 0. Prerequisites (PC)

- [ ] Windows 10 or 11 x64
- [ ] PowerShell 5.1+ or PowerShell 7
- [ ] Folder e.g. `C:\NVRA\` writable by current user
- [ ] Optional: antivirus exclusion for `C:\NVRA\` if PyInstaller one-file is quarantined
- [ ] Internet only to download the artifact (offline OK after file is local)

---

## 1. Download artifact

1. Open https://github.com/whatman42/nvra/actions/runs/33937427462  
2. Download artifact **`NVRA-Windows`** (ID `9960916455`).  
3. Extract so you have:
   - `NVRA.exe`
   - `NVRA.exe.sha256.json` (if present)
4. Copy into e.g. `C:\NVRA\NVRA.exe`

**Do not** use `NVRAFX.exe` or `NUNG.exe` for this qualification path.

---

## 2. Verify SHA-256 (mandatory)

In PowerShell:

```powershell
Get-FileHash C:\NVRA\NVRA.exe -Algorithm SHA256 | Format-List
```

**PASS only if Hash is exactly:**

```
73E647E74866D8C4B828FE5084055CB6F7A117B00CFDBB2DE3B4A8A7CA4B57FF
```

If mismatch → **STOP**. Do not run the binary for qualification.

---

## 3. CLI smoke (no broker, no credentials)

```powershell
cd C:\NVRA
.\NVRA.exe --version
.\NVRA.exe --health
```

Expected:

| Command | Expected |
|---------|----------|
| `--version` | Exit code **0**; prints version string |
| `--health` | Exit code **0**; no secrets in output |

Record exact stdout (sanitize if any path is sensitive).

---

## 4. PAPER / headless composition

```powershell
.\NVRA.exe --headless
```

Expected:

- Exit code **0**
- Composition completes without requiring API keys
- **live=false** (or equivalent: no LIVE authorization)
- ProductionGate is **not** GO for LIVE submission
- No broker orders attempted

Optional repeat (determinism smoke):

```powershell
1..5 | ForEach-Object { $p = Start-Process .\NVRA.exe -ArgumentList '--headless' -Wait -PassThru -WindowStyle Hidden; "run=$_ exit=$($p.ExitCode)" }
```

All exits should be **0**.

---

## 5. Safety checks (observation only)

Confirm from health/logs/UI (without enabling LIVE):

| Check | Expected |
|-------|----------|
| Startup lifecycle | INIT → … → READY/RUNNING or documented safe state |
| LIVE default | **false** / disabled |
| ProductionGate | Not GO without explicit authorization |
| RiskEngine | Present / not bypassed |
| SAFE_MODE / EMERGENCY_STOP | Available |
| Automatic PAPER → LIVE | **Must not occur** |
| Credential leakage | None in console/logs |

**Do not** paste API keys, tokens, or account secrets into this report.

---

## 6. Optional process recovery (PC)

```powershell
$p = Start-Process .\NVRA.exe -ArgumentList '--headless' -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
$p2 = Start-Process .\NVRA.exe -ArgumentList '--headless' -Wait -PassThru -WindowStyle Hidden
"restart_exit=$($p2.ExitCode)"
```

Expected: restart exit **0**, still **live=false**.

---

## 7. Explicitly forbidden on this checklist

- Entering real broker credentials into the app for LIVE
- Connecting production trading API keys for order placement
- Submitting / canceling real orders
- Withdrawals or transfers
- Claiming **Production Ready (LIVE)**
- Capital escalation

---

## 8. Result table (fill on PC)

| Item | Result |
|------|--------|
| PC OS | Windows __ / build __ |
| Binary path | |
| SHA-256 match | PASS / FAIL |
| `--version` exit | |
| `--health` exit | |
| Headless PAPER exit | |
| live=false | PASS / FAIL |
| Recovery (if run) | PASS / FAIL / SKIPPED |
| Secrets in output | none / **FAIL** |
| Real order | **NOT DONE** |

**Verdict options:**

- All software checks PASS → **PAPER DEPLOYMENT VERIFIED**
- Any mismatch / secret leak / unexpected LIVE → **BLOCKED**

Real capital remains **BLOCKED**. Stages countdown phrase: **8 major stages remain**.

---

## 9. CI reference evidence (already green on HEAD)

| Surface | Run | Status |
|---------|-----|--------|
| CI | 33937427439 | success |
| Regression | 33937427441 | success |
| Security | 33937427469 | success |
| Windows | 33937427462 | success |
| NVRA.exe SHA-256 | `73E647E74866D8C4B828FE5084055CB6F7A117B00CFDBB2DE3B4A8A7CA4B57FF` | recorded |
