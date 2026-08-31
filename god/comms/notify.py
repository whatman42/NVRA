"""Voice / text notifications — name from authenticated identity only."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NotifySettings:
    sound_enabled: bool = True
    voice_enabled: bool = True
    volume: float = 0.8  # 0.0–1.0
    do_not_disturb: bool = False


@dataclass
class Notification:
    kind: str
    text: str
    spoken: str


class NotificationService:
    def __init__(self) -> None:
        self.settings = NotifySettings()
        self.history: List[Notification] = []

    def configure(
        self,
        *,
        sound: Optional[bool] = None,
        voice: Optional[bool] = None,
        volume: Optional[float] = None,
        dnd: Optional[bool] = None,
    ) -> NotifySettings:
        if sound is not None:
            self.settings.sound_enabled = bool(sound)
        if voice is not None:
            self.settings.voice_enabled = bool(voice)
        if volume is not None:
            self.settings.volume = max(0.0, min(1.0, float(volume)))
        if dnd is not None:
            self.settings.do_not_disturb = bool(dnd)
        return self.settings

    def welcome(self, display_name: str) -> Notification:
        """display_name MUST come from authenticated profile, not free input as identity proof."""
        name = (display_name or "pengguna").strip() or "pengguna"
        spoken = f"Halo {name}, NUNG sudah aktif."
        n = Notification(kind="WELCOME", text=spoken, spoken=spoken)
        if not self.settings.do_not_disturb:
            self.history.append(n)
        return n

    def event(self, kind: str, message: str, display_name: str = "") -> Notification:
        prefix = f"{display_name}, " if display_name else ""
        text = f"{prefix}{message}"
        n = Notification(kind=kind, text=text, spoken=text if self.settings.voice_enabled else "")
        if not self.settings.do_not_disturb:
            self.history.append(n)
        return n
