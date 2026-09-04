"""Stage 2.4 — product headless path (source-level mirror of NVRA.exe --headless)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


def test_headless_autonomous_runtime_paper_exit_zero():
    from god.live.autonomous_runtime import run_autonomous_runtime
    codes = [run_autonomous_runtime() for _ in range(20)]
    assert codes == [0] * 20


def test_nvrafx_entry_headless_exit_zero():
    import scripts.nvrafx_entry as entry
    codes = [entry._run_headless_autostart() for _ in range(10)]
    assert all(c == 0 for c in codes)


def test_health_payload_no_live():
    import json
    import io
    from contextlib import redirect_stdout
    import scripts.nvrafx_entry as entry
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = entry.cmd_health()
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["live_authorized"] is False
    assert data["live_trading_enabled"] is False
    assert data["executable"] == "NVRA.exe"
