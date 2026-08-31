# DEPRECATED — product binary is NVRAFX.exe only.
# Redirected to unified NVRAFX entry so legacy scripts do not produce NVRA.exe.
# Prefer: packaging/nvrafx_onefile.spec

block_cipher = None

a = Analysis(
    ['../scripts/nvrafx_entry.py'],
    pathex=['..'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'god.nvra_app',
        'god.production',
        'god.runtime',
        'god.loop',
        'god.paper',
        'god.ml',
        'god.ml.adaptive',
    ],
    excludes=['PyQt5', 'matplotlib'],
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
)
