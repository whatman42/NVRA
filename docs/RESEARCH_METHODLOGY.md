# Research Methodology

## Experiment metadata schema (required)

```json
{
  "experiment_id": "EXP-DR-01",
  "git_commit": "sha",
  "environment": {"os": "...", "python": "...", "deps_hash": "..."},
  "dataset_hash": "...",
  "config_hash": "...",
  "seed": 0,
  "model_artifact_hash": null,
  "input_hash": "...",
  "output_hash": "...",
  "timestamp_utc": "...",
  "metrics": {},
  "result": "PASS|FAIL|INCONCLUSIVE",
  "status": "completed"
}
```

## Quality gates

- Pre-register metrics and PASS/FAIL thresholds **before** run.
- Report confidence intervals where Bernoulli or continuous metrics allow.
- Distinguish **statistical** vs **practical** significance.
- Any safety invariant violation → automatic **FAIL** (not INCONCLUSIVE).
- No performance claims without this metadata package.

## Reproducibility

- Fixed seeds; record numpy/python hash environment.
- Prefer synthetic data with generator version hash.
- Store artifacts outside secrets paths.

## Ethics / safety

- No real capital in L0–L6 research ladder.
- SAFETY-CRITICAL semantic changes require separate review board process (out of band).
