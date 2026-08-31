# -*- mode: python ; coding: utf-8 -*-
# PyInstaller ONE-FOLDER spec for CRYPTO Windows x64.
# Build (on Windows):
#   pyinstaller packaging/CRYPTO.spec --noconfirm --clean
#
# Hidden imports are limited to modules actually referenced by the codebase.

import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules
from pathlib import Path

block_cipher = None
SPECDIR = Path(SPECPATH).resolve().parent
ROOT = SPECDIR.parent

# Optional GUI — include only if PySide6 is installed in the build env
def _has_pyside6() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False

# Native ML/GUI packages are imported lazily at runtime, so collect their
# submodules/binaries when present in the Windows build environment.
_collected_datas = []
_collected_binaries = []
_collected_hidden = []

def _collect_optional(mod: str) -> None:
    try:
        datas_, binaries_, hidden_ = collect_all(mod)
    except Exception:
        return
    _collected_datas.extend(datas_)
    _collected_binaries.extend(binaries_)
    _collected_hidden.extend(hidden_)

for _mod in ("PySide6", "numpy", "scipy", "sklearn", "lightgbm", "xgboost", "catboost"):
    _collect_optional(_mod)

hiddenimports = [
    # Core
    "crypto",
    "crypto.runtime",
    "crypto.runtime.entrypoint",
    "crypto.runtime.paths",
    # Exchanges
    "crypto.exchanges",
    "crypto.exchanges.binance",
    "crypto.exchanges.tokocrypto",
    "crypto.exchanges.indodax",
    "crypto.exchanges.factory",
    "crypto.exchanges.ccxt_base",
    "ccxt",
    # ML optional / fallback
    "crypto.ml",
    "crypto.ml.backends",
    "crypto.ml.features",
    # Control / notify / telegram / gui
    "crypto.control",
    "crypto.notify",
    "crypto.telegram",
    "crypto.gui",
    # Hardware / governor / recovery
    "crypto.hardware",
    "crypto.governor",
    "crypto.recovery",
    "crypto.ml.provenance",
    "crypto.ml.fallback",
    "crypto.runtime.migrate",
    "crypto.production.gates",
    "crypto.production",
    # Stdlib needed under freeze
    "multiprocessing",
    "sqlite3",
]

if _has_pyside6():
    hiddenimports += [
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ]

# Optional ML backends — only if present (must not be mandatory)
for mod in ("lightgbm", "xgboost", "sklearn", "catboost"):
    try:
        __import__(mod)
        hiddenimports.append(mod)
    except ImportError:
        pass

hiddenimports += _collected_hidden
datas = list(_collected_datas)
binaries = list(_collected_binaries)
resources = ROOT / "resources"
if resources.is_dir():
    datas.append((str(resources), "resources"))

a = Analysis(
    [str(ROOT / "src" / "crypto" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "tensorflow",
        "jax",
        "matplotlib",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CRYPTO",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can break native ML DLLs
    console=False,  # polished desktop GUI; diagnostics remain in log files
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CRYPTO",
)
