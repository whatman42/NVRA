# Security Model — Credentials & Configuration

**Phase 1 document.**

## What is protected

| Asset                    | Storage location                          | Protection mechanism                  |
|--------------------------|-------------------------------------------|---------------------------------------|
| Exchange API key         | CredentialStore only                      | OS secure storage (Windows CM / DPAPI via keyring) or process memory (tests) |
| Exchange API secret      | CredentialStore only                      | Same as above                         |
| Non-secret config        | `%LOCALAPPDATA%\CRYPTO\config\` (future)  | Ordinary file permissions             |

API credentials **never** appear in:

- configuration JSON / YAML / TOML files
- SQLite / DuckDB / Parquet
- application logs
- exception messages
- audit-trail records
- `repr()` / `str()` of configuration or credential objects
- Git history
- README or documentation examples with real values

## Credential lifecycle

1. **Capture** — User enters key + secret in the first-run GUI (Phase 11).
2. **Validate** — Structural checks only (non-empty, length bounds, identifier format). No network call in Phase 1.
3. **Store** — `CredentialStore.set(ExchangeCredentials(...))`.
4. **Use** — Phase 2 adapters call `store.get(exchange_id, account_id)` and receive `SecretStr` values.
5. **Delete** — Explicit user action or `store.delete(...)`. The OS credential entry is removed.
6. **Overwrite** — `set()` replaces any existing entry for the same `(exchange_id, account_id)`.

## Platform behaviour

| Platform   | Production backend              | Fallback                          |
|------------|---------------------------------|-----------------------------------|
| Windows    | Windows Credential Manager via `keyring` | **None** — fail closed            |
| Linux/macOS (CI / dev) | InMemoryCredentialStore (only when `allow_in_memory=True`) | Explicit error otherwise |

There is **no** plaintext file fallback (`credentials.json`, `.env`, etc.).

## Secret redaction

- `SecretStr` overrides `__str__` and `__repr__` to return `********`.
- `ExchangeCredentials` holds `SecretStr` fields; its dataclass `repr` therefore cannot leak values.
- `AppConfig` contains zero secret fields and is safe to serialize.

## Logging policy

- Never log `api_key`, `api_secret`, or any `SecretStr.get_secret_value()`.
- Correlation IDs and high-level events (credential stored / deleted / missing) are permitted.
- Exception messages raised by the credential layer refer only to identifiers, never to secret material.

## Threat model (honest limits)

**Protected against**

- Casual inspection of the application directory or config files.
- Accidental logging / crash dumps that format objects via `repr`.
- Simple process-memory scraping of non-secret config.

**Not protected against**

- A local attacker with administrator rights who can read Windows Credential Manager or dump process memory while the secret is in use.
- Malware running as the same user that can call the Credential Manager APIs.
- Physical access + offline attacks against the Windows user profile (depending on OS configuration).
- Compromise of the exchange itself or of the API key via phishing / clipboard malware before storage.

Windows Credential Manager / DPAPI significantly raises the bar compared with a plaintext file, but **does not make the machine compromise-proof**.

## Backup policy

- Non-secret configuration may be backed up normally.
- Credentials must **not** be included in ordinary backups. Users who need multi-machine portability should re-enter API keys or use exchange-side key management.
- Deleting an account via `CredentialStore.delete` removes the OS entry; residual copies may exist in OS-level backups (Volume Shadow Copy, etc.) until those expire — this is an OS limitation.

## Development & testing

- Unit tests use `InMemoryCredentialStore` exclusively.
- Tests generate synthetic dummy values; real exchange keys must never appear in the repository.
- CI runs on Linux and therefore never exercises the Windows backend; the Windows path is isolated behind an import that is only loaded on `win32`.


## Control plane (Phase 11)

- PIN stored as PBKDF2 verifier + salt only
- No API secrets / Telegram tokens / PIN in audit or GUI snapshots
- Cashout cannot bypass exchange withdrawal policy
- Emergency stop does not delete state or alter RiskPolicy
