"""MetaEditor discovery — dynamic, injectable, no mandatory hard paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Sequence

from god.bridge.models import Platform, TerminalInstance
from god.bridge.windows.identity import TerminalIdentity


class MetaEditorStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_FOUND = "NOT_FOUND"
    NOT_WINDOWS = "NOT_WINDOWS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass
class MetaEditorInfo:
    path: str
    status: MetaEditorStatus = MetaEditorStatus.AVAILABLE
    version: Optional[str] = None
    related_platform: Optional[str] = None
    provenance: str = "unknown"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "status": self.status.value,
            "version": self.version,
            "related_platform": self.related_platform,
            "provenance": self.provenance,
            "metadata": dict(self.metadata),
        }


_EDITOR_NAMES = (
    "metaeditor64.exe",
    "metaeditor.exe",
    "MetaEditor64.exe",
    "MetaEditor.exe",
)


class MetaEditorDiscovery:
    """Discover MetaEditor via injectable PATH/which/probe/relationship."""

    def __init__(
        self,
        *,
        system: Optional[str] = None,
        which: Optional[Callable[[str], Optional[str]]] = None,
        path_probe: Optional[Callable[[str], bool]] = None,
        extra_candidates: Optional[Sequence[str]] = None,
    ) -> None:
        import platform as _plat

        self._system = system if system is not None else _plat.system()
        self._which = which or _default_which
        self._probe = path_probe or (lambda p: Path(p).exists())
        self._extra = list(extra_candidates or [])

    def availability(self) -> MetaEditorStatus:
        if self._system != "Windows":
            return MetaEditorStatus.NOT_WINDOWS
        found = self.discover()
        if not found:
            return MetaEditorStatus.NOT_FOUND
        if len(found) > 1:
            return MetaEditorStatus.AMBIGUOUS
        return MetaEditorStatus.AVAILABLE

    def discover(self) -> list[MetaEditorInfo]:
        if self._system != "Windows":
            return []
        found: list[MetaEditorInfo] = []
        seen: set[str] = set()

        for name in _EDITOR_NAMES:
            path = self._which(name)
            if path and self._probe(path) and path.lower() not in seen:
                seen.add(path.lower())
                found.append(
                    MetaEditorInfo(
                        path=path,
                        status=MetaEditorStatus.AVAILABLE,
                        provenance="path",
                    )
                )

        for path in self._extra:
            if path and self._probe(path) and path.lower() not in seen:
                seen.add(path.lower())
                found.append(
                    MetaEditorInfo(
                        path=path,
                        status=MetaEditorStatus.AVAILABLE,
                        provenance="injected",
                    )
                )

        return found

    def find_for_terminal(
        self,
        terminal: TerminalInstance | TerminalIdentity,
    ) -> Optional[MetaEditorInfo]:
        """Prefer MetaEditor next to terminal executable when present."""
        exe = getattr(terminal, "executable_path", None)
        plat = getattr(terminal, "platform", None)
        plat_s = plat.value if isinstance(plat, Platform) else str(plat or "")

        if exe:
            root = Path(exe).resolve().parent
            for name in _EDITOR_NAMES:
                candidate = root / name
                if self._probe(str(candidate)):
                    return MetaEditorInfo(
                        path=str(candidate),
                        status=MetaEditorStatus.AVAILABLE,
                        related_platform=plat_s or None,
                        provenance="terminal_sibling",
                    )

        all_ed = self.discover()
        if len(all_ed) == 1:
            ed = all_ed[0]
            ed.related_platform = plat_s or ed.related_platform
            return ed
        if not all_ed:
            return None
        return None


def _default_which(cmd: str) -> Optional[str]:
    from shutil import which

    return which(cmd)
