# NVRA Phase 7 Residual Hardening Audit

## Baseline

| Item | Value |
|------|--------|
| Windows Build Run | [33356315324](https://github.com/whatman42/nvra/actions/runs/33356315324) |
| Build HEAD | `d3987b545568fac6ef2e18b8d91336149891b33a` |
| Docs residual commit | `3748501b174d015fe429e3c0f9db32f8ecad43d0` |
| Artifact (zip) SHA-256 | `c6081079c8c731f72ace5317cc944ab59c56df8bef14700621b38aa141e0afb9` |
| Status | **Windows Build SUCCESS** (locked) |

Gates already proven on that run: pip check, GUI import, secret scan, Windows regression,
PyInstaller, `NVRAFX.exe`, `--version`/`--health`/`--check-config` ExitCode=0, SHA-256,
artifact upload, `console=False` / `runw.exe`.

**This audit is READ-ONLY.** No production code, packaging, or workflow was modified.

---

## 1. `god.orchestration.models`

### Evidence

**Filesystem**

- Present under `god/orchestration/`: `__init__.py`, `bus.py`, `worker.py`, `scheduler.py`,
  `checkpoint_store.py`, `context_store.py`, `recovery.py`, `validation.py`, `handlers/*`.
- **Absent:** `god/orchestration/models/` (no directory, no `__init__.py`, no modules).

**Static imports (exact package `god.orchestration` / `.models`)**

All hits are **inside** `god/orchestration/**` only. Representative:

| File | Import |
|------|--------|
| `god/orchestration/__init__.py` | `from .models import (Checkpoint, CognitiveContext, …)` |
| `god/orchestration/bus.py` | `from .models.events import CognitiveEvent` |
| `god/orchestration/worker.py` | `from .models.checkpoint/context/events …` |
| `god/orchestration/scheduler.py` | `from .models.task …` |
| `god/orchestration/validation.py` | `from .models.events …` |
| `god/orchestration/handlers/*.py` | `from god.orchestration.models.context/events …` |

**No** matches for `god.orchestration` under:

- `scripts/nvrafx_entry.py`
- `god/gui/**`
- `god/production/**`
- `tests/**` (no orchestration package tests found)
- any module **outside** `god/orchestration/**`

Homonyms that are **not** this package:

- `god/paper/orchestrator.py` — paper pipeline docstring (“orchestration”), different module
- `god/ml/adaptive.py` — “ML orchestration facade”, not `god.orchestration`

**Dynamic import**

- No `importlib` / string-based loaders found that target `god.orchestration` in
  `god/`, `scripts/`, `src/`, `packaging/`, `tools/`.

**Live import (audit environment)**

```text
import god.orchestration
→ ModuleNotFoundError: No module named 'god.orchestration.models'

import god.orchestration.bus
→ same failure

import god.orchestration.handlers.base
→ same failure
```

**PyInstaller**

- Spec uses `collect_submodules("god")` (`packaging/nvrafx_onefile.spec`).
- Walker attempts to import subpackages; fails on `god.orchestration` → warning only.
- Entry analysis root remains `scripts/nvrafx_entry.py` (does not import orchestration).
- Baseline run still produced `NVRAFX.exe` (~448 MB) and passed smoke ExitCode=0.

**Git**

- History on this repo shows `god/orchestration/**` introduced with bulk commit
  `9a3ec97` (“Update project”); no separate commit history restoring a
  `god/orchestration/models/**` tree in this clone.

### Dependency Chain

```text
[nothing outside god/orchestration]
        │
        ▼
god.orchestration.__init__  ──imports──►  god.orchestration.models  (MISSING)
god.orchestration.bus       ──imports──►  models.events
god.orchestration.worker    ──imports──►  models.*
god.orchestration.handlers.*──imports──►  models.context / models.events
```

Internal package is self-consistent in **intent** (Phase 4G cognitive bus) but
**broken at import** because the models layer is absent.

### Reachability

| Consumer | Can reach `god.orchestration`? | Evidence |
|----------|--------------------------------|----------|
| `scripts/nvrafx_entry.py` | **No** | Top-level imports: stdlib only; no `god.orchestration` |
| GUI (`god.gui.main`) | **No** | Top-level: `god.app`, `god.broker…`, `god.gui…` — no orchestration package |
| NVRAFX frozen entry path | **No** | Same entry; smoke CLI/GUI import smoke passed without loading models |
| Production trading/risk path | **No** | No static edges into package |
| Tests | **No** | No test modules import package |
| Accidental `import god.orchestration` | **Fails hard** | ModuleNotFoundError (incomplete tree) |

### Root Cause

**A — Incomplete scaffold (primary).**

Phase 4G cognitive orchestration code was committed **without** the
`god.orchestration.models` subpackage that the rest of the package imports.

Not classified as:

- intentional dead-code deletion with cleaned references (references remain),
- required runtime feature of current NVRAFX product path (unreachable),
- PyInstaller-only bug (failure is real on plain `import god.orchestration`).

### Risk

| Scenario | Severity |
|----------|----------|
| Current NVRAFX product binary / paper path | **LOW** — unreachable |
| Future feature enabling cognitive orchestrator | **MEDIUM** — package cannot import until models restored or package removed |
| Developer `import god.orchestration` | **HIGH for that feature work** — immediate ImportError |
| Security vulnerability | **None evidenced** — build warning ≠ CVE |

### Recommendation

| Priority | Action | Notes |
|----------|--------|-------|
| **LOW** (backlog) | Restore `models` (context/events/checkpoint/task contracts) **with tests**, **or** quarantine/remove incomplete package so imports cannot partially exist | Product decision for Phase 4G |
| **LOW** | Optional packaging hygiene: exclude `god.orchestration` from `collect_submodules("god")` after explicit approval | Reduces warning noise only; must re-run full Windows Build |
| **Do not** | Dummy `models.py`, fake hidden-imports, mass-delete without design | Violates residual policy |

### Decision

**Document only. Non-blocking for production NVRAFX baseline.**

No code change in this pass.

---

## 2. `tbb12.dll`

### Evidence

**PyInstaller (Windows baseline log)**

```text
Library not found: could not resolve 'tbb12.dll',
dependency of '.../numba/np/ufunc/tbbpool.cp312-win_amd64.pyd'
```

Bootloader used: `runw.exe` (windowed). Build completed successfully.

**Project manifests**

| File | `numba` / `tbb` / `llvmlite` listed? |
|------|-------------------------------------|
| `requirements.txt` | **No** `numba`/`tbb`/`llvmlite`; has `torch`, `shap`, sklearn, lightgbm, xgboost, catboost |
| `pyproject.toml` | No runtime dependency list beyond project metadata |
| Lock files | None present |
| `packaging/nvrafx_onefile.spec` | No explicit numba/tbb binary collection |
| Workflows | Install `-r requirements.txt` only |

**Source imports**

```text
rg \\bnumba\\b|\\btbb\\b|llvmlite|tbbpool|njit|prange  under god/, src/, scripts/
→ no project source hits (zero)
```

**Transitive likelihood**

- `shap>=0.45` and scientific stack commonly pull **numba** (and thus llvmlite) on pip resolve.
- Numba’s optional parallel backend links `tbbpool.pyd` → `tbb12.dll`.
- Runner environment had numba present during analysis; project does not declare it.

### Dependency Chain

```text
requirements.txt (shap / scientific stack)
        │  (transitive, environment-dependent)
        ▼
     numba (not declared by NVRA)
        │
        ▼
numba/np/ufunc/tbbpool*.pyd
        │
        ▼
    tbb12.dll  (Intel TBB — not on runner path → PyInstaller WARNING)
```

### Runtime Reachability

| Question | Evidence |
|----------|----------|
| Does NVRAFX entry import numba? | No (static + source scan) |
| Did baseline smoke need TBB? | **No** — ExitCode=0 for `--version`, `--health`, `--check-config` |
| GUI import smoke | PASS without TBB packaging |
| Declared direct dependency? | **No** |

Conclusion: warning is from **binary graph analysis** of a transitive package present on the
build image, not from an NVRA feature path that requires TBB at runtime.

### Root Cause

**B/C — Transitive (and environment) dependency of the Windows build image**, not a
first-party NVRA dependency.

Optional Numba TBB pool is analyzed by PyInstaller; DLL not resolved → warning;
build does not fail.

### Risk

| Scenario | Severity |
|----------|----------|
| Current smoke / paper entry paths | **LOW** |
| Hypothetical future code path loading numba TBB pool without DLL | **LOW–MEDIUM** if such code is added without packaging TBB |
| Security vulnerability from the warning alone | **None evidenced** |

### Recommendation

| Priority | Action | Notes |
|----------|--------|-------|
| **LOW** | Keep as documented non-blocking warning | Default |
| **LOW** (optional later) | After approval: measure whether excluding `numba` from PyInstaller Analysis shrinks binary **and** re-run full Windows gate | Must not be done without regression proof |
| **Do not** | Vendor arbitrary `tbb12.dll`, add undeclared deps, weaken smoke tests | |

### Decision

**Document only. Non-blocking for production NVRAFX baseline.**

No packaging or workflow change in this pass.

---

## 3. Baseline Impact

Explicit confirmation for this audit:

| Constraint | Satisfied |
|------------|-----------|
| No business logic change | **Yes** |
| No trading / risk / execution change | **Yes** |
| No packaging change | **Yes** |
| No workflow change | **Yes** |
| Windows Build SUCCESS remains baseline | **Yes** (`d3987b54…` / run `33356315324`) |
| No dummy modules / no dependency adds / no file deletes | **Yes** |

---

## 4. Final Decision

### **PASS — residual non-blocking, documentation only**

Both residuals are **build-environment / incomplete-scaffold warnings**, not proven
production runtime failures for the shipped NVRAFX path validated on Windows CI.

| Residual | Production impact | Action now |
|----------|-------------------|------------|
| `god.orchestration.models` | Unreachable from entry; package import fails if used | Backlog feature cleanup |
| `tbb12.dll` | Transitive numba noise; smoke ExitCode=0 | Monitor; optional future exclude |

**NEED REVIEW** only if product owners later mandate: (1) enable cognitive orchestrator, or
(2) zero PyInstaller warnings / binary size reduction via excludes — those require a
separate approved change set and a full Windows Build re-gate.

**BLOCKER** is **not** assigned: no evidence either residual breaks current NVRAFX
production gates.
