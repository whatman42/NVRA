# LIVE Validation Mode (Fail-Closed)

Default: LIVE **disabled**. `LIVE_CAPITAL_BLOCKED=True` remains in force.

## States

| State | Meaning |
|-------|---------|
| DEMO | Paper/demo; LIVE arm rejected |
| LIVE_DISABLED | Default LIVE path |
| LIVE_READY | All prerequisites true; not armed |
| LIVE_ARMED | Prerequisites + explicit operator ARM |
| SAFE_MODE | Fault; LIVE blocked |

Module: `god.live.authorization.LiveAuthorizationGate`

## Prerequisites (all required for LIVE_READY)

operator authorization · license · device · credentials · broker · state loaded · reconciliation · risk governor · startup READY · explicit `arm()`

## Warning

**LIVE can produce real transactions.** Unit tests use mocks only.
