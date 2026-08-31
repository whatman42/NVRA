"""Cognitive-layer control commands for N.U.N.G. — never execution commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .models import ControlCommandType


@dataclass(frozen=True)
class ControlCommand:
    command_type: ControlCommandType
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_type": self.command_type.value,
            "payload": dict(self.payload) if self.payload else {},
        }


def parse_command(name: str, payload: Optional[dict[str, Any]] = None) -> ControlCommand:
    return ControlCommand(command_type=ControlCommandType(name), payload=payload)
