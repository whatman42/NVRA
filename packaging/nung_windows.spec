# LEGACY alias — final product executable is NVRA.exe (not NVRAFX.exe / NUNG.exe).
# Prefer: packaging/nvra_onefile.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH).resolve().parent

hiddenimports = (
    collect_submodules("god")
    + collect_submodules("crypto")
    + collect_submodules("nvra_unified")
)
datas = collect_data_files("god") + collect_data_files("crypto") + collect_data_files("nvra_unified")

block_cipher = None

a = Analysis(
    [str(ROOT / "scripts" / "nvrafx_entry.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=datas + [(str(ROOT / "god" / "gui" / "assets"), "god/gui/assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="NVRA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "god" / "gui" / "assets" / "nvra.ico"),
)
