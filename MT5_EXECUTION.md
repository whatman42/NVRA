# MT5 Execution Architecture

**Status:** DEMO E2E verified · LIVE readiness gate enforced · LIVE capital **BLOCKED** by default  
**Binary:** `NVRAFX.exe` only — MetaTrader 5 terminal remains **external** (never bundled).

## Architecture

```
NVRAFX.exe
  ├── ML Engine (evidence only)
  ├── Signal / Market Decision
  ├── Risk Engine
  ├── Policy Engine
  ├── Live Readiness Gate          ← authoritative, fail-closed
  ├── LiveExecutionController      ← arm / kill / submit boundary
  ├── Audit + Recovery
  └── MT5 Manager                  ← external gateway
           │
           ▼
      MT5 Terminal (terminal64.exe on host)
           │
           ▼
         Broker
```

## Separation invariants

| Rule | Enforcement |
|------|-------------|
| No `terminal64.exe` inside PyInstaller binary | packaging + CI smoke |
| No direct `order_send` from ML / AI / recovery | only `LiveExecutionController` → adapter |
| LIVE capital blocked by default | `LIVE_CAPITAL_BLOCKED=True`, `LiveCapitalGate` |
| DEMO path only for automated tests | `FakeMetaTrader5`, `allow_live_account=False` |
| Explicit operator `arm()` required | `LiveExecutionController.arm(operator_ack=...)` |

## MT5 Manager (`god/broker/mt5/manager.py`)

Production gateway: discover/validate terminal, connect/reconnect/heartbeat, account & server identity, symbol validation, market-data freshness, order path (still gated upstream), reconciliation, crash recovery snapshot, structured audit.

**NO TRADE** when: MT5 unhealthy, market data stale, account/server mismatch, symbol invalid, LIVE without allow flag, or upstream risk/policy/readiness/authorization failure.

## Execution lifecycle (DEMO)

Market data → features/ML evidence → signal → risk sizing → live readiness/preflight → operator arm → MT5Manager.is_trade_allowed → idempotent submit → retcode validation → positions → reconciliation → audit.

## Order safety

Idempotency on `client_order_id`; never treat API return as success without retcode+broker state; restart uses crash_recovery_snapshot; LIVE rejected unless allowed and capital unlocked.

## Live Readiness Gate

LIVE only if configuration valid, MT5 connected, correct account/server, symbol valid + data fresh, model valid/integrity/fresh, risk healthy, policy allows, recovery healthy, no unresolved execution state, audit healthy, **explicit manual authorization**. ML/recovery/hardware cannot arm LIVE.

## Failure modes (tested)

MT5 missing/init fail, disconnect, stale tick, invalid symbol/account/server, order reject/partial/unknown, duplicate client_order_id, model corrupt → SAFE_ONLY, risk/policy/preflight fail, live_authorized=false → all NO TRADE / BLOCKED.

## Deployment (Windows)

Install MT5 separately. Credentials via env/secure store. `NVRAFX.exe --health` must show live_authorized=false, broker_orders_submitted=0. LIVE only after manual operator authorization.

**This document does not claim LIVE READY for real-money trading.**
