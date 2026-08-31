# NVRA Portable Migration

NVRA supports moving a user's learned state and runtime state to another PC without retraining from zero.

## What is preserved

- portfolio/runtime state under the NVRA data root;
- durable order journal and reconciliation state;
- model registry/artifacts when `--model-root` is supplied;
- non-secret configuration snapshot when `--config` is supplied;
- checksums for every exported file.

## What is never exported

- `.env` files;
- API tokens and passwords;
- private signing keys/certificates;
- Git metadata and Python caches.

## Export on the old PC

```powershell
python tools/migrate_state.py export `
  --data-root "$env:USERPROFILE\.nvrafx" `
  --model-root "$env:USERPROFILE\.nvrafx\ml" `
  --config "config\settings.yaml" `
  --version "V7" `
  --output "NVRA-MIGRATION-V7.nvra.zip"
```

Inspect before moving it:

```powershell
python tools/migrate_state.py inspect NVRA-MIGRATION-V7.nvra.zip
```

## Load on the new PC

Install the same NVRA release first, then:

```powershell
python tools/migrate_state.py import `
  NVRA-MIGRATION-V7.nvra.zip `
  --data-root "$env:USERPROFILE\.nvrafx"
```

Use `--replace` only when intentionally replacing an existing installation state.

The import is fail-closed: archive paths and every file checksum are verified before live state is touched. The model artifacts are restored so the bot can resume from the existing Champion/registry state instead of learning from zero. Credentials must be configured separately on the new PC.

## Operational rule

After migration, start in recovery/reconciliation mode. The bot must verify journal, positions, orders, fills and balance before allowing new execution intents.
