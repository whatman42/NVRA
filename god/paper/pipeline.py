"""Phase 5G — N.U.N.G. paper pipeline facade."""

from __future__ import annotations

from .orchestrator import PaperOrchestrator, PaperPipelineResult, PipelineStatus

__all__ = ["PaperOrchestrator", "PaperPipelineResult", "PipelineStatus", "run_paper_cycle"]


def run_paper_cycle(decision, **kwargs) -> PaperPipelineResult:
    """Canonical entry point for paper-only end-to-end cycle."""
    return PaperOrchestrator().run_paper_cycle(decision, **kwargs)
