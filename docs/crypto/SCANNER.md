# Opportunity Scanner

**Asset-first, cheap filters before ML, bounded candidates.**

## Order of filters

1. Available balances / assets (hop 0 direct; hop ≤ 1 prepared)
2. Market active
3. Spread
4. Data quality
5. Min order feasibility
6. ML ensemble (bounded)
7. Fee/slippage vs expected edge
8. Portfolio exposure awareness
9. Opportunity score ranking

## Limits (`ScannerConfig`)

`max_universe`, `max_candidates`, `max_ml_candidates`, `max_predictions_per_cycle`, `max_opportunities`.

## Opportunity

Exchange-specific symbol identity retained. Mandatory `reason_codes`. Score 0..1 ranking only — **not** trade authorization.

## Bridge

`opportunity_to_proposal` → `TradeProposal` → RiskEngine only.
