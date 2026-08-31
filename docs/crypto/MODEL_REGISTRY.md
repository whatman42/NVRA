# Model Registry

Local filesystem registry (`index.json` + artifacts).

## Lifecycle

```
CANDIDATE → VALIDATED → ACTIVE
                     ↘ CANARY (limited observation only)
ACTIVE → RETIRED
any → INVALID (fail closed)
```

- Activate only VALIDATED / CANARY / ACTIVE.
- Rollback: most recent VALIDATED/RETIRED for algorithm.
- CANARY never drives execution path alone.
- Remote/global models must pass local validation before activation (prepared; no federation yet).

## Compatibility

Feature schema, algorithm, artifact integrity checked. Schema mismatch → fail closed.
