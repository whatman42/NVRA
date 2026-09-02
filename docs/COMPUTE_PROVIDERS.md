# NVRA Optional Multi-Provider Compute

Local CPU/GPU is the baseline. Google Colab Free and Kaggle Notebooks are **opportunistic** accelerators for heavy training and research only.

NVRA runs fully without Colab or Kaggle.

## Architecture boundary

```
NVRA Core: data → quality → features → ML governor → regime → ensemble
         → signal governor → risk governor → paper execution → portfolio → audit
```

Compute providers may only participate in:

- model training / fine-tuning
- heavy data analysis
- offline CPCV / WFA / SHAP
- research diagnostics
- dataset preparation
- artifact generation

Providers **must not** control:

- Risk Governor / Signal Governor
- execution, reconciliation, SAFE_MODE
- broker credentials or live authorization
- order submission / portfolio authority

## Providers

| Provider | Module | Default |
|----------|--------|---------|
| Local | `god.ml.compute.LocalComputeProvider` | always available baseline |
| Colab | `god.ml.compute.ColabComputeProvider` | disabled, opportunistic |
| Kaggle | `god.ml.compute.KaggleComputeProvider` | disabled, opportunistic |

Status values: `AVAILABLE`, `UNAVAILABLE`, `DISABLED`, `INTERRUPTED`, `FAILED`.

Disconnect or timeout **never** maps to training `SUCCESS` — use `INTERRUPTED` or `UNKNOWN`.

## Selection policy

```text
provider: local  → Local
provider: colab  → Colab if AVAILABLE else Local
provider: kaggle → Kaggle if AVAILABLE else Local
provider: auto   → enabled+AVAILABLE cloud preferred, else Local
```

Safe default configuration:

```yaml
compute:
  provider: auto
  local:
    enabled: true
  colab:
    enabled: false
    opportunistic: true
  kaggle:
    enabled: false
    opportunistic: true
```

Missing `compute` section ⇒ local only.

## Workload matrix

| Workload | Local | Colab | Kaggle |
|----------|-------|-------|--------|
| Inference | YES | NO | NO |
| Signal / Risk / Paper execution / Reconciliation | YES | NO | NO |
| Fine-tuning / heavy training / CPCV / WFA / SHAP | YES | YES | YES |

## Job → registry flow

```text
prepare dataset + hash
    → TrainingJob manifest (sanitized)
    → selected provider
    → checkpoint / artifact + hashes
    → validate_training_result (fail-closed)
    → Model Registry / promotion (existing god.ml governance)
```

Invalid hash, schema mismatch, or non-SUCCESS job status ⇒ **no promotion**.

## Security

Cloud payloads and job metadata are passed through `sanitize_mapping`. Forbidden key fragments include password, secret, token, api_key, broker, mt5, credential, live_auth, keyring, etc.

Never send broker/live/exchange credentials to Colab or Kaggle.

## Windows EXE / Linux

- Lazy optional detection only (`google.colab`, Kaggle env vars).
- No mandatory cloud/torch/transformers imports on startup.
- Paper trading, inference, risk, and execution work offline with Local only.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| Colab UNAVAILABLE | Expected outside Colab; falls back to Local |
| Job INTERRUPTED | Session lost — resume from checkpoint metadata; do not promote |
| CI needs GPU/account | Not required — use unit tests / forced status doubles |

## Python API

```python
from god.ml.compute import (
    load_compute_config,
    select_provider,
    TrainingJob,
    validate_training_result,
)

cfg = load_compute_config(None)  # local-safe defaults
provider = select_provider(cfg)
result = provider.submit(TrainingJob(model_id="research_v1", dataset_hash="..."))
gate = validate_training_result(result)
if gate.eligible_for_promotion:
    ...  # hand off to existing ModelRegistry / promotion path
```
