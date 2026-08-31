"""Phase 4L — Canonical market data models. Immutable where practical. No execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash


class DataQualityState(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INSUFFICIENT = "INSUFFICIENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    PARTIAL = "PARTIAL"


class IngestionStatus(str, Enum):
    OK = "OK"
    NO_VALID_MARKET_DATA = "NO_VALID_MARKET_DATA"
    INVALID_MARKET_DATA = "INVALID_MARKET_DATA"
    STALE_DATA = "STALE_DATA"
    UNKNOWN_DATA_FRESHNESS = "UNKNOWN_DATA_FRESHNESS"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"


@dataclass(frozen=True)
class MarketBar:
    """Single observation point. Missing OHLCV fields stay None — never invented."""

    symbol: str
    timestamp: Optional[str]
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    source_id: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "source_id": self.source_id,
            "metadata": dict(self.metadata),
        }


@dataclass
class SymbolSeries:
    symbol: str
    bars: list[MarketBar] = field(default_factory=list)
    quality: DataQualityState = DataQualityState.UNKNOWN
    quality_reason: str = ""
    source_id: str = "unknown"

    def values(self) -> list[float]:
        """Prefer close; skip missing — no fabrication."""
        out: list[float] = []
        for b in self.bars:
            if b.close is not None:
                out.append(float(b.close))
            elif b.open is not None:
                out.append(float(b.open))
        return out

    def timestamps(self) -> list[str]:
        return [b.timestamp for b in self.bars if b.timestamp]

    def to_observation_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"values": self.values()}
        ts = self.timestamps()
        if ts and len(ts) == len(d["values"]):
            d["timestamps"] = ts
        return d


@dataclass
class MarketDataSnapshot:
    snapshot_id: str
    universe: list[str]
    series: dict[str, SymbolSeries]
    timestamp: str
    quality_status: DataQualityState
    ingestion_status: IngestionStatus
    stale_symbols: list[str] = field(default_factory=list)
    invalid_symbols: list[str] = field(default_factory=list)
    insufficient_symbols: list[str] = field(default_factory=list)
    partial: bool = False
    provenance: Optional[dict[str, Any]] = None
    content_hash: Optional[str] = None
    schema_version: str = "market-data-4l-v1"
    source_id: str = "unknown"
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_observations(self) -> dict[str, dict[str, Any]]:
        """Format consumed by DiscoveryEngine / CognitiveLoopEngine."""
        return {
            sym: ser.to_observation_dict()
            for sym, ser in self.series.items()
            if ser.quality in (DataQualityState.VALID, DataQualityState.STALE)
            and ser.values()
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "universe": list(self.universe),
            "series": {
                k: {
                    "symbol": v.symbol,
                    "bars": [b.to_dict() for b in v.bars],
                    "quality": v.quality.value,
                    "quality_reason": v.quality_reason,
                    "source_id": v.source_id,
                }
                for k, v in self.series.items()
            },
            "timestamp": self.timestamp,
            "quality_status": self.quality_status.value,
            "ingestion_status": self.ingestion_status.value,
            "stale_symbols": list(self.stale_symbols),
            "invalid_symbols": list(self.invalid_symbols),
            "insufficient_symbols": list(self.insufficient_symbols),
            "partial": self.partial,
            "provenance": dict(self.provenance) if self.provenance else None,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


def make_snapshot_id(
    universe: list[str],
    fingerprint: str,
    schema_version: str = "market-data-4l-v1",
) -> str:
    return "snap-" + content_hash(
        {"u": sorted(universe), "f": fingerprint, "v": schema_version}
    )[:24]


def series_fingerprint(series_map: dict[str, SymbolSeries]) -> str:
    payload = {
        sym: [
            {
                "t": b.timestamp,
                "c": b.close,
                "o": b.open,
                "h": b.high,
                "l": b.low,
                "v": b.volume,
            }
            for b in ser.bars
        ]
        for sym, ser in sorted(series_map.items())
    }
    return content_hash(payload)
