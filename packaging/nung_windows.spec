# DEPRECATED — product binary is NVRAFX.exe only.
# This file redirects to the unified NVRAFX one-file build so legacy scripts
# do not produce NUNG.exe.
# Prefer: packaging/nvrafx_onefile.spec

block_cipher = None

a = Analysis(
    ['../scripts/nvrafx_entry.py'],
    pathex=['..'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'god.app',
        'god.auth',
        'god.admin',
        'god.comms',
        'god.persist',
        'god.mt5_runtime',
        'god.keygen',
        'god.loop',
        'god.production',
        'god.ml',
        'cryptography',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'tkinter'],
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
    name='NVRAFX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
