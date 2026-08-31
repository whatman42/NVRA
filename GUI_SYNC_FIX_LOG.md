# NVRA GUI Sync Fix Log — Phase 6.1

Baseline: NVRA Phase 6 - GUI Fault Isolation

## GUI-001
- **Files:** `src/crypto/runtime/startup.py`, `god/gui/main.py`
- **Changes:** Added a read-only composition-root startup-state publication/reader (`get_startup_state`) and made the GUI poll it at a lightweight 500 ms interval. The GUI header now maps all `StartupState` values to explicit operator-facing labels and no longer hard-codes `SYSTEM SAFE`.
- **Reason:** The GUI must reflect the authoritative startup state without bypassing or changing startup/business logic.
- **API impact:** Existing startup APIs are preserved; `get_startup_state()` is additive. Existing GUI construction and runtime APIs are unchanged.
- **Validation:** `compileall` PASS; fault isolation test PASS; registry tests 3 passed; full regression validated in batches, aggregate 765 passed / 1 skipped.

## GUI-005
- **File:** `nvra_unified/__main__.py`
- **Changes:** Changed `--register-user` from three positional values (`USERNAME PASSWORD SECRET`) to username only. Password and registration secret are collected using hidden `getpass()` prompts and are never accepted through `argv`.
- **Reason:** Prevent credential exposure through process listings, shell history, and command-line inspection.
- **API impact:** The insecure legacy invocation is intentionally removed; the supported command remains `--register-user USERNAME` with interactive prompts.
- **Validation:** Explicit legacy-argument rejection test PASS; compileall PASS; full regression aggregate PASS.

## Headless GUI validation note
- The current Linux environment does not have `PySide6` installed, so an actual Qt widget smoke test cannot be executed without adding a dependency.
- The startup state bridge itself was exercised directly for `READY`, `RUNNING`, and `SAFE_MODE`, and the GUI source was verified to consume that bridge and contain no `SYSTEM SAFE` hard-coded header update.
