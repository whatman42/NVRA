# Stage 2.3 Gap Matrix

## Handler inventory

| Handler | Engine | Status | Reachable |
|---------|--------|--------|-----------|
| CuriosityHandler | CuriosityEngine | REAL | yes |
| ResearchHandler | ResearchEngine + ExperimentEngine | REAL | yes |
| StrategyHandler | StrategyRegistry | REAL | yes |
| DriftRegimeHandler | DriftEngine + RegimeEngine | REAL | yes |
| PolicyCapitalHandler | PolicyEngine + CapitalSafetyEngine | REAL | yes |
| RealityRCAHandler | RealityGapEngine + RCAEngine | REAL | yes |
| ShadowHandler | RealityGapEngine | REAL | yes |
| CognitiveLoopHandler | CognitiveLoopEngine | OPTIONAL | not required for S2 path |

## Surfaces

| Surface | Status | Notes |
|---------|--------|-------|
| Multi-handler real engines | PASS | 100/100 deterministic |
| Worker/dispatcher | PASS | |
| RiskEngine | PASS | REAL_PRODUCTION |
| ExecutionStore | PASS | Stage 2.1 |
| Recovery B1–B6 | PASS | Stage 2.1 |
| run_startup PAPER | PASS | REAL_PRODUCTION |
| NVRA.exe GUI composition | UNOBSERVABLE | CLI smoke ≠ full GUI composition |
| Process-level EXE restart | UNOBSERVABLE | Linux host |
| External LLM research | N/A | not used; no fixture claim as real |

**Verdict:** GO-MORE-DATA (NVRA.exe full GUI composition remains material gap)
