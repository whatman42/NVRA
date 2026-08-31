"""CLI: python -m god.bridge.windows

Prints redacted Windows integration diagnostic JSON-ish text.
Never prints secrets.
"""

from __future__ import annotations

import json
import sys

from god.bridge.windows.diagnostic import WindowsDiagnostic


def main(argv: list[str] | None = None) -> int:
    report = WindowsDiagnostic().run()
    print("N.U.N.G Windows Integration Diagnostic")
    print("=" * 40)
    data = report.to_dict()
    print(json.dumps(data, indent=2, default=str))
    if not report.is_windows:
        print("\nStatus: WINDOWS_UNAVAILABLE — architecture only; real MT verification pending.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
