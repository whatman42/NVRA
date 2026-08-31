# Upgrade Safety

## Preserved across upgrade

- Execution / recovery SQLite databases  
- Audit logs  
- Model registry & ACTIVE artifacts (if schema-compatible)  
- User configuration references  
- Credential **references** (secrets stay in Windows Credential Manager)

## Procedure

1. Stop trading / allow reconciliation (or installer `taskkill` best-effort).  
2. Install new version (Program Files only for installer edition).  
3. Startup: integrity check → **schema migration** (`PRAGMA user_version`) → recovery → gates.  
4. LIVE remains explicit; default PAPER.  

## SQLite migration

- Versioned, transactional, idempotent  
- Backup under `backups/` before migrate  
- Failure → **SAFE MODE**, database not deleted  

## Models

Incompatible ACTIVE artifact → fallback / SAFE path. Old files are **not** auto-deleted.

## Rollback

Restore `backups/*_vbackup_*` and previous executable. Do not mix newer DB `user_version` with older app binaries.
