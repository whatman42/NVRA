# Ensemble

**Phase 7 — multi-model aggregation (no orders)**

## Flow

```
Models (ACTIVE in registry) → votes → weighted aggregate → EnsemblePrediction → Strategy → Risk
```

## Weighting

Bounded, normalized, regime-aware (`WeightConfig`). No fixed permanent 40/30/20/10 split. Metrics may gently nudge weights. Always re-normalized to sum 1.

## Disagreement

`agreement` / `disagreement` / `high_disagreement` exposed. High disagreement reduces confidence and opportunity score.

## Output

`EnsemblePrediction`: direction, probability, confidence (uncalibrated), expected return, volatility, regime, votes, versions, weights, data quality, seed opportunity score.
