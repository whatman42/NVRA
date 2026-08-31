# NVRA V8 — NautilusTrader / TradingAgents Integration Final Audit

## Baseline
`NVRA-UNIFIED-INSTITUTIONAL-V8-REFERENCE-HARDENED(1).zip`

## Implemented
- Institutional typed contracts and bounded MessageBus.
- Explicit idempotent order lifecycle with UNKNOWN reconciliation state.
- SQLite checkpoint/recovery primitive.
- Typed multi-agent analyst/evidence decision graph.
- Institutional composition kernel.
- Autonomous control-loop integration as an observation/checkpoint spine; no second execution path.
- Hardware workload profiles for 8GB, 16GB, 32GB+, and 64GB+GPU.
- ResourceGovernor separation between heavy ML training and heavy ML inference.
- Documentation and configuration updated.

## Source audit
- Python files: 683
- Source lines: 71399
- Characters inspected: 2447888
- UTF-8 failures: 0
- NUL bytes: 0
- AST/parse errors: 0
- Files missing final newline: 0
- Exact duplicate source-file groups: 0
- Sibling duplicate class/function definitions: 0
- Static deep audit: PASS
- Deep-audit orphan candidates: 320 (non-fatal; includes dynamically discovered/adapter modules)

The deep-audit reachability detector was hardened to preserve full import paths and resolve relative imports correctly. Orphan candidates are reported rather than treated as automatic failures because NVRA contains dynamic adapters, plugins, compatibility modules and optional platform integrations.

## Tests executed
- New institutional integration suite: 6 passed.
- Adaptive ML + institutional suite: 31 passed.
- Agent/healing/institutional targeted suite: 45 passed.
- Crypto test suite: 282 passed.
- Windows suite: 22 passed, 1 skipped because the runner is not Windows.
- Cloud suite: 3 passed.
- Security suite: 2 passed.
- Unified suite: 4 passed.
- Migration suite: 2 passed.

The complete 759-test collection was verified. A single monolithic full-suite run could not be completed in this runner because the execution environment interrupted long-running pytest processes; therefore this release does NOT claim 759/759 PASS.

## Hardware policy
8GB DDR3 remains the minimum. Lightweight ML inference/training is enabled with sequential resource limits. Neural training is not resident on 8GB. 16GB permits the full tree stack and optional neural inference when Torch is installed. 32GB+ makes heavy training eligible under ResourceGovernor pressure checks. 64GB+GPU receives the highest profile.

## Safety
Agent/LLM output has no direct execution authority. Risk gating and the existing execution contract remain authoritative. The institutional kernel's executor in the autonomous control loop is observation-only, preventing duplicate order submission.
