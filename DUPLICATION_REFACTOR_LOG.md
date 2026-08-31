# NVRA Duplication Refactor Log — Batch 1

## Batch 1 — Atomic writer + SHA-256 helper

| File | Baseline lines | Duplication removed | New function | Reason | Test result |
|---|---:|---|---|---|---|
| `god/ml/lifecycle.py` | ~100-115 | Local `atomic_write_bytes` implementation | `god.persist.atomic.atomic_write_bytes` | Consolidate identical crash-safe temp+fsync+replace implementation while preserving public name via imported symbol | PASS |
| `god/ml/persist.py` | ~40-55 | Private `_atomic_write_bytes` implementation | `god.persist.atomic.atomic_write_bytes` (aliased as `_atomic_write_bytes`) | Remove duplicate implementation while preserving the existing private call/API surface | PASS |
| `god/state/checksum.py` | ~9-15 | Local `file_sha256` implementation | `god.persist.hash.sha256_file` (aliased as `file_sha256`) | Consolidate identical file SHA-256 implementation while preserving existing public name | PASS |
| `god/persist/migration.py` | ~41-46 | Local `_sha256` implementation | `god.persist.hash.sha256_file` (aliased as `_sha256`) | Consolidate duplicate file SHA-256 implementation | PASS |

### Import safety check

- `god/ml/lifecycle.py`: `os` and `tempfile` were retained because `atomic_write_text()` still uses both directly.
- `god/ml/persist.py`: existing `hashlib` was retained because `_sha256_bytes()` still uses `hashlib.sha256()`.
- `god/state/checksum.py`: `hashlib` was retained because `bytes_sha256()` still uses it.
- `god/persist/migration.py`: `hashlib` was deliberately retained because the ZIP-stream verification path in `inspect_migration_bundle()` still calls `hashlib.sha256()` directly (around baseline line 181).
- No business, trading, risk, or execution logic was changed.
- No new third-party dependency was added.

### Validation

- `python -m compileall -q .` — PASS
- `python -c "import crypto.ml.governor; print('governor ok')"` — PASS
- `python -c "import crypto.ensemble.engine; print('engine ok')"` — PASS
- `python -m pytest tests/crypto/registry/test_registry.py -q` — **3 passed**
- `python -m pytest tests/migration/test_migration_bundle.py -q` — **2 passed**
- Full repository test set, executed in bounded batches due environment timeout behavior — **764 passed, 1 skipped**
- Windows integration marker: 1 skip because the validation host is Linux (`REAL WINDOWS TEST REQUIRED`).

## Status

Batch 1 accepted. MT4/MT5 adapters were not modified. Circular-import fix was not altered by this refactor.

## Batch 2 — Version formatter and provenance wrappers

### Sub-batch 2A — Version formatter
- **File:** `god/nvra_app/main.py` (former `_version_text`, lines 19-29)
- **File:** `god/runtime/main.py` (former `_version_text`, lines 29-38)
- **Duplikasi dihapus:** duplicated version-text construction.
- **Fungsi baru:** `god/runtime/version.py::format_version_text()`.
- **Perubahan:** kedua existing `_version_text()` wrappers tetap dipertahankan untuk API compatibility dan mendelegasikan formatting ke shared helper. Existing product-specific values remain unchanged.
- **Alasan:** menghilangkan copy-paste tanpa mengubah CLI/API behavior.
- **Import review:** no existing import was removed; added only the shared helper import.
- **Hasil test:** `compileall` PASS; `tests/crypto/registry/test_registry.py` = 3 passed; full repository validation = 764 passed / 1 skipped.

### Sub-batch 2B — Provenance wrappers
- **Files:** `god/decision/models.py`, `god/loop/models.py`, `god/resilience/models.py`, `god/selection/provenance.py`, `god/control/models.py`, `god/paper/models.py`, `god/execution_contract/models.py`.
- **Duplikasi dihapus:** seven wrappers duplicated the same `build_provenance(...)` → three-field dictionary projection, differing only by domain origin string.
- **Fungsi baru:** `god/research/provenance.py::build_provenance_dict()`.
- **Perubahan:** each existing public/domain wrapper name and signature is preserved; each now delegates to `build_provenance_dict(origin=..., payload=...)`. Domain-specific origin constants remain unchanged.
- **Alasan:** shared helper removes structural copy-paste while preserving domain-specific API names and readability.
- **Import review:** existing `build_provenance` imports in the seven wrapper modules were replaced only after repository/file usage review; `content_hash` imports remain where used elsewhere in the same files.
- **Hasil test:** `compileall` PASS; `tests/crypto/registry/test_registry.py` = 3 passed; full repository validation = 764 passed / 1 skipped.

### Intentionally not changed
- MT4/MT5 adapters: unchanged, preserving platform isolation.
- Business/trading/risk/execution logic: unchanged.

### Batch 2 final validation
- Collected test nodes: 765.
- Passed: 764.
- Skipped: 1 Windows-only integration test (Linux environment).
- Failed: 0.

## Startup Composition Root — Phase 4B

| File | Lines | Change | Reason | Validation |
|---|---|---|---|---|
| `src/crypto/runtime/startup.py` | new | Added `StartupState`, `StartupContext`, `StartupResult`, bounded stage runner, and `run_startup()` composition root | Make startup order explicit while reusing existing subsystem boundaries | `compileall` PASS; startup smoke PASS; full suite validated |
| `src/crypto/runtime/entrypoint.py` | `_boot()` | `_boot()` now delegates orchestration to `run_startup()` while retaining public entrypoints and GUI handling | Establish one composition root without removing `_boot()` API | entrypoint import PASS; registry 3 passed; full suite validated |
| `STARTUP_COMPOSITION_ROOT.md` | new | Documented startup/recovery state machine and stage ownership | Architecture documentation | Included in release |
| `README.md` | appended | Added pointer to startup composition documentation | Make the new composition root discoverable | Documentation-only |

### Phase 4B validation

- `python -m compileall -q .` — PASS
- `import crypto.runtime.entrypoint` — PASS
- `import crypto.runtime.startup` — PASS
- `tests/crypto/registry/test_registry.py` — 3 passed
- Full collected suite — 765 tests: 764 passed, 1 skipped
- Windows integration marker — 1 expected skip on non-Windows
- No new dependency
