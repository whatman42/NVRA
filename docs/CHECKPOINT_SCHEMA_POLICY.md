# Checkpoint Schema Policy (Production)

**Status:** Production semantic gate **ENFORCED** on institutional lifecycle claims (P0-A).

## Scope

| Payload type | Behavior |
|--------------|----------|
| Opaque workflow (`observation`, `decision`, `risk_gated`, `executed`) | Allowed; **not** trusted READY |
| Lifecycle claim (`schema_version` / `lifecycle` / `recon_complete` / lifecycle node) | **Validated fail-closed** |

## Required fields (schema `1.0`)

- `schema_version` (str; supported: `1.0`, legacy `0.legacy`)
- `sequence` (int ≥ 0)
- `lifecycle` (enum)
- `recon_complete` (bool)
- `updated_ns` (int)

## Rules

- Malformed JSON on load → `None` (fail closed)
- READY/RUNNING without `recon_complete` → reject save; load returns `None`
- UNKNOWN / SAFE_MODE → loadable but `trusted_ready=False`, `trusted_execution=False`
- `load_trusted_ready()` only when validation grants ready trust (execution still requires RiskEngine)
- Unsupported schema version → reject

## Compatibility

- Existing opaque kernel checkpoints continue to work.
- Lifecycle states without `schema_version` treated as `0.legacy` and still must satisfy READY/recon rules.

## Modules

- `god/institutional/checkpoint_schema.py`
- `god/institutional/checkpoint.py`

## Non-goals (still open)

- OS process-kill MTTR
- INV-001 / INV-010 full E2E LIVE wiring
- Orchestration models package (separate ticket)
