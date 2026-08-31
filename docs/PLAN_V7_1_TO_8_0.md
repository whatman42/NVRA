# NVRA V7.1 → V8.0 Engineering Plan

## V7.1 — Identity, device binding, backup and recovery
- Google OAuth 2.0; never request/store a Google password.
- Optional local TOTP (Google Authenticator compatible).
- Cryptographic installation/device identity.
- One-active-device policy through a configured HTTPS license service.
- Remote device revocation; offline/failed old PC does not block replacement once revoked server-side.
- Encrypted, checksummed migration bundles and Google Drive transport.
- Restore models, ML state, portfolio, journal and data without retraining from zero.

## V7.2 — Autonomous recovery
- Same DEMO/REAL state machine.
- SAFE_MODE on uncertain execution state.
- Exponential backoff, circuit breakers, atomic checkpoints.
- Reconciliation of orders, fills, positions, balances and journal before resume.

## V7.3 — Broker certification
- E2E DEMO certification and 2–4 week soak test.
- Partial fills, rejects, timeout, reconnect, restart and duplicate-order scenarios.

## V7.4 — Quant validation
- Walk-forward, CPCV, PBO, DSR, bootstrap/Monte Carlo, costs and liquidity-aware validation.
- Champion/Challenger governance.

## V7.5 — Governor 2.0
- Adaptive signal thresholds and sizing.
- Governor may reduce risk or loosen filters gradually, never raise immutable risk ceilings.

## V7.6 — Portfolio intelligence
- Correlation, sector/factor concentration, HHI, liquidity and portfolio heat.

## V7.7 — IDX market intelligence
- Configurable tick/lot/session/ARA-ARB/corporate-action rules with effective dates.

## V7.8 — Operations
- Telegram clickable control plane, health, alerts, audit, migration and backup controls.

## V7.9 — Certification
- Full test, chaos, soak, security, reproducible-build and disaster-recovery evidence.

## V8.0 — Production intelligence
- Controlled online learning, feature selection, retraining, regime detection, execution optimization and multi-strategy capital allocation.

### Invariants
1. LIVE/REAL is never activated by recovery or cloud restore.
2. DEMO and REAL use the same reconciliation/recovery state machine.
3. Unknown broker outcomes are never treated as failed.
4. Risk ceilings are immutable from ML/Governor actions.
5. Secrets are never included in migration bundles or source control.
