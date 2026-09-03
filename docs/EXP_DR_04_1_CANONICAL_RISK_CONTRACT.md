# EXP-DR-04.1 — Canonical Risk Contract & Authority Boundary Study

**Design only · Production UNCHANGED · Git `646bd53`**  
**Classification: HOLD**  
**Authority ambiguity: YES**  
**Critical unsafe ownership conflict: not demonstrated**

## Objective

Reduce semantic non-isomorphism that limited EXP-DR-04 (8 comparable scenarios, 50% concordance, 9 D7) by defining a **research-only** canonical contract — without merging or modifying production engines.

## Equivalence summary

| Class | Meaning | Count |
|-------|---------|------:|
| E0 | exact | 2 |
| E1 | lossless normalize | 1 |
| E2 | approximate | 10 |
| E3 | fundamentally different | 3 |
| E4 | absent one stack | 10 |
| **Total concepts** | | **26** |

### Highlights

- **E0:** equity; max concurrent positions  
- **E2:** free_margin ↔ available_balance; quantity/lots; risk_pct; decisions  
- **E3:** exposure lots vs % equity; daily loss absolute vs %  
- **E4:** SAFE_MODE, reconciliation, DataQuality on adaptive; leverage on crypto snapshot; LIVE auth outside RiskEngine  

## Canonical contract (research-only)

Groups: `ACCOUNT_STATE`, `POSITION_STATE`, `TRADE_RISK`, `DATA_STATE`, `CONTROL_STATE`, `DECISION`  

See JSON schema artifact. **Non-goals:** not production API; no LIVE grant; no ceiling raise; no engine merge.

## Authority matrix (excerpt)

| Decision | crypto | adaptive | live | Resolution |
|----------|--------|----------|------|------------|
| Position sizing | allowed_quantity | volume | — | **UNKNOWN** |
| Portfolio exposure | max_*_pct | max_*_lots | — | **DUAL** |
| Safety gating | SafetyMode | ABSENT | safe_mode | path-split |
| Reconciliation | reconciliation_ok | ABSENT | — | crypto path |
| Data quality | DataQualityReport | ABSENT | — | crypto path |
| LIVE authorization | not in RiskEngine | — | **LiveAuthorizationGate** | god.live |
| Final order approval | executable | ok | can_submit_live | **UNKNOWN** |

## Safety invariant mapping

| INV | crypto | adaptive | live/paper |
|-----|--------|----------|------------|
| INV-001 | PARTIAL | N/A | IMPLEMENTED (live) |
| INV-002 | IMPLEMENTED | ABSENT | PARTIAL |
| INV-003 | IMPLEMENTED | IMPLEMENTED | — |
| INV-004 | IMPLEMENTED | ABSENT | live + paper |
| INV-008 | PARTIAL | N/A | PARTIAL |
| INV-010 | N/A | N/A | UNKNOWN |

ABSENT on adaptive ≠ automatic bug: adaptive is sizing-focused, not full pre-trade safety plane.

## D7 root-cause (9 from EXP-DR-04)

| | Count |
|--|------:|
| Original D7 | 9 |
| D7_RESOLVABLE | **7** |
| D7_FUNDAMENTAL | **2** |

Resolvable via research CONTROL/DATA overlays: stale/UNKNOWN/invalid, SAFE_MODE, recon, connectivity.  
Fundamental: missing-price vs SL-distance model; PaperRiskEngine third stack.

## Classification: HOLD

Contract improves future comparability; **authority still ambiguous**; no CRITICAL dual-approve path shown; **PASS not met**.

## Recommendation

- **EXP-DR-04.2 justified** (research harness + contract only)
- **No production implementation**
- Unresolved: composition-root ownership, lots↔currency, paper third path, INV-010

## Artifacts

- `research/results/exp_dr_04_1_canonical_risk_contract.json`
- `research/results/exp_dr_04_1_authority_matrix.json`
- `research/results/exp_dr_04_1_semantic_mapping.json`
