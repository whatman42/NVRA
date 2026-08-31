# Phase 7 Residual Hardening

**Baseline (locked):** Windows Build SUCCESS  
Run `33356315324` · Job `99379071254` · HEAD `d3987b545568fac6ef2e18b8d91336149891b33a`

This document audits packaging warnings that **do not fail** the Windows gate.
No production entry, trading, risk, or execution logic was changed for these findings.

---

## 1. `god.orchestration.models`

### Symptom
PyInstaller during `collect_submodules("god")`:

```
Failed to collect submodules for 'god.orchestration'
ModuleNotFoundError: No module named 'god.orchestration.models'
```

### Root cause
Package `god/orchestration/` is **incomplete**:

| Present | Missing |
|---------|---------|
| `__init__.py`, `bus.py`, `worker.py`, `scheduler.py`, stores, handlers | `god/orchestration/models/` (entire subpackage) |

Internal imports still reference:

- `god.orchestration.models.context` (`CognitiveContext`, `CognitiveStage`, …)
- `god.orchestration.models.events` (`CognitiveEvent`, `EventType`, `create_event`, …)
- `god.orchestration.models.checkpoint` (`make_checkpoint`, …)

`god/orchestration/__init__.py` re-exports from `.models`, and every handler under
`god/orchestration/handlers/` imports those symbols.

### Classification
**Stale / incomplete Phase 4G scaffold** — not a packaging bug in the canonical
`NVRAFX` product path.

### Reachability (production)
| Surface | References `god.orchestration`? |
|---------|----------------------------------|
| `scripts/nvrafx_entry.py` | No |
| `god/gui/**` (GUI entry) | No |
| `god/production/**` | No |
| Tests under `tests/` | No |
| Outside `god/orchestration/**` | **No imports found** |

Conclusion: the broken package is **not reachable** from the shipped entrypoint.
`collect_submodules("god")` walks the tree and surfaces the missing submodule as a
**warning**; the build still completes and produces `NVRAFX.exe`.

### Decision
| Option | Chosen? | Why |
|--------|---------|-----|
| Invent dummy `models.py` | **No** | Hides incompleteness; false API |
| Blind hidden-import | **No** | Module does not exist |
| Restore full models package | **Deferred** | Requires product design for Phase 4G; out of residual scope |
| Delete handlers / package | **Deferred** | Large cleanup; risk without dedicated audit |
| Change `collect_submodules` filter | **No (this pass)** | Baseline packaging already PASS; filter is optional hygiene |
| Document non-blocking | **Yes** | Accurate, preserves baseline |

**Status: non-blocker · deferred cleanup (backlog)**

### Recommended backlog
1. Either restore `god.orchestration.models` (context/events/checkpoint contracts) with tests, **or**
2. Remove/quarantine incomplete orchestration package and handlers so `import god.orchestration` cannot fail.
3. After (1) or (2), re-run Windows Build once to confirm the collect_submodules warning is gone.

---

## 2. `tbb12.dll`

### Symptom
PyInstaller:

```
Library not found: could not resolve 'tbb12.dll',
dependency of '.../numba/np/ufunc/tbbpool.cp312-win_amd64.pyd'
```

### Root cause
- **Numba** ships optional TBB-backed parallel ufuncs (`tbbpool`).
- On the Windows CI image, Numba appears as a **transitive** dependency (not listed in
  project `requirements.txt`; project source has **zero** `import numba` / `@njit` usage
  under `god/`, `src/`, `scripts/`).
- PyInstaller binary analysis sees the `.pyd` → `tbb12.dll` edge and warns when the
  Intel TBB shared library is not on the search path.

### Classification
**Optional native side-channel of a transitive package**, not a first-class NVRA dependency.

### Production path impact
| Question | Answer |
|----------|--------|
| Does NVRAFX entry import numba? | No |
| Is TBB required for `--version` / `--health` / `--check-config`? | No (ExitCode=0 on baseline run) |
| Is TBB required for paper GUI path validated in CI? | No evidence of numba on that path |
| Does the warning fail the build? | **No** |

### Decision
| Option | Chosen? | Why |
|--------|---------|-----|
| Vendor `tbb12.dll` into the one-file build | **No** | No reproducing load path; license/source provenance unclear for blind copy |
| Add `tbb` / `numba` to requirements | **No** | Not required by project code |
| Exclude numba from Analysis | **Deferred** | Possible future size win; needs careful excludes + regression; not required for gate |
| Document non-blocking | **Yes** | Matches evidence |

**Status: non-blocker · track for size/hardening only**

### Recommended backlog
1. Confirm on a Windows host with the released EXE whether any ML path loads
   `numba.np.ufunc.tbbpool` (unlikely given zero source imports).
2. If never loaded: optionally add PyInstaller `excludes=['numba']` (or tighter) after
   measuring binary size and re-running full Windows Build.
3. If a future feature requires numba parallel: pin `numba` + legitimate TBB redistributable
   with a documented packaging recipe — do not copy random DLLs.

---

## 3. Validation (this residual pass)

| Check | Result |
|-------|--------|
| Code / packaging change for residual | **None** (documentation only) |
| Baseline Windows Build | Unchanged — remains SUCCESS at `d3987b54…` |
| compileall / full pytest / Windows gate | Not re-run for doc-only; baseline already green |

If a future commit changes packaging excludes or restores orchestration models, re-run the
full Windows Build gate (regression, PyInstaller, smoke ExitCode, SHA-256, artifact).

---

## 4. Residual risk summary

| Item | Risk if ignored | Severity |
|------|-----------------|----------|
| Incomplete `god.orchestration` | Accidental future import of package fails at runtime; PyInstaller noise | Medium for **orchestration feature work**; **Low** for current NVRAFX product path |
| `tbb12.dll` unresolved | Only if some code path loads numba TBB pool without the DLL | **Low** given no project numba usage |

---

## 5. Explicit non-actions (this pass)

- Did **not** invent `god/orchestration/models`
- Did **not** add hidden imports for missing modules
- Did **not** vendor TBB DLLs
- Did **not** change `console=False`, smoke `Start-Process`, or workflows that already PASS
- Did **not** alter trading / risk / execution / public product API
