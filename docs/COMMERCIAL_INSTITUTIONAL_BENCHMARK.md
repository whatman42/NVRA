# COMM-01 — Commercial & Institutional Capability Benchmark

**Research audit only · Production UNCHANGED · Baseline EXP-DR-06 `0497d80`**  
**Evidence rule:** repo code/tests/EXP-DR first; external claims only from official/primary sources.  
**Not a ranking contest** — objective parity map.

## Benchmark platforms

| Platform | Role | Primary sources |
|----------|------|-----------------|
| **QuantConnect / LEAN** | Event-driven research→backtest→live quant engine | lean.io, QuantConnect docs (pre-trade risk, framework, brokerage models) |
| **NautilusTrader** | Backtest/live parity, multi-venue, L2/book, Rust core | nautilustrader.io docs |
| **AlgoTrader / institutional OEMS** | Institutional quant + OEMS, SOR/algos, multi-venue | Vendor platform materials |
| **TT / Elwood-class EMS** | Desk EMS, execution algos, cross-venue routing | Vendor EMS pages |
| **NVRA** | Local-first governed trading research system | `god/`, `src/crypto/`, `docs/EXP_DR_*`, tests |

## NVRA status counts

| Status | Count | Meaning |
|--------|------:|---------|
| **EXISTS** | **40** | Code + credible test/runtime evidence |
| **PARTIAL** | **70** | Present but incomplete vs institutional bar |
| **MISSING** | **14** | Not found in repo as product capability |
| **SUPERIOR** | **12** | NVRA stronger on governance/science/fail-closed |
| **UNKNOWN** | **0** | Insufficient evidence |
| **Total** | **136** | Across taxonomy A–L |

Machine-readable: `research/results/commercial_capability_matrix.json`

## Competitor strengths (evidence-based)

### QuantConnect / LEAN
- Streaming event-driven algorithm manager; universe selection; brokerage/fee/margin models.
- Algorithm framework: Alpha → Portfolio Construction → Risk Management → Execution.
- Pre-trade checks (tradable, hours, price, size, buying power).
- Broad data + multi-asset; cloud/local CLI optimize/backtest/live.

### NautilusTrader
- Same strategy code backtest↔live; multi-venue; nanosecond data; order book/L2 tutorials.
- Advanced order types/TIF; execution algorithms; Rust-native performance core.
- Portfolio/cache/message-bus architecture; reconciliation concepts in live docs.

### AlgoTrader / OEMS class
- Institutional OEMS narratives: blotter, live vs sim, reconciliation, compliance logging.
- SOR / execution algos / multi-venue crypto+tradFi (vendor claims).

### TT / Elwood-class EMS
- Desk-centric EMS: cross-venue routing, TWAP/POV-style algos, fill oversight.

## WHAT NVRA ALREADY DOES BETTER

1. **Scientific verification packaging** — seeds, dataset/config hashes, git SHA, E0–E4 evidence levels (EXP-DR program).
2. **Authority boundary clarity research** — path-scoped dual stack; dual computation ≠ dual owner on one sink (EXP-DR-04.3).
3. **Fail-closed pre-trade data quality** — STALE/INVALID/UNKNOWN veto (RiskEngine + EXP-DR-05/06).
4. **Idempotent execution intents** — deterministic `client_order_id` + store (INV-008 PASS).
5. **ML cannot raise risk ceiling** — INV-003; promotion gates; uncertainty not wired as authority increase.
6. **Offline signed fallback design** — `evaluate_offline` → paper-only, `live_trading=False` (INV-010 component).
7. **Local-first dual platform** — Windows one-file + Linux/Oracle headless contracts.
8. **Immutable execution gate** — `ExecutionEngine` requires `RiskDecision.APPROVED`.
9. **CPCV/PBO offline governance utilities** — `god/research/validation`.
10. **Research scoreboard discipline** — explicit HOLD/GO-MORE-DATA vs fake production-ready claims.

## WHAT COMMERCIAL/INSTITUTIONAL SYSTEMS STILL DO BETTER

1. **Market data breadth & corporate actions** (LEAN/QC equity stack).
2. **Backtest↔live code parity at scale** (Nautilus, LEAN).
3. **L2/L3 book & microstructure simulation** (Nautilus).
4. **Productized execution algorithms & SOR** (AlgoTrader/TT/Elwood class).
5. **Institutional multi-broker connectivity** at venue scale.
6. **Portfolio optimization / CVaR toolchains** as products.
7. **Desk OMS/EMS UX** (blotter, allocations, compliance workflows).
8. **Process-level HA/MTTR as SRE practice** (NVRA process MTTR still NOT OBSERVABLE).
9. **Managed cloud research/optimize farms** (QC cloud).
10. **Fill-quality / TCA analytics products**.

## Safety non-negotiables (adoption filter)

Any capability that enables Risk Governor/RiskEngine bypass, SAFE_MODE bypass, reconciliation bypass, risk ceiling raise by ML/agent, LIVE via fallback, RBAC/license bypass, or direct agent/LLM order authority → **REJECT**.

## Limits of this benchmark

- External platform maturity from **official docs/vendor materials**, not independent penetration tests.
- NVRA ratings prefer **code/test/EXP-DR** over README claims.
- COMM-01 does **not** implement features.
