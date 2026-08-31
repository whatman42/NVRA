"""Market data ingestion — bounded, fail-closed, deterministic snapshots."""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance

from .models import (
    DataQualityState,
    IngestionStatus,
    MarketDataSnapshot,
    SymbolSeries,
    make_snapshot_id,
    series_fingerprint,
)
from .source import MarketDataSource
from .validation import validate_series


class MarketDataIngestion:
    def __init__(
        self,
        source: MarketDataSource,
        *,
        max_symbols: int = 500,
        max_bars: int = 5000,
        min_bars: int = 1,
        max_age_seconds: Optional[float] = None,
        now_iso: Optional[str] = None,
        schema_version: str = "market-data-4l-v1",
        use_integrity_gate: bool = False,
        require_aware_timestamps: bool = False,
    ) -> None:
        self.source = source
        self.max_symbols = max_symbols
        self.max_bars = max_bars
        self.min_bars = min_bars
        self.max_age_seconds = max_age_seconds
        self.now_iso = now_iso
        self.schema_version = schema_version
        self.use_integrity_gate = use_integrity_gate
        self.require_aware_timestamps = require_aware_timestamps
        self._cache: dict[str, MarketDataSnapshot] = {}

    def ingest(self) -> MarketDataSnapshot:
        source_id = getattr(self.source, "source_id", "unknown")
        try:
            universe = list(self.source.fetch_universe())
        except Exception:
            universe = []

        # dedupe deterministic
        seen: set[str] = set()
        ordered: list[str] = []
        for s in universe:
            su = str(s).strip().upper()
            if su and su not in seen:
                seen.add(su)
                ordered.append(su)

        truncated_universe = False
        if len(ordered) > self.max_symbols:
            ordered = ordered[: self.max_symbols]
            truncated_universe = True

        series_map: dict[str, SymbolSeries] = {}
        invalid: list[str] = []
        insufficient: list[str] = []
        stale: list[str] = []

        for sym in ordered:
            try:
                bars = self.source.fetch_bars(sym, max_bars=self.max_bars)
            except Exception:
                invalid.append(sym)
                series_map[sym] = SymbolSeries(
                    symbol=sym,
                    bars=[],
                    quality=DataQualityState.INVALID,
                    quality_reason="fetch_error",
                    source_id=source_id,
                )
                continue
            raw_series = SymbolSeries(
                symbol=sym, bars=list(bars), source_id=source_id
            )
            if self.use_integrity_gate:
                from .integrity import integrity_check_series
                validated = integrity_check_series(
                    raw_series,
                    now_iso=self.now_iso,
                    require_aware_timestamps=self.require_aware_timestamps,
                    min_bars=self.min_bars,
                )
            else:
                validated = validate_series(
                    raw_series,
                    now_iso=self.now_iso,
                    min_bars=self.min_bars,
                    max_age_seconds=self.max_age_seconds,
                )
            series_map[sym] = validated
            if validated.quality == DataQualityState.INVALID:
                invalid.append(sym)
            elif validated.quality == DataQualityState.INSUFFICIENT:
                insufficient.append(sym)
            elif validated.quality == DataQualityState.STALE:
                stale.append(sym)
            elif validated.quality == DataQualityState.UNKNOWN:
                insufficient.append(sym)

        fp = series_fingerprint(series_map)
        snap_id = make_snapshot_id(ordered, fp, self.schema_version)
        if snap_id in self._cache:
            return self._cache[snap_id]

        valid_count = sum(
            1 for s in series_map.values() if s.quality == DataQualityState.VALID
        )
        partial = bool(invalid or insufficient or stale) and valid_count > 0
        if truncated_universe:
            partial = True

        if not ordered:
            status = IngestionStatus.EMPTY
            q = DataQualityState.INSUFFICIENT
        elif valid_count == 0 and (invalid or insufficient):
            status = (
                IngestionStatus.INVALID_MARKET_DATA
                if invalid and not insufficient
                else IngestionStatus.NO_VALID_MARKET_DATA
            )
            q = DataQualityState.INVALID if invalid else DataQualityState.INSUFFICIENT
        elif partial:
            status = IngestionStatus.PARTIAL
            q = DataQualityState.PARTIAL
        else:
            status = IngestionStatus.OK
            q = DataQualityState.VALID

        prov = build_provenance(
            origin="market_data_ingestion",
            payload={
                "snapshot_id": snap_id,
                "universe": ordered,
                "source_id": source_id,
                "status": status.value,
            },
        )
        snap = MarketDataSnapshot(
            snapshot_id=snap_id,
            universe=ordered,
            series=series_map,
            timestamp=utc_now(),
            quality_status=q,
            ingestion_status=status,
            stale_symbols=stale,
            invalid_symbols=invalid,
            insufficient_symbols=insufficient,
            partial=partial,
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            content_hash=fp,
            schema_version=self.schema_version,
            source_id=source_id,
            notes="truncated_universe" if truncated_universe else "",
            metadata={
                "max_symbols": self.max_symbols,
                "max_bars": self.max_bars,
                "valid_count": valid_count,
                "requested_count": len(ordered),
                "received_count": valid_count,
            },
        )
        self._cache[snap_id] = snap
        return snap
