# COMM-01 — Commercial & Institutional Capability Benchmark

**Research audit only · Production UNCHANGED · Baseline `0497d80`**

## Purpose

Objective capability parity analysis versus commercial/institutional platforms **without** weakening NVRA governance, safety invariants, or scientific verification.

## Benchmark platforms

| Platform | Role | Primary evidence |
|----------|------|------------------|
| QuantConnect / LEAN | Event-driven research→live quant OS | lean.io, QuantConnect docs |
| NautilusTrader | Backtest/live parity, multi-venue OMS | nautilustrader.io docs |
| AlgoTrader / institutional OEMS | Institutional crypto/tradFi OEMS | vendor materials |
| TT OMS | Institutional OMS pre-trade risk, algos | tradingtechnologies.com |
| NVRA | Code + tests + EXP-DR evidence | `god/`, `src/crypto/`, `docs/EXP_DR_*` |

## Status counts (NVRA)

| Status | Count |
|--------|------:|
| EXISTS | 27 |
| PARTIAL | 45 |
| MISSING | 11 |
| SUPERIOR | 7 |
| UNKNOWN | 0 |
| **Total** | **90** |

Full matrix: `research/results/commercial_capability_matrix.json`

## WHAT NVRA ALREADY DOES BETTER

1. Scientific experiment packaging (seeds, hashes, E0–E4 evidence levels).
2. Authority boundary research (path-scoped dual-stack; EXP-DR-04.x).
3. Fail-closed risk + data-quality veto (STALE/UNKNOWN/recon/SAFE_MODE).
4. Idempotent execution intents (INV-008).
5. ML governance (promotion gates; INV-003 no ceiling raise).
6. Offline signed fallback design (paper-only; no LIVE grant).
7. Local-first dual platform (Windows/Linux headless).

## WHAT COMMERCIAL/INSTITUTIONAL SYSTEMS STILL DO BETTER

1. Market data breadth & corporate actions (LEAN/QC).
2. Backtest/live code parity at scale (Nautilus, LEAN).
3. L2/L3 book & microstructure simulation (Nautilus).
4. Institutional OMS/EMS desk workflows (TT OMS / AlgoTrader class).
5. Productized execution algorithms & SOR.
6. Portfolio optimization / CVaR toolchains.
7. Managed multi-broker connectivity at scale.
8. Process-level HA/MTTR as production SRE practice.

## Safety rule

Adoption that enables Risk Governor bypass, SAFE_MODE bypass, recon bypass, risk-ceiling raise, LIVE via fallback, RBAC bypass, direct agent orders, or LLM final authority → **REJECT**.
