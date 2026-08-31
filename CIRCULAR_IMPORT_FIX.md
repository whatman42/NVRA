# NVRA Circular Import Fix

## Scope

Fixes only the indirect circular import that prevented `crypto.ml.governor` and
`crypto.ensemble.engine` from importing. No business, trading, risk, or execution
logic was changed. No dependency was added.

## Changes

| File | Baseline lines | Change | Reason | Validation |
|---|---:|---|---|---|
| `src/crypto/governor/__init__.py` | 7-17 | Replaced eager submodule imports with PEP 562 `__getattr__` lazy exports; preserved `__all__` and public names. | Importing `crypto.governor.states` previously executed the entire governor package initializer and pulled hardware/scanner/ensemble modules into the import graph. | governor import PASS; engine import PASS; registry tests PASS |
| `src/crypto/hardware/__init__.py` | 6-27 | Replaced eager integration/model/profile/snapshot imports with lazy exports; preserved public API names. | `crypto.hardware.models` was triggering hardware integration, which imported scanner configuration and continued the cycle. | governor import PASS; engine import PASS; registry tests PASS |
| `src/crypto/scanner/__init__.py` | 3-7 | Replaced eager engine/config/bridge/universe imports with lazy exports; preserved public API names. | `crypto.scanner.config` was triggering `scanner.engine`, which imported `ensemble.engine`. | governor import PASS; engine import PASS; registry tests PASS |
| `src/crypto/ensemble/__init__.py` | 3-5 | Replaced eager aggregate/engine/weighting imports with lazy exports; preserved public API names. | `crypto.ensemble.engine` was being eagerly imported while `crypto.ml.governor` was still partially initialized. | governor import PASS; engine import PASS; registry tests PASS |

## Verification sequence

Each changed initializer was validated immediately after the change with:

- `python -c "import crypto.ml.governor; print('governor ok')"` — PASS
- `python -c "import crypto.ensemble.engine; print('engine ok')"` — PASS
- `python -m pytest tests/crypto/registry/test_registry.py -q` — **3 passed**

After all changes:

- `python -m compileall -q .` — **PASS**
- Public package-level lazy exports — **PASS**
- Full suite collected — **765 tests**
- Full suite equivalent verification in three chunks — **764 passed, 1 skipped**
- Skipped test: `tests/windows/test_windows_integration_marker.py` (requires real Windows host)

The literal `python -m pytest -q` invocation was also attempted twice; it timed out in
this Linux execution environment after reaching the mid-suite without reporting a test
failure. To obtain deterministic completion, the exact same 765 collected node IDs were
then executed in chunks; all 764 runnable tests passed and the single Windows-only test
was skipped.

## Circular import status

The previously failing imports now complete successfully. The specific cycle through
`governor -> hardware -> scanner -> ensemble -> ml.governor` is broken by preventing
package initializers from eagerly importing their heavy submodules.

No changes were made to `src/crypto/ml/governor.py` or `src/crypto/ensemble/engine.py`.
