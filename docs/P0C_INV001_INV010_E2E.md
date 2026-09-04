# P0-C: INV-001 + INV-010 E2E Qualification

## Commands

```bash
export PYTHONPATH=".:src"
python -m pytest tests/test_p0c_inv001_inv010_e2e.py -q
python -m pytest tests/test_checkpoint_semantic_gate.py tests/test_os_process_crash_recovery.py tests/test_p0c_inv001_inv010_e2e.py -q
python -m pytest tests/ -q --ignore=tests/research/test_phase0_harness_smoke.py
```

## Composition (production modules, no policy change)

`LiveAuthorizationGate` ∧ `ProductionGate` ∧ `RiskEngine` ∧ `CheckpointStore` ∧ `evaluate_offline`

LIVE authorization requires **all** of:

1. LiveAuthorizationGate.can_submit_live() (all LivePrerequisites + explicit ARM)
2. ProductionGate.live_decision == GO
3. RiskEngine executable (recon + not SAFE_MODE/UNKNOWN/STALE)
4. Checkpoint trusted_ready when recovery claims lifecycle authority
5. No offline fallback active (fallback never grants LIVE)

## INV-001 matrix (summary)

| Scenario | Expected | Actual |
|----------|----------|--------|
| Fully qualified path | LIVE authorized | ALLOW |
| Any missing prerequisite | REJECT | REJECT |
| Missing/invalid license | REJECT | REJECT |
| Recon incomplete / failed | REJECT | REJECT |
| SAFE_MODE | REJECT | REJECT |
| Broker unavailable | REJECT | REJECT |
| Untrusted/corrupt/semantic-invalid CP | REJECT | REJECT |
| ProductionGate NO_GO | REJECT | REJECT |
| Execution before READY | REJECT | REJECT |
| READY-like CP alone | REJECT | REJECT |

## INV-010 matrix (summary)

| Scenario | Expected | Actual |
|----------|----------|--------|
| offline / signed / corrupt / revoked fallback | live_trading=False | PASS |
| fallback during SAFE_MODE / UNKNOWN | no LIVE | PASS |
| malicious OfflineDecision(live_trading=True) | integrated path REJECT | PASS |
| repeated fallback / restart after fallback | never LIVE | PASS |

## Evidence

Machine-readable: `research/results/p0c_inv001_inv010_results.json`

## Observability gaps

- Full NVRAFX GUI operator ARM UX path not exercised in this suite
- Real exchange canary / production_live_verified remains deploy-time

## Safety

No changes to RiskEngine, SAFE_MODE, LIVE gate, fallback, ExecutionEngine, or checkpoint semantic policy.
