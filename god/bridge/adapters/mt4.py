"""MT4-specific adapter."""

from __future__ import annotations

from pathlib import Path

from god.bridge.artifacts.registry import EA_NAME_MT4
from god.bridge.models import Platform, TerminalInstance, TerminalStatus


class MT4Adapter:
    platform = Platform.MT4

    def experts_subdir(self) -> str:
        return str(Path("MQL4") / "Experts")

    def ea_filename(self) -> str:
        return EA_NAME_MT4

    def normalize_terminal(self, terminal: TerminalInstance) -> TerminalInstance:
        experts = terminal.experts_path
        data = terminal.data_path
        if not experts and terminal.executable_path:
            root = Path(terminal.executable_path).resolve().parent
            data = data or str(root)
            experts = str(root / "MQL4" / "Experts")
        elif not experts and data:
            experts = str(Path(data) / "MQL4" / "Experts")
        return TerminalInstance.create(
            platform=Platform.MT4,
            executable_path=terminal.executable_path,
            data_path=data,
            experts_path=experts,
            version=terminal.version,
            build=terminal.build,
            process_id=terminal.process_id,
            status=terminal.status if terminal.status != TerminalStatus.UNKNOWN else TerminalStatus.DISCOVERED,
            terminal_id=terminal.terminal_id,
            discovered_at=terminal.discovered_at,
            metadata={**terminal.metadata, "adapter": "MT4"},
        )
