"""Model / artifact compatibility checks for upgrades."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Application artifact schema the binary understands
ARTIFACT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CompatResult:
    compatible: bool
    detail: str
    use_fallback: bool = False


def check_model_artifact_schema(
    meta: dict[str, object] | None,
    *,
    app_schema: int = ARTIFACT_SCHEMA_VERSION,
) -> CompatResult:
    """Validate ACTIVE model metadata against this app version."""
    if meta is None:
        return CompatResult(False, "missing metadata", use_fallback=True)
    ver = meta.get("schema_version", meta.get("schema"))
    if ver is None:
        # legacy unknown — do not auto-activate
        return CompatResult(False, "schema_version missing", use_fallback=True)
    try:
        v = int(str(ver))
    except (TypeError, ValueError):
        return CompatResult(False, "schema_version not int", use_fallback=True)
    if v > app_schema:
        return CompatResult(False, f"artifact schema {v} > app {app_schema}", use_fallback=True)
    if v < 1:
        return CompatResult(False, f"invalid schema {v}", use_fallback=True)
    return CompatResult(True, "ok")


