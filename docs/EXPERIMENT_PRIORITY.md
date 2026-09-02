# Experiment Priority Matrix

Scores 1–5. Higher better except Difficulty/Compute/Data (higher = harder/costlier).

| EXP | Sci | Eng | Safety | Pract | Diff | Comp | Data | Repro | Pub | Tier |
|-----|-----|-----|--------|-------|------|------|------|-------|-----|------|
| Deterministic paper replay | 5 | 5 | 5 | 5 | 2 | 1 | 1 | 5 | 4 | **T0** |
| INV property pack 001–004/008 | 5 | 5 | 5 | 5 | 3 | 1 | 1 | 5 | 4 | **T0** |
| Uncertainty→risk path coverage | 5 | 5 | 5 | 5 | 3 | 1 | 1 | 5 | 5 | **T0** |
| Dual-stack concordance | 5 | 5 | 5 | 5 | 3 | 1 | 1 | 5 | 5 | **T1** |
| Chaos recovery success CIs | 5 | 5 | 4 | 4 | 3 | 2 | 1 | 4 | 4 | **T1** |
| Corrupt checkpoint fail-closed | 4 | 5 | 5 | 5 | 2 | 1 | 1 | 5 | 3 | **T1** |
| Calibration under synthetic shift | 5 | 3 | 3 | 4 | 3 | 2 | 2 | 4 | 4 | **T1** |
| OOD vs reject precision | 5 | 3 | 4 | 4 | 3 | 2 | 2 | 4 | 4 | **T1** |
| Embargo width FDR study | 4 | 2 | 2 | 3 | 3 | 2 | 3 | 4 | 4 | **T2** |
| Regime hysteresis cost | 4 | 3 | 2 | 3 | 3 | 2 | 2 | 4 | 3 | **T2** |
| Adaptive vs fixed risk shocks | 4 | 4 | 3 | 4 | 3 | 2 | 2 | 4 | 3 | **T2** |
| Latency injector microstructure | 3 | 4 | 3 | 3 | 3 | 2 | 1 | 4 | 3 | **T2** |
| Resource shed invariant | 3 | 4 | 4 | 4 | 2 | 2 | 1 | 5 | 2 | **T2** |
| Full CPCV engine study | 5 | 3 | 2 | 3 | 4 | 3 | 4 | 3 | 5 | **T3** |
| Conformal coverage guarantees | 5 | 3 | 3 | 3 | 4 | 3 | 3 | 3 | 5 | **T3** |
| Event-sourcing reducer design | 4 | 5 | 4 | 4 | 5 | 2 | 1 | 3 | 4 | **T3** |
| CVaR sim allocator | 4 | 2 | 2 | 2 | 4 | 3 | 3 | 3 | 3 | **T3** |
| Demo broker field | 2 | 4 | 3 | 5 | 4 | 2 | 2 | 2 | 2 | **T4** |
| Live capital study | 1 | 2 | 1 | 2 | 5 | 2 | 5 | 1 | 1 | **OUT** |

## Top experiment briefs (EXP-DR-01…20)

Each requires fixed seed policy, pre-registered metrics, FAIL if safety invariant violated. See DEEP_RESEARCH_PROGRAM and EXPERIMENT_CATALOG for procedures.

1. Replay equality  2. INV property  3. Uncertainty coupling  4. Dual concordance  5. Chaos recovery CI  6. Checkpoint corruption  7. Shift calibration  8. OOD precision  9. Embargo FDR  10. Regime hysteresis  11. Adaptive risk Pareto  12. Latency sim  13. Resource shed  14. Promotion mutation  15. Startup budget  16. Duplicate event  17. Shadow divergence  18. Kill-9 recovery  19. Heartbeat class  20. Fallback live-incapable

**Scientific quality gate:** predeclare PASS/FAIL thresholds; report CI; separate statistical vs practical significance; INCONCLUSIVE if power insufficient.
