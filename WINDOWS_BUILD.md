# NVRA Windows Build

On a Windows x64 machine or GitHub Actions:

1. Install Python 3.12.
2. Install `requirements.txt`.
3. Run the regression suite.
4. Run `tools/secret_scan.py`.
5. Run the GUI import smoke test.
6. Build with:
   `python -m PyInstaller packaging/nvrafx_onefile.spec --noconfirm --clean`
7. Verify `dist/NVRA.exe` exists.
8. Verify `NUNG.exe` and `NVRAFX.exe` do not exist as product binaries.
9. Run:
   `dist\NVRA.exe --version`
   `dist\NVRA.exe --health`
   `dist\NVRA.exe --check-config`
10. Launch the GUI with:
   `dist\NVRA.exe --gui`

The repository's Windows GitHub Actions workflows automate these checks.

MT5 terminal is external and must be installed separately. The Python MetaTrader5 package is included in the Windows dependency set so the API layer can be packaged into the executable.

LIVE capital remains blocked until the existing readiness, risk, policy, recovery and explicit operator authorization gates pass. A real broker E2E test on Windows is mandatory before real-money deployment.
