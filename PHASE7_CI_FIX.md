# Phase 7 CI Fix

## Baseline
commit: 9a3ec97eeeb9e093e99f0e6a0366b8d755009c44

## Changes

| File | Change | Reason |
|------|--------|--------|
| `.github/workflows/build.yml` | Replace `build/nvra.spec` + `NVRA.exe` with `packaging/nvrafx_onefile.spec` + `NVRAFX.exe`; pin actions to immutable SHAs; add `pip check`; verify no NUNG/NVRA.exe | Phase 7 pipeline was calling non-existent spec and wrong product name |
| `.github/workflows/windows-build.yml` | Add `python -m pip check` after install | Required validation step before build |
| `.github/workflows/nvra_windows_release.yml` | Add pip upgrade + `pip check` | Consistency with other Windows build paths |
| `.github/workflows/ci.yml` | Add `permissions: contents: read` and `pip check` | Least-privilege + dependency integrity |
| `.github/workflows/regression.yml` | Add `permissions: contents: read` and `pip check` | Least-privilege + dependency integrity |
| `.github/workflows/release.yml` | Add `permissions: contents: read` | Least-privilege |
| `NVRA_GITHUB_PACKAGE_README.md` | Canonical product name NVRAFX.exe | Docs contradicted architecture |
| `NVRA_COMPLETE_PROJECT_MANIFEST.md` | Canonical product + workflow mapping | Docs referenced NVRA.exe |
| `docs/AUTOSTART.md` | Example path → NVRAFX.exe | Autostart docs used legacy name |
| `README.md` | Autostart path text → NVRAFX.exe | Single remaining README reference to NVRA.exe as product binary |

## Validation

- compileall: PASS (`python -m compileall -q .` exit 0)
- registry tests: PASS (3 passed)
- full pytest: 761 passed, 4 failed, 1 skipped (local Linux host)
- pip check: FAIL on this host due to unrelated system packages (manim/numpy, polygon-api-client/certifi); clean GitHub Actions runners are expected to pass
- PyInstaller: NOT run (no Windows runner in this environment)
- executable: NOT produced locally
- SHA-256: N/A (no local Windows build)

## Remaining Findings

1. Four adaptive-ML scheduler tests fail on this Linux host with `resource_pressure_or_training_disabled` (`test_adaptive_ml_phase2.py`, `test_adaptive_ml_phase3.py`). Environment-sensitive; not introduced by CI changes. Baseline target was 766 passed / 1 skipped.
2. Windows PyInstaller build and SHA-256 of `NVRAFX.exe` require GitHub Actions `windows-latest` (or a real Windows machine). Not verified in this Linux sandbox.
3. `pip check` conflicts are from host system packages outside `requirements.txt`; CI runners installing only project deps should be clean.
4. Legacy specs still present (`packaging/nvra_onefile.spec`, `packaging/nung_windows.spec`, etc.) — intentionally left; they already redirect or are non-canonical. Do not delete without separate audit.
5. Workflow overlap remains (`build.yml` vs `windows-build.yml` vs `nvra_windows_release.yml`). Both now build the same canonical artifact; consolidation is a future recommendation, not done in this fix.
