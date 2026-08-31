# Configuration

Canonical application configuration is `config/settings.yaml`. Secrets must not be stored there.

Common environment inputs used by the release include:

| Variable | Default | Purpose |
|---|---|---|
| `NVRA_EXCHANGE_ID` | unset | Selects a configured exchange adapter; unset keeps exchange startup optional/safe. |
| `NVRA_SESSION_TOKEN` | unset | Session token source when a token file is not used. |
| `NVRA_CONFIG` | unset | Optional configuration path override where supported. |
| `NVRA_DATA_DIR` | unset | Optional user data/state directory override where supported. |

Credential enrollment is interactive and has no default credentials. Windows credentials may be stored through the configured credential manager/keyring.

See `.env.example` for a non-secret template. Actual deployment values belong in the environment or protected local files.
