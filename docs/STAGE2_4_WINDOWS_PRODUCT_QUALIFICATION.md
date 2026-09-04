# Stage 2.4 — Windows product-level NVRA.exe qualification

## Distinction

| Layer | Path | Status |
|-------|------|--------|
| SOURCE_COMPOSITION | `crypto.runtime.startup.run_startup(PAPER)` | PASS (Stage 2.2+) |
| ACTUAL_NVRA_EXE CLI | `NVRA.exe --version/--health/--check-config` | PASS (Windows CI) |
| ACTUAL_NVRA_EXE headless | `NVRA.exe --headless` → `run_autonomous_runtime` | PASS (Windows CI N=20) |
| ACTUAL_NVRA_EXE process recovery | kill + restart `--headless` | PASS (Windows CI N=5) |
| GUI_HOST_E2E | interactive desktop GUI | **UNOBSERVABLE** in CI |

## Notes

- PyInstaller entry is `scripts/nvrafx_entry.py` (console=False).
- `--headless` is an **existing** supported flag; no new production CLI invented.
- Headless path is PAPER/safe by default; LIVE remains blocked.
- `run_startup` stages are source composition evidence, not identical to `--headless` autonomous path — both are real product surfaces.
- CognitiveLoopEngine remains OPTIONAL for Stage 2 gate.
