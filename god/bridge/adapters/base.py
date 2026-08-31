"""TerminalAdapter protocol / base."""

from __future__ import annotations

from typing import Protocol

from god.bridge.models import Platform, TerminalInstance


class TerminalAdapter(Protocol):
    """Platform-specific helpers for Experts path and EA naming."""

    platform: Platform

    def experts_subdir(self) -> str:
        """Relative Experts path segment under data/install root."""
        ...

    def ea_filename(self) -> str:
        """Compiled EA filename for this platform."""
        ...

    def normalize_terminal(self, terminal: TerminalInstance) -> TerminalInstance:
        """Fill experts_path / data_path when inferable."""
        ...
