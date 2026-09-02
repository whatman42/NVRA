# NVRA Research Gaps (Evidence-Based)

## Implemented (code present)
- RiskEngine + SafetyMode; capital adaptive risk; paper portfolio + drawdown halt
- Institutional kernel, typed AgentEvidence/DecisionPacket, MessageBus
- ML: calibration (Platt/Isotonic), regime, drift, OOD, promotion, compute integrity gates
- Orchestration EventBus + duplicate ids; resilience RuntimeSupervisor
- Autonomous runtime state machine; live authorization fail-closed
- Control plane Ed25519 licenses, RBAC, signed offline fallback
- GUI fault isolation test; chaos_v7 scenario module

## Partially implemented
- Full reconciliation completeness across brokers after every restart path
- Multi-agent debate quality vs single analyst (structure > measured efficacy)
- Exactly-once execution semantics under all failure modes
- Unified single risk contract across `god` and `src/crypto` stacks
- End-to-end event sourcing (bus exists; not full ES/CQRS store)

## Design / docs heavier than code
- Some Nautilus/Tauric integration narrative beyond kernel contracts
- Full Cloudflare→Vercel→Neon production (templates only)

## Not implemented / research gaps
- Formal vector/Lamport clocks for multi-host ordering
- Property-based + mutation testing as standard CI gates
- CVaR/ES optimizers as first-class portfolio controls (beyond DD thresholds)
- Online continual learning with guaranteed non-increase of risk
- Proven adversarial robustness suite for models
- Quantized inference path as measured product feature
- Full deterministic time-travel debugger for production incidents

## Scientific validity risks
Look-ahead / leakage in feature pipelines; unrealistic fills; multiple testing across many strategies; non-stationarity; treating paper PnL as production expectancy.
