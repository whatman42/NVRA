"""Phase 3B-C — Windows / MT4 / MT5 compatibility layer (additive).

Linux CI uses injectable mocks. Real terminal verification requires Windows host.
Never claims MT5 verified from fixtures alone.
"""

from .diagnostic import WindowsDiagnostic, WindowsDiagnosticReport
from .identity import (
    IdentityResolution,
    IdentityStatus,
    TerminalIdentity,
    resolve_identities,
)
from .metaeditor import (
    MetaEditorDiscovery,
    MetaEditorInfo,
    MetaEditorStatus,
)
from .compile import CompileResult, CompileStatus, EACompiler
from .observability import (
    ComponentStatus,
    ExecutionGate,
    NUNGHealthSnapshot,
    build_health_snapshot,
)
from .evidence import EALoadEvidence, LoadEvidenceLevel

__all__ = [
    "WindowsDiagnostic",
    "WindowsDiagnosticReport",
    "TerminalIdentity",
    "IdentityStatus",
    "IdentityResolution",
    "resolve_identities",
    "MetaEditorDiscovery",
    "MetaEditorInfo",
    "MetaEditorStatus",
    "CompileStatus",
    "CompileResult",
    "EACompiler",
    "ComponentStatus",
    "ExecutionGate",
    "NUNGHealthSnapshot",
    "build_health_snapshot",
    "EALoadEvidence",
    "LoadEvidenceLevel",
]
