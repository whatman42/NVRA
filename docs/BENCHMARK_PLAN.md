# NVRA Benchmark Plan

**Rule:** no invented numbers. Collect baselines on a named machine profile first.

## Suite

| ID | Metric | Method (sketch) | Notes |
|----|--------|-----------------|-------|
| B01 | Startup latency to READY | timed composition root (PAPER) | cold vs warm |
| B02 | Event throughput | EventBus publish/consume loop | synthetic events |
| B03 | Decision latency | decision engine on fixed batch | p50/p95 |
| B04 | Inference latency | single-model + ensemble | CPU first |
| B05 | Risk evaluation latency | RiskEngine.evaluate batch | |
| B06 | Paper execution latency | N simulated orders | |
| B07 | Checkpoint write/read | institutional CheckpointStore | size sweep |
| B08 | Recovery time | kill + restart to READY | |
| B09 | RSS memory | steady RUNNING paper | |
| B10 | CPU% | steady + inference spike | |
| B11 | Fault recovery success | chaos scenario pass rate | |
| B12 | Duplicate-order prevention | replay attack rate | |
| B13 | Stale-state prevention | injected stale snapshots | |
| B14 | Deterministic replay consistency | hash equality | |
| B15 | Calibration quality | Brier/ECE pre/post | |

## Reporting

Machine: CPU model, RAM, OS, commit SHA, Python version, profile (LOW_END/…).  
Store raw JSON timings under `artifacts/benchmarks/` (local only; not secrets).
