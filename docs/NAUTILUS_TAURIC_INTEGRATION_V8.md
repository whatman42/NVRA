# NVRA V8 — NautilusTrader / TradingAgents integration

## Adopted patterns
- Deterministic bounded message bus with Data/Event/Command categories.
- Composition-root kernel and explicit order lifecycle.
- Idempotent event handling and checkpoint/cache separation.
- Risk gate on the order path and reconciliation as a first-class state.
- Typed analyst evidence and structured analyst → research/debate → trader decisions.
- Node checkpoints and provider/LLM dependency injection.

## Safety adaptation
Agent/LLM output is advisory. Final decisions must pass the immutable Risk Governor and execution contract. Agents cannot raise risk ceilings, bypass reconciliation, or access credentials.

## Hardware policy
- 8 GB DDR3: all lightweight ML inference; sequential training; no resident neural training.
- 16 GB: full tree-model stack plus neural inference when Torch is installed; heavy training deferred.
- 32 GB+: ensemble and heavy training when resource pressure permits.
- 64 GB + GPU: full training profile, subject to ResourceGovernor.

Inference always has priority. Workloads tighten automatically under CPU/RAM pressure.

## Recovery
The SQLite checkpoint store is dependency-light. On restart, the graph can resume from its last completed node; execution state remains separate and must reconcile before new broker orders.

## Audit
```powershell
python tools/deep_audit.py
python -m pytest tests/test_institutional_kernel_v8.py -q
```
