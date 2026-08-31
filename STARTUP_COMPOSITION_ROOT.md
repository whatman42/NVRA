# NVRA Startup Composition Root

## Purpose

`src/crypto/runtime/startup.py` is the explicit startup composition root. It orchestrates existing subsystem boundaries without moving trading, risk, execution, broker, or recovery business logic into the runtime layer.

## Startup state machine

```text
INIT
  ↓
LICENSE_CHECK
  ↓
LOAD_STATE
  ↓
BROKER_CONNECT
  ↓
RECONCILIATION
  ↓
RISK_GOVERNOR
  ↓
READY
  ↓
RUNNING
```

Every stage is logged and bounded by five attempts. A stage failure enters `SAFE_MODE`, waits briefly, and retries. Exhaustion leaves startup in `SAFE_MODE` and returns a non-zero result.

## Recovery

The existing `SafeModeController` is the safety boundary. A successful retry may clear SAFE_MODE only through its existing exit gates. The composition root never mutates `RiskPolicy` and never submits orders.

## Stage responsibilities

- **License/device:** `god.licensing.guard.check_device`.
- **Load state:** `crypto.runtime.migrate.open_and_migrate`.
- **Data/broker:** configured adapter from `crypto.exchanges.factory`; with no exchange configured, startup remains PAPER-safe/offline.
- **Reconciliation:** explicit stage boundary. The default root does not fabricate portfolio state; hosts with a persisted/local `PortfolioSnapshot` can inject the existing `crypto.portfolio.reconcile` operation.
- **Risk/governor:** initializes the existing `crypto.risk.engine.RiskEngine`, `RiskPolicy`, and `crypto.governor.engine.ResourceGovernor` independently.
- **READY/RUNNING:** reached only after all required stages return successfully.

## Compatibility

`crypto.runtime.entrypoint._boot()` remains present and delegates to `run_startup()`. The public `main()` and `run_application()` APIs are unchanged. `--live` remains explicit and does not bypass production gates.

## Configuration

Optional environment variables:

- `NVRA_LICENSE_ACCOUNT_ID`
- `NVRA_LICENSE_SERVICE_URL`
- `NVRA_EXCHANGE_ID`
- `NVRA_EXCHANGE_ACCOUNT_ID`
- `NVRA_EXCHANGE_SANDBOX`

No new third-party dependency was introduced.
