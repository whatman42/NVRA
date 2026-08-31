# NVRA V7 Deep Engineering Audit

## Scope

The V7 source-of-truth archive was unpacked and audited file-by-file using deterministic AST parsing and repository scans. The audit covers syntax, imports/dependencies, duplicate implementations, unreachable statements, internal reachability, build workflow consistency, execution surfaces, repository hygiene and migration portability.

## Hard gates

- Every Python source file must parse successfully.
- Every external runtime import must be declared in `requirements.txt`.
- No generated `.pyc`, `__pycache__` or `.pytest_cache` may ship.
- No workflow may accidentally publish the legacy `NVRA.exe` name when the canonical product is `NVRAFX.exe`.
- Non-trivial duplicate function bodies are rejected.
- Secret-looking files are rejected.
- Live execution remains fail-closed and requires explicit authorization outside the default product configuration.

## Orchestration policy

The declared product flow is:

`data → quality → features/decision → ML governor → regime → signal governor → risk governor → execution contract → portfolio/accounting → audit/telemetry → notifications`

Research-only and compatibility modules are retained when they are covered by tests or documented subsystem contracts; they are not treated as daily-path dependencies merely because they exist in the repository.

## Migration invariant

The migration package preserves runtime state, order journal, portfolio state and model artifacts when present. Credentials are excluded. Import verifies every checksum before replacement and must be followed by reconciliation. A mismatch cannot be auto-resolved into a new order.
