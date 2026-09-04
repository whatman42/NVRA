# NVRA Release Manifest

Canonical Windows binary: NVRA.exe

PyInstaller one-file embeds the Python interpreter and installed Python package dependencies into `NVRA.exe`. External configuration, persistent state, market data and secrets are intentionally not embedded.

See packaging/nvra_onefile.spec and packaging/nvrafx_onefile.spec (legacy alias; product name remains NVRA).
