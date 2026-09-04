# Stage 4.1 Gap Matrix — Unified Data & Research

| Area | Status | Label |
|------|--------|-------|
| Content hash determinism/divergence | PASS | PRODUCTION_PATH |
| DatasetSnapshot checksum immutability | PASS | PRODUCTION_PATH |
| Leakage/embargo detection | PASS | PRODUCTION_PATH |
| Data quality gates (NaN fail-closed) | PASS | PRODUCTION_PATH |
| Artifact validation / promotion gate | PASS | PRODUCTION_PATH |
| Experiment metadata reproducibility N=20 | PASS | RESEARCH_PATH |
| Research → execution boundary | PASS | PRODUCTION_PATH |
| External market data providers | UNOBSERVABLE | no credentials in CI |
| L2 / microstructure full stack | GAP | defer Stage 7 if needed |
| Full CPCV/PBO/FDR statistical certification | EXISTING modules, not full cert | scientific Stage later |
| Exact HEAD CI GREEN | pending | |

**Verdict:** GO-MORE-DATA until exact HEAD CI/Windows GREEN; external data/L2 remain non-blocking if classified.
