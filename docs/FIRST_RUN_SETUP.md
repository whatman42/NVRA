# NVRA First-Run Setup Runbook

Guide from fresh installation to a successful **PAPER** trading run.

**Product boundary:** distributed NVRA defaults to **PAPER ONLY**. Real trading requires explicit environment authorization.

**Cloud compute:** Google Colab and Kaggle are **optional external-session adapters**. They do **not** perform autonomous remote training in the current build.

## A. Requirements

| Item | Guidance |
|------|----------|
| OS | Windows 10/11 or Linux |
| RAM | Minimum 8 GB; 16 GB recommended |
| Disk | Free space under `~/.nvrafx` |
| Python (source) | 3.10–3.12 |
| Packaged Windows | `NVRA.exe` + SHA-256 verify |

## B. Installation

```bash
git clone https://github.com/whatman42/nvra.git
cd nvra
python -m pip install -r requirements.txt
export PYTHONPATH=".:src"
python -m pytest -q
```

Windows packaged: download Actions artifact, verify hash, run `NVRA.exe`.

## C. Wizard order

1. Welcome — version, OS, data/state/config dirs  
2. Hardware — existing ResourceGovernor / institutional profile  
3. Operator — enrollment (password → CredentialStore only)  
4. Data — symbols/timeframe/cache  
5. Exchange — binance / tokocrypto / indodax / mt5  
6. Credentials — API key/secret for non-PAPER; PAPER may skip live keys  
7. Telegram — optional  
8. Compute — Local on; Colab/Kaggle default off  
9. Security — fail-closed checklist  
10. Validate — local validations only  
11. Done — summary; non-secret setup state persisted  

Default mode: **PAPER**.

## D. Credentials

Secrets only in CredentialStore / Windows Credential Manager / environment.  
**Never** YAML, Git, logs, TrainingJob metadata, or cloud payloads.

## E. Telegram (optional)

Bot token → secure store; chat ID may be non-secret config. Skip allowed.

## F. Colab (optional)

Do **not** enter Google password into NVRA. External-session adapter only. Unavailable → Local fallback.

## G. Kaggle (optional)

Kaggle Settings → API → token → secure NVRA field only. External-session adapter. Unavailable → Local fallback.

## H. First PAPER run

Setup → validation → READY → data → quality → features → inference → signal governor → risk governor → paper execution → portfolio → audit.

## I. Cloud training integrity

dataset hash → TrainingJob (sanitized) → provider → artifact SHA-256 → provenance → compute gate → Model Registry → promotion only if eligible.

## J. Troubleshooting

Wizard blocked: check required fields. CredentialStore issues: use platform backend. Colab/Kaggle unavailable: expected outside those runtimes. Artifact integrity fail: do not promote. SAFE_MODE: resolve underlying fault; risk ceiling unchanged.

Related: `docs/COMPUTE_PROVIDERS.md`, `docs/INSTALL.md`, `docs/BROKER_MODES.md`.
