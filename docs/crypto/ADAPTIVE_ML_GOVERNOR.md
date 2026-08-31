# Adaptive ML Governor

The CRYPTO runtime now separates three decisions:

1. **Hardware budget** — hardware detection determines the maximum compute envelope.
2. **Resource governor** — live CPU/RAM/thermal/power pressure reduces the envelope.
3. **ML model governor** — model quality and runtime health decide which loaded models
   actually receive inference slots.

This means a high-end machine can load LightGBM, XGBoost, Random Forest and CatBoost
without being forced to execute all of them on every cycle. A model must earn a slot.

## Selection policy

| Hardware profile | Normal-state model slots |
|---|---:|
| ULTRA_LITE | 1 |
| LITE | 1 |
| BALANCED | 2 |
| PERFORMANCE | 3 |
| EXTREME | 4 |

The governor ranks models using `test_accuracy` (falling back to validation accuracy),
then discounts models with high inference latency or repeated errors. The fallback
model is a safety net and is not treated as a normal ensemble peer when real models
are available.

Resource pressure reduces slots further:

`NORMAL → RECOVERY → DEGRADED → CONSTRAINED/CRITICAL`

The governor never changes RiskPolicy, order limits, credentials, withdrawal
permissions, or LIVE authorization.

## Runtime health

Inference latency and success/failure are observed using an EWMA. Repeated slow or
failed models are demoted on the next selection cycle. This is bounded and
deterministic; there is no uncontrolled thread/model spawning.

## Windows

Windows hardware detection includes physical RAM and power status. Runtime telemetry
uses `psutil` for CPU, memory, process RSS, battery and (when supported) temperatures.

## LIVE safety

The software can be built as a Windows GUI executable, but `SOFTWARE GREEN` is not
the same as a verified production exchange.

LIVE requires:

- real connectivity probe,
- real permission probe,
- measured time synchronization,
- withdrawal explicitly `DISABLED` (UNKNOWN is unsafe),
- model/DB/recovery/governor/risk/control integrity,
- micro-capital ceiling,
- reconciliation clean,
- emergency-stop test,
- completed real exchange canary round-trip,
- expected build hash when configured.

CI and automated tests never place real orders.
