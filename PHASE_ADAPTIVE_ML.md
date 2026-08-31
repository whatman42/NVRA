# Zero-Config Hardware-Adaptive ML (N.U.N.G / NVRAFX)

**Status:** Phase-3 + Ops + Ops-2 + Lifecycle + Hardening + **Reliability** (state machine / transactional promotion / self-recovery / health score / freshness)  
**Safety:** PAPER / DEMO only — ML evidence only; `broker_orders_submitted=0`; LIVE blocked.

Single master technical document. Features listed are implemented and tested.

## Goal

NVRAFX runs optimally on any host without manual configuration:

| Host | Profile |
|------|---------|
| ≤ 8 GB / constrained | **CONSERVATIVE** |
| 12–16 GB | **BALANCED** (16 GB is **never** HIGH_PERFORMANCE) |
| ≥ 32 GB + strong CPU + low pressure | **HIGH_PERFORMANCE** |

Champion stays until OOS promotion gate passes. Hardware alone cannot promote.

## Modules (implemented)

| Module | Role |
|--------|------|
| hardware / model_capabilities / selector / ensemble | Zero-config adaptation |
| meta_label / retention / adaptive | Orchestration + fail-closed meta |
| registry / regime / benchmark / drift / weighting | Phase-2 |
| feature_eval / promotion / scheduler | OOS gates + event retrain |
| dataset / uncertainty / calibration / persist | Phase-3 |
| telemetry / health / audit / recovery | Ops |
| data_quality / config_validate / degradation | Ops-2 |
| lifecycle | Integrity, checksum, schema, atomic |
| manifest | Full artifact deployment manifest |
| rollback_safe | Integrity-verified rollback |
| **state_machine** | Deterministic legal transitions + audit |
| **transactional_promote** | Atomic promotion with pre/post verify |
| **recover_startup** | Full restart recovery → SAFE_ONLY if none valid |
| **compute_health_score** | Composite 0..1 advisory health |
| **freshness** | Model/dataset age → stale signals / prefer_no_trade |

## Reliability layer

### State machine
TRAINING → VALIDATED → CANDIDATE → OOS → CHALLENGER → PROMOTION_GATE → CHAMPION  
Failure → REJECTED; Champion degradation → ROLLED_BACK. Illegal transitions denied and audited.  
State persistence is crash-safe via registry atomic save. Restart yields deterministic status.

### Transactional promotion
Pre-checks: candidate present, state legal, integrity, manifest, OOS gates, calibration policy.  
Single commit of champion pointer. Post-verify. Crash before commit → old champion remains.  
No champion pointer ever left pointing at invalid artifact.

### Self-recovery
`recover_startup` / `recover_champion`: integrity + manifest + load_with_integrity.  
Corrupt/incomplete champion → previous valid champion (integrity-verified), else SAFE_ONLY / prefer_no_trade.  
Multiple champions → inconsistent → prefer_no_trade (no arbitrary pick). Auditable.

### Health score
Deterministic composite from OOS accuracy/Brier/F1, drift, data quality, calibration, uncertainty/OOD, latency, artifact integrity, block rate, confidence, model_stale, recovery_failed.  
Advisory only — never bypasses Risk Engine. Low score → DEGRADED/CRITICAL + prefer_no_trade when warranted.

### Freshness
`evaluate_freshness(model_saved_at, dataset_built_at)`:  
- soft stale (model > 7d or dataset > 3d) → status stale_*;  
- hard stale (model > 30d) → prefer_no_trade.  
Missing timestamps → unknown (not auto-fail). Wired into health/recovery signals.

## Lifecycle hardening

- `schema_version=1.0`, sha256 checksum, atomic write (temp+replace)
- `verify_artifact_integrity` / `load_with_integrity` fail-closed
- Champion protection: candidates never auto-promote; hardware never swaps champion
- Retention never deletes active champion

## Artifact manifest

`ArtifactManifest` + `validate_manifest` + `verify_manifest_against_disk` fail-closed.

## Safe rollback

`safe_rollback` / `try_rollback`: integrity-verified previous champion only. Corrupt previous → prefer_no_trade.

## Graceful degradation

FULL → REDUCED → MINIMAL → SAFE_ONLY.

## Hardware capability matrix

| Family | CONSERVATIVE (≤8 GB) | BALANCED | HIGH_PERFORMANCE |
|--------|----------------------|----------|------------------|
| numpy_logit | always | always | always |
| random_forest | always (sklearn or numpy fallback) | always | always |
| lightgbm / xgboost | if installed | if installed | if installed |
| catboost | — | if installed | if installed |
| LSTM / GRU / Transformer | disabled | disabled | if torch + GPU |

Heavy ML optional; missing deps → graceful fallback, no crash. Inference prioritized over training under resource pressure.

## Safety

- ML → evidence only; no order_send; no Policy/Risk/LiveReadiness bypass
- `LIVE-AUTHORIZED=false`, `live_authorized=false`, `broker_orders_submitted=0`

## Packaging

**Sole executable:** `NVRAFX.exe` (workflows hard-fail on NUNG.exe / NVRA.exe)

## Tests

- test_adaptive_ml / phase2 / phase3 / ops / ops2 / ml_lifecycle / ml_hardening
- **test_ml_reliability.py** — state machine, transactional promote, crash-before-commit, recovery (corrupt / both-corrupt / multi-champion), health score, freshness, optional-deps graceful, LIVE safety

## Optional dependencies

Core: numpy, psutil, cryptography, PySide6, httpx, requests, urllib3.  
Optional (runtime-guarded): lightgbm, xgboost, catboost, torch, shap, sklearn.

## Requirements policy

`requirements.txt` lists core + pytest + pyinstaller. Heavy ML stays commented optional so clean install on 8 GB hosts succeeds without GPU frameworks.
