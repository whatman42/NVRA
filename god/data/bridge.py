"""Bridge MarketDataSnapshot → CognitiveLoopEngine without frozen edits.

Preserves injected-observation test path: callers may still construct
CognitiveLoopEngine(observations=...) directly.
"""

from __future__ import annotations

from typing import Any, Optional

from god.discovery import Universe
from god.loop import CognitiveLoopEngine, CycleResult

from .ingestion import MarketDataIngestion
from .models import IngestionStatus, MarketDataSnapshot
from .source import MarketDataSource


def snapshot_to_loop_kwargs(snapshot: MarketDataSnapshot) -> dict[str, Any]:
    """Build universe + observations for CognitiveLoopEngine."""
    u = Universe(snapshot.universe)
    obs = snapshot.to_observations()
    return {"universe": u, "observations": obs}


def run_cycle_from_source(
    source: MarketDataSource,
    *,
    strategy_registry: Any = None,
    policy_engine: Any = None,
    capital_engine: Any = None,
    drift_engine: Any = None,
    regime_engine: Any = None,
    reality_engine: Any = None,
    max_matrix_cells: int = 256,
    max_attention: int = 50,
    max_symbols: int = 500,
    max_bars: int = 5000,
    min_bars: int = 2,
    now_iso: Optional[str] = None,
    memory_store: Any = None,
) -> tuple[MarketDataSnapshot, Optional[CycleResult]]:
    """
    Ingest → if usable data → CognitiveLoopEngine.run_cycle().
    Returns (snapshot, cycle_result|None).
    """
    ingestion = MarketDataIngestion(
        source,
        max_symbols=max_symbols,
        max_bars=max_bars,
        min_bars=min_bars,
        now_iso=now_iso,
    )
    snap = ingestion.ingest()
    if snap.ingestion_status in (
        IngestionStatus.EMPTY,
        IngestionStatus.NO_VALID_MARKET_DATA,
        IngestionStatus.INVALID_MARKET_DATA,
    ):
        return snap, None
    if not snap.to_observations():
        return snap, None

    kw = snapshot_to_loop_kwargs(snap)
    engine = CognitiveLoopEngine(
        kw["universe"],
        observations=kw["observations"],
        strategy_registry=strategy_registry,
        policy_engine=policy_engine,
        capital_engine=capital_engine,
        drift_engine=drift_engine,
        regime_engine=regime_engine,
        reality_engine=reality_engine,
        max_matrix_cells=max_matrix_cells,
        max_attention=max_attention,
        memory_store=memory_store,
        now_iso=now_iso,
    )
    result = engine.run_cycle()
    return snap, result
