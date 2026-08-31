# NVRA Security Fixes — Phase 5

Baseline: `NVRA Phase 4B - Startup Composition`

## SEC-001 — First-run local operator enrollment

- **Files:** `nvra_unified/auth.py`, `nvra_unified/gui.py`, `tests/unified/test_unified.py`
- **Changes:** removed the hard-coded `nung` username/default password verifier. Added first-run enrollment with a PBKDF2-HMAC-SHA256 verifier, random salt, owner-only `auth_verifier.json`, private parent directory, and no overwrite of an existing enrollment. The existing `verify_default_login()` name is retained only as a compatibility wrapper around enrolled-credential verification; it no longer contains or falls back to any default credential.
- **GUI:** local username is no longer prefilled; first-run enrollment is explicit and password entry is hidden. Google sign-in is blocked until local enrollment exists.
- **Reason:** eliminate deployment-wide built-in authentication material and require an operator-created credential on first use.

## SEC-002 — Model artifact deserialization boundary

- **Files:** `src/crypto/ml/backends.py`, `src/crypto/ml/artifacts.py`
- **Changes:** removed direct `pickle.loads()` calls from the four ML backend loaders. Deserialization is isolated behind a private trusted-artifact loader. `load_model_bytes()` now rejects untrusted input unless explicitly invoked by the verified artifact-loading path. Model artifacts receive a sidecar SHA-256 manifest (`.sha256`), and the artifact directory is restricted to owner access on POSIX-style filesystems. Missing or mismatched checksums fail closed before deserialization.
- **Reason:** magic headers are not an authentication boundary. The existing ML object format is retained for compatibility while ensuring the deserialization path is reached only after integrity verification.
- **Note:** the sidecar checksum must be distributed/protected as a trusted artifact manifest; it is not a cryptographic signature by itself.

## SEC-003 — Remove credentials from CLI argv

- **Files:** `scripts/nung_entry.py`, `scripts/nvrafx_entry.py`
- **Changes:** password arguments were removed from command-line positions and are now requested with `getpass.getpass()`. Session tokens are accepted only through `--token-file` or `NVRA_SESSION_TOKEN`, never as a `--token` argument. Help text documents the behavior.
- **Reason:** prevent passwords/bearer tokens from appearing in process listings, shell history, and command auditing.

## SEC-004 — Restrictive credential-file permissions

- **Files:** `god/auth/registry.py`, `god/admin/admin_registry.py`
- **Changes:** credential JSON files are written through owner-only `0600` file descriptors, temporary files are also `0600`, parent directories are set to `0700` where supported, and final files are re-chmodded to `0600` after atomic replacement.
- **Reason:** prevent local users from obtaining password hashes under permissive umasks.

## SEC-005 — Dependency security floors

- **File:** `requirements.txt`
- **Changes:** `requests>=2.33.0`; `urllib3>=2.7.0`.
- **Reason:** prevent fresh installs from selecting versions covered by the audit's identified security advisories.
- **`pip check`:** the environment reports an unrelated pre-existing conflict: `moviepy 2.2.1` requires `pillow<12.0,>=9.2.0`, while the environment contains Pillow 12.3.0. NVRA's requested dependency changes do not cause this conflict, so no unrelated dependency was changed.

## Validation

- `python -m compileall -q .` — **PASS**
- `python -m pytest tests/crypto/registry/test_registry.py -q` — **3 passed**
- ML/security-focused tests — **PASS**
- Full suite, executed in controlled batches due runner time limits — **764 passed / 1 skipped**
- Total collected — **765**
- Windows-only integration skip — expected on Linux
- Production grep: no `DEFAULT_USERNAME`, `_DEFAULT_PASSWORD_VERIFIER`, or direct `pickle.loads()` remains in the audited `nvra_unified` / `src` paths.

## Scope safety

No trading, risk, execution, broker, or ML business logic was intentionally changed. No new third-party dependency was introduced.
