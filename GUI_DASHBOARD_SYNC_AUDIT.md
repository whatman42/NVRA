# NVRA GUI / Dashboard Synchronization Audit — Phase 6

Baseline: **NVRA Phase 6.1 - GUI Sync Fix**

Scope: production GUI, unified GUI/runtime, entrypoints/CLI, and the existing crypto startup composition root. No production source code was modified during this audit.

## Executive Summary

The GUI is broadly aligned with the Phase 4B/Phase 5 product model, but it is **not fully synchronized with the new startup composition root**. The main UI surfaces still use the older `NungApplication`/`UnifiedRuntime` status model and do not consume the authoritative `crypto.runtime.startup.StartupState` (`LICENSE_CHECK → LOAD_STATE → BROKER_CONNECT → RECONCILIATION → RISK_GOVERNOR → READY → RUNNING / SAFE_MODE`). This is the principal synchronization gap.

The GUI does correctly reflect several recent functional constraints: no username prefill, hidden password fields, first-run enrollment, Google sign-in blocked before enrollment, CRYPTO PAPER/LIVE, Forex following the MT5 account, IDX signal-only/portfolio integration, and notification mute support.

A second security/synchronization gap exists in `nvra_unified/__main__.py`: the legacy `--register-user USERNAME PASSWORD SECRET` interface still places a password and registration secret in `argv`. The dedicated `scripts/nung_entry.py` and `scripts/nvrafx_entry.py` paths are corrected, but the unified module entrypoint is not.

## Findings

| ID | Location | Finding | Risk | Recommendation |
|---|---|---|---|---|
| GUI-001 | `god/gui/main.py:240-254` | Dashboard refresh derives status from `NungApplication.dashboard()` and hard-sets header to `SYSTEM SAFE`; it does not display authoritative startup states READY/RUNNING/SAFE_MODE or recovery/retry state from `crypto.runtime.startup`. | **High** | Introduce a read-only status adapter from the composition root to the GUI. Display the actual startup/recovery state and last stage/error without allowing GUI to bypass gates. |
| GUI-002 | `nvra_unified/gui.py:257-266` | Unified GUI displays `UnifiedRuntime` service fields (`running`, `crypto`, `forex`, etc.) rather than the composition-root state machine. SAFE_MODE/retry is not represented as a first-class UI state. | **Medium** | Expose a safe, read-only startup/recovery snapshot to the UI and map SAFE_MODE/retry/reconciliation states explicitly. |
| GUI-003 | `god/gui/main.py:195-200` | Autostart catches exceptions, but writes `traceback.format_exc()` into the GUI audit pane. This is useful diagnostically but can disclose local filesystem/module details. | **Medium** | Keep detailed traceback in protected application logs; show only sanitized error category/message in the operator GUI. |
| GUI-004 | `nvra_unified/gui.py:170-188` | Google authentication is correctly blocked before enrollment, but post-auth UI state is not tied to the startup composition-root state. | **Low/Medium** | After authentication, consume authoritative startup state rather than only starting `UnifiedRuntime`. |
| GUI-005 | `nvra_unified/__main__.py:13-23` | Legacy `--register-user USERNAME PASSWORD SECRET` still accepts password and registration secret directly in command-line arguments. | **High** | Remove password/secret from argv. Use interactive `getpass()` and an environment/protected file for the registration secret, consistent with the security-fixed CLI scripts. |
| GUI-006 | `god/gui/main.py:256-260` | MT5 operations are invoked synchronously from GUI event handlers. A slow/unavailable terminal could block the Qt event loop. | **Medium** | Move network/terminal operations to a worker and report completion asynchronously. |
| GUI-007 | `nvra_unified/gui.py:241-244` | Cashout response is shown directly as JSON in a message box. Current backend is fail-closed, but future sensitive fields could accidentally become operator-visible. | **Low** | Use a sanitized presentation DTO for operator-facing responses. |

## Areas Confirmed Synchronized

- `god/gui/main.py:147-151`: username is empty by default; password uses `QLineEdit.Password`; explicit account creation and login controls exist.
- `nvra_unified/gui.py:146-158`: first-run enrollment is available and refuses empty credentials.
- `nvra_unified/gui.py:170-188`: Google login is blocked while enrollment is required.
- `god/gui/main.py:157-170`: CRYPTO has PAPER/LIVE; Forex has no Demo/Real selector and follows the MT5 terminal account; IDX is signal-only with portfolio integration.
- `god/gui/main.py:178-180`: notification mute control exists.
- `nvra_unified/gui.py:269`: closing the window hides to tray while the runtime remains active.
- `scripts/nung_entry.py` and `scripts/nvrafx_entry.py`: passwords use `getpass`; session tokens use token-file/environment mechanisms.
- `src/crypto/runtime/startup.py`: startup states and bounded retry/SAFE_MODE behavior are explicit.

## Fault Injection Test

Added: `tests/test_gui_fault_isolation.py`.

Scenario:
1. Compose the real startup state machine with deterministic injected stage implementations.
2. Assert the core reaches `StartupState.RUNNING`.
3. Run an independent core loop in a background thread.
4. Inject a GUI exception at the product GUI boundary (`nvrafx_entry._run_gui`).
5. Assert the GUI failure is converted to a return code and does not stop the core loop or alter the already-running core state.

Expected/validated behavior: **GUI failure is isolated from the core loop.**

## Phase 6.1 Fix Status

The two HIGH-priority findings are fixed without changing trading, risk, execution, or broker business logic.

- **GUI-001 — FIXED:** `god/gui/main.py` now observes the read-only authoritative `crypto.runtime.startup` state bridge. The header dynamically displays `STARTUP INIT`, `LICENSE CHECK`, `LOADING STATE`, `BROKER CONNECT`, `RECONCILIATION`, `RISK / GOVERNOR`, `READY`, `RUNNING`, `SAFE MODE`, or `FAILED`. The previous hard-coded `SYSTEM SAFE` update was removed.
- **GUI-005 — FIXED:** `nvra_unified/__main__.py --register-user` now accepts only `USERNAME`; password and registration secret are collected through hidden `getpass()` prompts. Legacy `USERNAME PASSWORD SECRET` argv usage is rejected by argparse.

A lightweight headless smoke was attempted, but the audit environment does not have `PySide6`; installing a new dependency was outside scope. The startup-state bridge was directly exercised for READY/RUNNING/SAFE_MODE, and the GUI source was statically checked for the authoritative state mapping.

See `GUI_SYNC_FIX_LOG.md` for the change log.

## Conclusion

The current system has a useful GUI exception boundary, but the GUI is not yet a first-class observer of the authoritative startup state machine. The recommended next architectural change is therefore a **read-only startup/recovery status bridge**, not a change to trading or execution logic. The legacy unified CLI credential path should also be corrected before the next security sign-off.

## Validation Results

- `python -m compileall -q .` — **PASS**
- `python -m pytest tests/test_gui_fault_isolation.py -q` — **1 passed**
- `python -m pytest tests/crypto/registry/test_registry.py -q` — **3 passed**
- Full regression suite executed in batches — **765 passed, 1 skipped** (766 collected after adding the new fault-injection test).
- The single skip is the expected real-Windows-only integration marker.
- No production source file was modified; the Phase 6 source changes are limited to this report and `tests/test_gui_fault_isolation.py`.
- No separate production dashboard/web endpoint was found in the scoped source tree; the audit therefore treated the desktop GUI and CLI/module entrypoints as the dashboard/control surfaces.
