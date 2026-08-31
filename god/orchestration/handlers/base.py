"""Handler protocol — thin adapters over 4A–4F engines."""

from __future__ import annotations

from typing import Protocol

from god.orchestration.models.context import CognitiveContext
from god.orchestration.models.events import CognitiveEvent


class Handler(Protocol):
    name: str

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        """Process event; return follow-on cognitive events (may be empty)."""
        ...
