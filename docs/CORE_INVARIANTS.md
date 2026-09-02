# NVRA Core Invariant Candidates

Evidence-oriented; severity S1 (safety-critical) … S3 (quality).

| ID | Statement | Location (examples) | Enforcement today | Testability |
|----|-----------|---------------------|-------------------|-------------|
| INV-001 | No LIVE order without all preconditions true | `god/live/*`, authorization gates | Fail-closed arming | High |
| INV-002 | Recovery must not invent orders from stale UNKNOWN state | `god/institutional/execution_state.py` | Partial | High |
| INV-003 | ML output cannot raise immutable risk ceiling | risk engines + ML risk_gate | Policy separation | High |
| INV-004 | SAFE_MODE blocks new risk-increasing entries | `RiskEngine`, autonomous runtime | Implemented | High |
| INV-005 | Paper path must not require broker credentials | paper/virtual execution | Implemented | High |
| INV-006 | GUI failure must not stop core supervisor | `tests/test_gui_fault_isolation.py` | Tested | High |
| INV-007 | Reconciliation precedes READY after restart | startup state machine | Staged; completeness varies | Medium |
| INV-008 | Duplicate client order ids are rejected/idempotent | execution models / paper portfolio | Partial | High |
| INV-009 | Heartbeat timeout ≠ license revoke | control_plane dashboard | Implemented | High |
| INV-010 | Control-plane fallback cannot enable live trading | `god/control_plane/fallback.py` | Implemented | High |
| INV-011 | Secrets never in YAML/setup state/logs | credentials, wizard, sanitize | Implemented + tests | High |
| INV-012 | Compute promotion requires artifact SHA + dataset hash | `god/ml/compute/validation.py` | Implemented | High |
| INV-013 | INTERRUPTED/UNKNOWN training never promotes | compute validation | Implemented | High |
| INV-014 | CLIENT cannot read other tenant data | control_plane RBAC | Implemented | High |
| INV-015 | Adaptive hardware profile cannot relax risk ceilings | resource profiles docs/code | Design + config | Medium |
| INV-016 | Event bus detects duplicate event ids | `god/orchestration/bus.py` | Implemented | High |
| INV-017 | Champion promotion requires governance gates | `god/ml/promotion.py` | Implemented | High |
| INV-018 | Clock rollback rejects offline fallback | control_plane evaluate_offline | Implemented | High |
| INV-019 | Withdrawal remains fail-closed | unified architecture notes | Adapter-level | Medium |
| INV-020 | Autonomous LIVE requires explicit policy + capital gate | autonomous_runtime | Implemented | High |
| INV-021 | Decision packets are risk-gated before execution authority | institutional kernel risk_gate | Partial–implemented | Medium |
| INV-022 | Checkpoint load failure → SAFE_MODE not silent continue | resilience/orchestration | Partial | Medium |
| INV-023 | Model PRIVATE scope not visible to CLIENT | control plane / registry intent | Design + partial | Medium |
| INV-024 | Paper portfolio open is idempotent for same execution | `god/paper/portfolio.py` | Implemented | High |
| INV-025 | Risk evaluation is pure w.r.t. policy inputs (no hidden globals) | RiskEngine | Mostly | Medium |

**Missing tests (research):** property-based generators for INV-001–004; differential replay for INV-008; chaos matrix coverage scores for INV-007/022.
