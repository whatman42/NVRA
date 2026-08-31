"""Artifact registry — maps platform → expected EA binary content + integrity.

On production Windows hosts, load real .ex4/.ex5 from a known artifacts dir.
On Linux CI, use injectable fixture bytes so installer/integrity can be tested.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from god.bridge.integrity import ArtifactSpec, sha256_bytes
from god.bridge.models import Platform

# Canonical EA filenames (compiled)
EA_NAME_MT4 = "NUNG_Bridge.ex4"
EA_NAME_MT5 = "NUNG_Bridge.ex5"
EA_VERSION = "0.1.0-3bb"

# Minimal fixture payloads for CI (not valid MT binaries — integrity only)
_FIXTURE_MT4 = b"NUNG-BRIDGE-MT4-FIXTURE-v0.1.0\n" + b"\x00" * 64
_FIXTURE_MT5 = b"NUNG-BRIDGE-MT5-FIXTURE-v0.1.0\n" + b"\x00" * 64


class ArtifactRegistry:
    """Resolves EA bytes + ArtifactSpec per platform.

    Injectable for tests; default uses in-memory fixtures.
    """

    def __init__(
        self,
        *,
        mt4_bytes: Optional[bytes] = None,
        mt5_bytes: Optional[bytes] = None,
        version: str = EA_VERSION,
        artifacts_dir: Optional[Path] = None,
    ) -> None:
        self._version = version
        self._artifacts_dir = Path(artifacts_dir) if artifacts_dir else None
        self._mt4 = mt4_bytes if mt4_bytes is not None else _FIXTURE_MT4
        self._mt5 = mt5_bytes if mt5_bytes is not None else _FIXTURE_MT5

    def get_bytes(self, platform: Platform | str) -> bytes:
        plat = platform if isinstance(platform, Platform) else Platform(platform)
        if plat == Platform.MT4:
            data = self._load_from_dir(EA_NAME_MT4)
            return data if data is not None else self._mt4
        if plat == Platform.MT5:
            data = self._load_from_dir(EA_NAME_MT5)
            return data if data is not None else self._mt5
        raise ValueError(f"unsupported platform for EA artifact: {plat}")

    def get_spec(self, platform: Platform | str) -> ArtifactSpec:
        plat = platform if isinstance(platform, Platform) else Platform(platform)
        data = self.get_bytes(plat)
        name = EA_NAME_MT4 if plat == Platform.MT4 else EA_NAME_MT5
        return ArtifactSpec(
            name=name,
            version=self._version,
            sha256=sha256_bytes(data),
            size_bytes=len(data),
            platform=plat.value,
            source_label="fixture" if self._artifacts_dir is None else "artifacts_dir",
        )

    def _load_from_dir(self, filename: str) -> Optional[bytes]:
        if self._artifacts_dir is None:
            return None
        path = self._artifacts_dir / filename
        if not path.is_file():
            return None
        return path.read_bytes()


_DEFAULT: Optional[ArtifactRegistry] = None


def get_default_registry() -> ArtifactRegistry:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ArtifactRegistry()
    return _DEFAULT
