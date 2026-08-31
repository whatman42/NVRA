"""EA compile state machine — honest about MetaEditor availability.

Never fabricates successful .ex4/.ex5 compilation on Linux.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from god.bridge.integrity import sha256_file
from god.bridge.models import Platform
from god.bridge.windows.metaeditor import MetaEditorDiscovery, MetaEditorInfo, MetaEditorStatus


class CompileStatus(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    DISCOVERED = "DISCOVERED"
    COMPILING = "COMPILING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ARTIFACT_MISSING = "ARTIFACT_MISSING"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"


@dataclass
class CompileResult:
    status: CompileStatus
    platform: Optional[str] = None
    source_path: Optional[str] = None
    artifact_path: Optional[str] = None
    metaeditor_path: Optional[str] = None
    sha256: Optional[str] = None
    message: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "platform": self.platform,
            "source_path": self.source_path,
            "artifact_path": self.artifact_path,
            "metaeditor_path": self.metaeditor_path,
            "sha256": self.sha256,
            "message": self.message,
            "metadata": dict(self.metadata),
        }


class EACompiler:
    """Compile MQL source via MetaEditor when available.

    Optional inject ``compile_runner`` for tests only (must be explicitly named mock).
    """

    def __init__(
        self,
        *,
        metaeditor: Optional[MetaEditorDiscovery] = None,
        system: Optional[str] = None,
        compile_runner: Optional[Callable[[str, str, str], CompileResult]] = None,
        path_probe: Optional[Callable[[str], bool]] = None,
    ) -> None:
        import platform as _plat

        self._system = system if system is not None else _plat.system()
        self.metaeditor = metaeditor or MetaEditorDiscovery(system=self._system)
        self._runner = compile_runner
        self._probe = path_probe or (lambda p: Path(p).exists())

    def compile(
        self,
        source_path: str,
        *,
        platform: Platform | str,
        output_path: Optional[str] = None,
        editor: Optional[MetaEditorInfo] = None,
    ) -> CompileResult:
        plat = platform if isinstance(platform, Platform) else Platform(platform)
        if self._system != "Windows" and self._runner is None:
            return CompileResult(
                status=CompileStatus.UNAVAILABLE,
                platform=plat.value,
                source_path=source_path,
                message="COMPILE_UNAVAILABLE: host is not Windows (no MetaEditor)",
            )

        if not self._probe(source_path):
            return CompileResult(
                status=CompileStatus.ARTIFACT_MISSING,
                platform=plat.value,
                source_path=source_path,
                message=f"source missing: {source_path}",
            )

        ed = editor
        if ed is None:
            found = self.metaeditor.discover()
            avail = self.metaeditor.availability()
            if avail == MetaEditorStatus.NOT_WINDOWS:
                return CompileResult(
                    status=CompileStatus.UNAVAILABLE,
                    platform=plat.value,
                    source_path=source_path,
                    message="COMPILE_UNAVAILABLE: NOT_WINDOWS",
                )
            if avail == MetaEditorStatus.NOT_FOUND or not found:
                return CompileResult(
                    status=CompileStatus.UNAVAILABLE,
                    platform=plat.value,
                    source_path=source_path,
                    message="COMPILE_UNAVAILABLE: MetaEditor not found",
                )
            if avail == MetaEditorStatus.AMBIGUOUS:
                return CompileResult(
                    status=CompileStatus.UNAVAILABLE,
                    platform=plat.value,
                    source_path=source_path,
                    message="COMPILE_UNAVAILABLE: MetaEditor AMBIGUOUS — select explicitly",
                    metadata={"candidates": [e.to_dict() for e in found]},
                )
            ed = found[0]

        if output_path is None:
            suffix = ".ex5" if plat == Platform.MT5 else ".ex4"
            output_path = str(Path(source_path).with_suffix(suffix))

        if self._runner is not None:
            return self._runner(ed.path, source_path, output_path)

        return CompileResult(
            status=CompileStatus.UNAVAILABLE,
            platform=plat.value,
            source_path=source_path,
            metaeditor_path=ed.path,
            message=(
                "COMPILE_UNAVAILABLE: MetaEditor discovered but compile runner not configured; "
                "real compile requires Windows host integration"
            ),
            metadata={"metaeditor_status": "DISCOVERED"},
        )

    def verify_artifact(self, artifact_path: str) -> CompileResult:
        if not self._probe(artifact_path):
            return CompileResult(
                status=CompileStatus.ARTIFACT_MISSING,
                artifact_path=artifact_path,
                message="artifact missing",
            )
        try:
            digest = sha256_file(artifact_path)
            size = Path(artifact_path).stat().st_size
            if size <= 0:
                return CompileResult(
                    status=CompileStatus.ARTIFACT_INVALID,
                    artifact_path=artifact_path,
                    sha256=digest,
                    message="artifact empty",
                )
            return CompileResult(
                status=CompileStatus.SUCCESS,
                artifact_path=artifact_path,
                sha256=digest,
                message="artifact present",
                metadata={"size_bytes": size},
            )
        except OSError as e:
            return CompileResult(
                status=CompileStatus.ARTIFACT_INVALID,
                artifact_path=artifact_path,
                message=str(e),
            )
