# NVRA Circular Dependency Fixes — Phase 4

## Scope

This change set addresses package-initialization cycles identified in the architecture audit. No trading, risk, execution, broker business logic, or adapter implementation logic was changed.

## Target 1 — `god.research` eager exports

- **File:** `god/research/__init__.py`
- **Lines:** 14–175 (replaced by lazy export surface; current implementation begins at line 14)
- **Change:** Removed eager imports of research models, engines, validation, strategies, reality/RCA, drift, and regime modules from package initialization. Added a PEP 562 `__getattr__` resolver backed by an explicit `_EXPORTS` map and retained the existing `__all__` public names.
- **Reason:** The package initializer eagerly imported multiple research subdomains, creating an initialization cycle through their transitive dependencies.
- **API compatibility:** Public exported names remain available as `god.research.<name>` and via `from god.research import <name>`; attributes are cached after first access.
- **Result:** `import god.research` succeeds without eagerly initializing the research graph; all 73 public exports were accessed successfully in a compatibility smoke test.

## Target 2 — `god.broker` MT5 eager import

- **File:** `god/broker/__init__.py`
- **Lines:** 6–40 (replaced by lazy export surface; current implementation begins at line 12)
- **Change:** Removed top-level MT5 adapter import and converted broker/MT5/mode/router exports to a PEP 562 `__getattr__` resolver. MT5 optional-import failure remains fail-closed by returning `None` for the three optional adapter attributes, matching the baseline behavior.
- **Reason:** Eager initialization of `god.broker.mt5` could re-enter `god.broker.models` while the package was partially initialized.
- **API compatibility:** Existing broker and MT5 attribute names remain accessible from the package; the baseline final `__all__` is preserved.
- **Result:** `import god.broker` succeeds; all names in `god.broker.__all__` were successfully resolved in a smoke test.

## Target 3 — `crypto.core.credentials` / `windows_cred`

- **File:** `src/crypto/core/credentials.py`
- **Lines:** 187–198
- **Change:** **No new change required.** The baseline already uses a local import of `WindowsCredentialStore` inside `create_credential_store()` rather than a top-level import.
- **Reason:** This is already the requested lazy-import boundary. Moving it back to module scope would recreate the runtime initialization cycle.
- **File:** `src/crypto/core/windows_cred.py`
- **Lines:** 14–20
- **Change:** No change.
- **Reason:** `WindowsCredentialStore` must inherit from and use the credential abstractions; the reverse dependency is safe at runtime because the Windows implementation is loaded only after `credentials.py` has initialized.
- **Result:** `import crypto.core.credentials` succeeds. The remaining static dependency edge from `windows_cred` to `credentials` is intentional; the runtime initialization cycle targeted by this fix is removed.

## Validation

- `python -m compileall -q .` — **PASS**
- `python -c "import god.research; print('research ok')"` — **PASS**
- `python -c "import god.broker; print('broker ok')"` — **PASS**
- `python -c "import crypto.core.credentials; print('credentials ok')"` — **PASS**
- `tests/crypto/registry/test_registry.py` — **3 passed**
- Full suite — **764 passed, 1 skipped** (765 collected; executed in batches because a single invocation exceeded the environment timeout)
- Windows-only skipped test: `tests/windows/test_windows_integration_marker.py`

## Static-cycle note

A static import graph still reports the intentional implementation dependency `crypto.core.windows_cred -> crypto.core.credentials`, while `credentials.py` contains only a function-local import back to the implementation. This is not a package-initialization cycle because the reverse import occurs only after `credentials.py` is fully initialized. The research and broker package-initialization cycles are removed.
