# EXP-DR-04.2 — Expanded Dual-Stack Concordance (CanonicalRiskContract_v0)

**Research-only overlay · Production UNCHANGED · Baseline `d1d66d9`**  
**Classification: HOLD**  
**Reproducibility: PASS**  
**D6: 0**

## Coverage

| Metric | Value |
|--------|------:|
| Canonical scenarios | **108** |
| Comparable | **89** |
| Non-comparable (D7) | **19** |
| Engine decision concordance (comparable) | **75.3%** |
| Overlay concordance (research policy) | **78.7%** |

Taxonomy: MATCH=67, D1=22, D7=19

## RQ answers

1. **Coverage increase?** Yes vs EXP-DR-04 (8 comparable) → 89 comparable; control/data still D7 without inventing adaptive semantics.
2. **Concordance still low?** Engine concordance **75.3%** on comparable — improved vs 50% but **below 95%** bar.
3. **Mostly intentional?** **Yes** — D1 model/limit differences among comparable.
4. **D6?** **No** (strict: no shared safety authority claimed for adaptive).
5. **Final authority determined?** **No** — still DUAL_AUTHORITY_CANDIDATE.
6. **Dual sizing real?** **YES** candidate.
7. **Lots↔currency?** **LOSSY / instrument-dependent**.
8. **Paper third path?** **YES**.
9. **Contract as future production spec?** Research-useful only — **DO NOT IMPLEMENT** without authority design.

## Authority ambiguity

**YES** — position sizing, portfolio risk units, final approval remain dual/unknown.

## Safety invariants

| INV | Result |
|-----|--------|
| INV-001 | UNOBSERVABLE |
| INV-002 | PASS crypto |
| INV-003 | PASS both surfaces |
| INV-004 | PASS crypto; N/A adaptive native |
| INV-008 | UNOBSERVABLE |
| INV-010 | UNOBSERVABLE |

Metamorphic: **20/20**

## Classification: HOLD

Concordance <95%; D1 remains; authority ambiguity persists; D6=0.

## Production integration

**DO NOT IMPLEMENT** canonical contract in production.

## Artifacts

- `research/results/exp_dr_04_2_expanded_concordance.json`
- `research/results/exp_dr_04_2_scenario_matrix.json`
- `research/results/exp_dr_04_2_disagreements.json`
- `research/results/exp_dr_04_2_authority_conflicts.json`
