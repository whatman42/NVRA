# Invariant Coverage Matrix

Focus invariants from CORE_INVARIANTS.md.

| Invariant | Current tests (examples) | Evidence | Coverage | Fault inject? | Property test? | Model check? | Mutation? | Risk if violated | Priority |
|-----------|--------------------------|----------|----------|---------------|----------------|--------------|-----------|------------------|----------|
| INV-001 LIVE preconditions | live authorization / autonomous tests | `god/live/*`, tests | PARTIAL | Yes | Yes | Yes (FSM) | Yes | S1 | P0 |
| INV-002 no order from UNKNOWN | institutional execution_state | `execution_state.py` | PARTIAL | Yes | Yes | Yes | Yes | S1 | P0 |
| INV-003 ML cannot raise ceiling | design separation; risk_gate | `god/ml/risk_gate.py`, RiskEngine | PARTIAL | Yes | Yes | Limited | Yes | S1 | P0 |
| INV-004 SAFE_MODE blocks entries | RiskEngine + autonomous | risk engine, live runtime | PARTIAL–GOOD | Yes | Yes | Yes | Yes | S1 | P0 |
| INV-008 idempotent orders | paper portfolio, bus dedup | paper, bus, loop | PARTIAL | Yes | Yes | Limited | Yes | S1 | P0 |
| INV-010 fallback not live | control_plane tests | fallback.py, tests | GOOD | Yes | Yes | Limited | Yes | S1 | P0 |
| INV-006 GUI isolation | `test_gui_fault_isolation.py` | tests | GOOD | Yes | Limited | No | Yes | S2 | P1 |
| INV-009 heartbeat ≠ revoke | admin dashboard tests | dashboard derive_* | GOOD | Yes | Yes | No | Yes | S2 | P1 |
| INV-012/013 promotion integrity | compute provider tests | validation.py | GOOD | Yes | Yes | No | Yes | S1 | P1 |
| INV-014 tenant isolation | admin dashboard tests | rbac/api | GOOD | Yes | Yes | No | Yes | S1 | P1 |
| INV-016 event dedup | bus unit behavior | bus.py | PARTIAL | Yes | Yes | No | Yes | S2 | P1 |
| INV-018 clock rollback | control plane tests | evaluate_offline | GOOD | Yes | Yes | No | Yes | S1 | P1 |
| INV-007 recon before READY | startup stages | startup docs/code | PARTIAL | Yes | Limited | Yes | Yes | S1 | P0 |
| INV-022 checkpoint fail-closed | sparse | stores | WEAK | Yes | Yes | No | Yes | S1 | P0 |

**Coverage labels:** GOOD = automated tests exist; PARTIAL = some tests/logic; WEAK = mostly design.
