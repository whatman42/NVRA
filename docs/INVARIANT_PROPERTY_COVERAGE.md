# Invariant Property Coverage — Tahap 2

| Property | INV | Result | Evidence |
|----------|-----|--------|----------|
| P1 UNKNOWN cannot execute | INV-002 | **PASS** | E4 |
| P2 SAFE_MODE blocks entry | INV-004 | **PASS** | E4 |
| P3 ML cannot raise ceiling | INV-003 | **PASS** | E2+E4 |
| P4 duplicate one effect | INV-008 | **PASS** | E4 |
| P5 fallback no LIVE | INV-010 | **COMPONENT PASS** | E4; E2E UNOBSERVABLE |
| P6 unreconciled blocks | INV-002 family | **PASS** | E4 |
| P7 replay preserves outcomes | multi | **PASS** | E4 |

## Still UNOBSERVABLE

- **INV-001** full LIVE precondition E2E chain
- **INV-010** fallback → ExecutionMode.LIVE E2E wiring

UNOBSERVABLE ≠ PASS.
