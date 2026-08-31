# NVRA Dead Code Removal Log — Phase 1

Baseline: `NVRA-UNIFIED-V8-PHASE1-CLEAN-BASELINE.zip`

Scope: production Python code only. Tests/scripts/tools/docs/config were not modified. No Protocol/interface (`LifecycleManager`, `ProductionExecutionProvider`) was removed.

## Batch 1 — 10 items

| File | Baseline line | Item removed | Type | Reason | Validation |
|---|---:|---|---|---|---|
| `god/market_decision/engine.py` | 110 | `_deterministic_score` | function | Repository-wide reference search found definition only; private helper; no `getattr`/`importlib`/registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/capability/probes.py` | 89 | `list_env_path` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/ml/dataset.py` | 116 | `save_dataset_manifest` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/ml/dataset.py` | 122 | `load_dataset_manifest` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/ml/labels.py` | 49 | `forward_returns` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/ml/lifecycle.py` | 35 | `payload_sha256` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/ml/lifecycle.py` | 120 | `compute_artifact_checksum` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/ml/uncertainty.py` | 99 | `conformal_prediction_set` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `god/orchestration/validation.py` | 43 | `validate_status_name` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `src/crypto/execution/states.py` | 149 | `is_active` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |

## Batch 2 — 6 items

| File | Baseline line | Item removed | Type | Reason | Validation |
|---|---:|---|---|---|---|
| `god/accounting/corporate_actions.py` | 6 | `apply_adjustment` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `src/crypto/recovery/storage.py` | 65 | `save_checkpoint` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `src/crypto/recovery/storage.py` | 79 | `load_checkpoint` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `src/crypto/recovery/storage.py` | 84 | `append_recovery_event` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `src/crypto/runtime/compat.py` | 42 | `preserve_models_dir` | function | No repository-wide reference; no dynamic registration reference | `compileall` PASS; full suite 764 passed / 1 skipped |
| `src/crypto/ml/cache.py` | 10 | `PredictionCache` | class | No repository-wide reference; no dynamic registration reference; not a Protocol/interface | `compileall` PASS; full suite 764 passed / 1 skipped |

## Intentionally skipped

- `god/agent/protocols.py:77` — `LifecycleManager`: Protocol/interface; explicitly retained.
- `god/production_execution/models.py:126` — `ProductionExecutionProvider`: Protocol/interface; explicitly retained.
- `god/bridge/errors.py:34` — `HealingError`: exception type; no in-repo use, but external API/consumer contract cannot be ruled out, so retained for manual review.
- `god/broker/mt5/errors.py:12` — `MT5ReconciliationError`: exception type; no in-repo use, but external API/consumer contract cannot be ruled out, so retained for manual review.

The remaining lower-confidence variable/constant and unused-import candidates from the audit were not removed in this pass.

## Final status

- Dead-code definitions removed: **16**
  - Functions: **15**
  - Classes: **1**
- Protocol/interfaces removed: **0**
- Exception classes removed: **0**
- Business/trading/risk logic intentionally unchanged.
- `python -m compileall -q .`: **PASS** after each batch.
- Full pytest collection: **765 tests**.
- Full pytest result after Batch 1: **764 passed, 1 skipped**.
- Full pytest result after Batch 2: **764 passed, 1 skipped**.
- The pytest process in this Linux environment remained alive during post-session teardown after reporting 100%; the captured pytest session summary was nevertheless `exitstatus=0`, `764 passed`, `1 skipped`. No test failure occurred.
