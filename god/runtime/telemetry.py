"""Lightweight cognitive runtime telemetry — no secrets, no orders."""

from __future__ import annotations

from typing import Any

from .models import RuntimeHealth


def health_snapshot(health: RuntimeHealth) -> dict[str, Any]:
    return health.to_dict()
