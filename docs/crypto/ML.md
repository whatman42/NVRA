# Lightweight ML

**Phase 6 — predictions only (no orders)**

```
MarketData → Features → Model → Prediction → Strategy → TradeProposal → RiskEngine → Execution
```

ML never calls `create_order` / `cancel_order`.

## Algorithms

| Algorithm | Dependency | Profiles |
|-----------|------------|----------|
| LightGBM | `ml-lightgbm` | ULTRA_LITE+ |
| XGBoost | `ml-xgboost` | BALANCED+ |
| Random Forest | `ml-rf` (scikit-learn) | LITE+ |
| CatBoost | `ml-catboost` (optional) | PERFORMANCE+ |
| Fallback | none (pure Python) | always |

Default profile: **ULTRA_LITE** (LightGBM if present, else fallback).

Install examples:

```bash
pip install -e ".[ml-lightgbm]"
pip install -e ".[ml-full]"   # lgb + xgb + rf + catboost
```

No PyTorch / TensorFlow / JAX.

## Features (schema v1)

~22 tabular features from OHLCV only (past bars at index i):

returns, momentum, SMA ratios, EMA gap, volatility, ATR-like, range/body,
volume changes, RSI-like, 10-bar high/low context, close location.

Multi-timeframe: caller supplies bars for the desired timeframe (1m–4h);
engine does not auto-download all TFs on low-end hardware.

## Labels

Default: 5-bar forward return  
- UP if return ≥ +0.2%  
- DOWN if return ≤ −0.2%  
- else NEUTRAL  

Configurable via `LabelConfig`.

## Validation

Chronological split (60% train / 20% val / 20% test). **No random shuffle.**

## Prediction

Includes direction, probability, confidence (uncalibrated margin), expected return,
volatility estimate, regime (rule-based), model votes (ensemble-ready), data quality.

## Artifacts

`model.json` + `model.bin` with metadata: model_id, algorithm, feature schema,
training hash, metrics. Schema mismatch → `ArtifactError`. Secret-like fields rejected.

## Resource profiles

Bounded threads, trees, depth, features, training rows per `MLProfile`.

## Security

Model files treated as untrusted; magic-prefix validation; no credentials in metadata.
