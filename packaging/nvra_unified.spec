# NVRA Unified Windows x64 one-file spec.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
root = Path(SPECPATH)
hiddenimports = collect_submodules("god") + collect_submodules("crypto") + collect_submodules("nvra_unified")
datas = []
datas += collect_data_files("god")
datas += collect_data_files("crypto")
a = Analysis(
    [str(root / "scripts" / "nvra_unified_entry.py")],
    pathex=[str(root), str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="NVRA",
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
)
