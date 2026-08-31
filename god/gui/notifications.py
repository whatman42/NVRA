"""Desktop notification sound helper for the NVRA GUI.

Presentation-only: it never touches trading/execution state.
"""
from __future__ import annotations

import os
from pathlib import Path


class NotificationSound:
    """System notification sound with a persistent mute switch."""

    def __init__(self, data_dir: Path) -> None:
        self._marker = Path(data_dir) / ".notification_sound_muted"
        self._marker.parent.mkdir(parents=True, exist_ok=True)

    @property
    def muted(self) -> bool:
        return self._marker.exists()

    def set_muted(self, muted: bool) -> None:
        if muted:
            self._marker.write_text("muted\n", encoding="utf-8")
        else:
            try:
                self._marker.unlink()
            except FileNotFoundError:
                pass

    def play(self) -> bool:
        """Play a short OS notification sound; return False when muted/unavailable."""
        if self.muted:
            return False
        if os.name == "nt":
            try:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return True
            except Exception:
                return False
        # Non-Windows: keep this presentation-only and dependency-free.
        try:
            print("\\a", end="", flush=True)
            return True
        except Exception:
            return False
