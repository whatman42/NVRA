# Dual-Stack Concordance Matrix

Stacks: **`god/`** (institutional, paper, adaptive risk, ML) vs **`src/crypto/`** (RiskEngine, execution, startup composition).

| Concern | god/ | src/crypto/ | Concordance hypothesis | Disagreement class if diverge |
|---------|------|-------------|------------------------|-------------------------------|
| Risk evaluate API | `CapitalAdaptiveRiskEngine`, `PaperRiskEngine` | `RiskEngine.evaluate` | Same blocked/reject for isomorphic limits | SEMANTIC or SAFETY-RELEVANT |
| Safety mode | paper safety / autonomous SAFE_MODE | `SafetyMode` on RiskEngine | Both block new risk | SAFETY-RELEVANT if one allows |
| Order lifecycle | institutional OrderState | crypto execution states | UNKNOWN needs reconcile | SAFETY-RELEVANT |
| Idempotency | paper open, bus, loop | client order id models | Same client id → one economic effect | BUG if double |
| Execution authority | virtual/null/paper | paper + adapters | LIVE only gated | SAFETY-RELEVANT |
| Reconciliation | paper reconciler | portfolio reconcile hooks | Both required before READY | SEMANTIC |
| Error taxonomy | agent errors, paper status | reject reasons | Map table needed | BENIGN if pure naming |
| Config/policy | autonomous policy JSON | RiskPolicy | Unified view missing | UNDEFINED until mapped |

## Experiment definition (no refactor)

**Input:** canonical decision + equity + limits fixture.  
**Run:** both stacks’ pure evaluate functions.  
**Expect:** identical allow/block + comparable reason codes.  
**Classify:** BENIGN | SEMANTIC | SAFETY-RELEVANT | BUG | UNDEFINED.

Do **not** merge stacks in this research phase; measure first.
