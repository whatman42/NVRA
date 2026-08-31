# Dual-Platform Deployment — NVRA

**Product:** NVRA  
**Developer / Publisher:** NUNG  

NUNG is the developer/publisher identity. It is **never** a default login username or password.

## Shared core

One codebase drives both platforms: autonomous runtime (`--autostart --headless`), policy (no secrets), safety gate / LIVE fail-closed, reconciliation, risk, governor, recovery, SAFE_MODE.

Platform-specific: packaging, launcher, service/autostart, credential backend, optional GUI (Windows).

## Windows

| Item | Value |
|------|--------|
| Executable | **`NVRA.exe`** |
| Spec | `packaging/nvra_onefile.spec` |
| Console | `False` (windowed) |
| Auto-start | `NVRA.exe --autostart --headless` |

See [WINDOWS_DEPLOYMENT.md](WINDOWS_DEPLOYMENT.md).

## Oracle Free Tier

| Item | Value |
|------|--------|
| Runtime | Headless Python + systemd |
| Unit | `deploy/oracle/nvra.service` |

See [ORACLE_FREE_TIER.md](ORACLE_FREE_TIER.md).

## LIVE

LIVE only when administrative policy is valid **and** license, credentials, broker, reconciliation, risk/governor, and safety gate all PASS. Otherwise **SAFE_MODE** — no new LIVE orders. ML cannot grant administrative authorization.
