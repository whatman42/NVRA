# GitHub Reference Audit — V8 Ready

Baseline: `NVRA-UNIFIED-INSTITUTIONAL-V7-FINAL-HARDENED-GOOGLE-AUTH-V8-READY.zip`

This review uses public repositories as architectural references. No repository code is copied into NVRA. Patterns are reimplemented behind NVRA's own contracts and risk boundaries.

## References reviewed

- `freqtrade/freqtrade` — strategy/dataflow separation, dry-run vs live operational parity, monitoring/control surfaces, and explicit backtest-vs-forward-test caveats.
- `polakowo/vectorbt` — vectorized research/backtesting orientation and separation of research analytics from runtime execution.
- `hudson-and-thames/mlfinlab` — purged cross-validation and combinatorial purged validation concepts for financial time series.
- `landtml/purgedcv` — leakage-aware CPCV/embargo API design and emphasis on empirical leakage tests.

## Implemented in NVRA

1. Offline CPCV with embargo and label-aware purging: `god/research/validation/cpcv.py`.
2. PBO diagnostic over CPCV train/test matrices: `god/research/validation/overfitting.py`.
3. Deflated Sharpe probability diagnostic with multiple-trial adjustment: `god/research/validation/overfitting.py`.
4. Validation is explicitly offline/model-governance only; it is not imported by the daily execution path.
5. Existing NVRA idempotency, reconciliation, risk ceilings, circuit breakers, audit ledger and Telegram control surfaces remain authoritative.

## Deliberately not copied

- Exchange-specific strategy rules.
- Fixed risk constants from third-party bots.
- Proprietary indicators or model parameters.
- Runtime assumptions that conflict with IDX/BEI constraints.
- Third-party live-order semantics that bypass NVRA reconciliation.

## Evidence

The reference material confirms the value of separate signal/data/order stages, forward-testing, monitoring, and leakage-aware validation. NVRA retains these concepts while keeping capital authority in its own Governor/Risk/Execution contracts.
