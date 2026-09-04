# Stage 2 / 2.1 Gap Matrix

| Surface | Coverage | Status |
|---------|----------|--------|
| synthetic replay | PASS | none |
| EventBus publish/consume | PASS | none |
| Worker/handler path | CuriosityHandler pass-through | PARTIAL (other handlers optional engines) |
| Recovery-boundary matrix B1–B6 | orchestration CheckpointStore | PASS (supported boundaries) |
| RiskEngine.evaluate | production API | PASS |
| ExecutionStore round-trip | semantic + idempotent save | PASS |
| Analysis/research pipeline | synthetic analysis + curiosity handler | PARTIAL |
| NVRA.exe startup composition | CLI --version/--health only | PARTIAL / CI-qualified |
| Full product EventBus all handlers | engines optional | gap |
| External LLM providers | fixture-only if used | N/A in harness |

**Replay scope:** INTEGRATED_PARTIAL (expanded)  
**Verdict:** GO-MORE-DATA (NVRA.exe full composition + multi-handler engines remain open)
