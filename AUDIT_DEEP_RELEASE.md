# NVRA Unified — Deep Release Audit

## Scope
Static audit of the complete supplied source tree before manual GitHub push.

## Findings and remediation

### 1. Generated artifacts
Removed from release tree:
- all `__pycache__/`
- all `*.pyc` / `*.pyo`
- `.pytest_cache/`

### 2. Dependency mismatch
The source imports optional ML providers that were previously absent from the main requirements file. The canonical `requirements.txt` now includes:
- PyYAML
- LightGBM
- XGBoost
- CatBoost
- PyTorch
- SHAP
- scikit-learn
- GUI/network/credential dependencies
- build/test tooling

`requirements-ml-full.txt` is retained as a compatibility alias to avoid two divergent dependency contracts.

### 3. Python import path conflict
The CRYPTO package lives under `src/crypto` while tests import `crypto`. A repository-level `pyproject.toml` now declares `pythonpath = [".", "src"]`, and Windows CI exports the same paths.

### 4. Build workflow conflict
The repository previously contained workflows capable of producing different product names (`NVRA.exe` vs `NVRAFX.exe`). The canonical product is now **NVRAFX.exe**. The legacy unified workflow was rewritten to build the same canonical artifact.

### 5. Duplicate definitions
There are intentionally repeated class/function names across the `god` and `src/crypto` bounded domains. These are not automatically semantic duplicates. The most important product entrypoint duplication remains documented; the distributed product uses `scripts/nvrafx_entry.py` as the sole public entrypoint.

### 6. Static reachability / dead-code warning
The tree contains many research, compatibility, test, Windows/MT5, and legacy modules that are not statically reachable from the single public entrypoint. They are retained because they are part of the supplied source and may be loaded dynamically or exercised by subsystem tests. They must not be treated as deleted/dead solely from static reachability.

### 7. Live execution surfaces
The source tree intentionally contains legacy/compatibility live-execution implementations and gates. The distributed NVRAFX product contract remains paper-only. The canonical entrypoint does not expose a `--live` option, and release workflows assert that only `NVRAFX.exe` is produced. A future hardening task should physically remove or compile-time exclude live execution implementations if absolute source-level impossibility is required.

## Release invariants

1. PAPER only.
2. No credentials in source/config YAML.
3. Risk ceilings immutable.
4. Data/storage/resource failures fail closed.
5. One canonical Windows product: `NVRAFX.exe`.
6. Python runtime and installed Python packages are embedded by PyInstaller one-file packaging; external config/state/data/secrets remain external.
