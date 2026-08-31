"""Deterministic paper fill simulator for N.U.N.G. — no price invention."""

from __future__ import annotations

from typing import Any, Optional

from god.research.provenance import content_hash

from .models import PaperFill, build_paper_provenance, make_fill_id


def extract_reference_price(
    market_observation: Optional[dict[str, Any]],
    symbol: str,
    *,
    now_iso: Optional[str] = None,
) -> tuple[Optional[float], str]:
    """
    Read last close/value from observation. Never invent.
    Returns (price, reason).
    """
    if not market_observation:
        return None, "missing_market_observation"
    # formats: {symbol: {values: [...]}} or {values: [...], timestamps: [...]}
    obs = market_observation.get(symbol) or market_observation.get(symbol.upper())
    if obs is None and "values" in market_observation:
        obs = market_observation
    if not isinstance(obs, dict):
        return None, "malformed_observation"
    values = obs.get("values") or obs.get("closes")
    if not values:
        return None, "empty_values"
    timestamps = obs.get("timestamps")
    if timestamps and now_iso:
        # reject if last timestamp is in the future
        last_ts = timestamps[-1] if timestamps else None
        if last_ts and last_ts > now_iso:
            return None, "future_timestamp"
        # chronology check
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1]:
                return None, "chronology_violation"
    try:
        price = float(values[-1])
    except (TypeError, ValueError):
        return None, "non_numeric_price"
    if price != price:  # NaN
        return None, "nan_price"
    return price, "ok"


def simulate_fill(
    *,
    paper_execution_id: str,
    symbol: str,
    market_observation: Optional[dict[str, Any]],
    simulated_at: str,
    snapshot_id: Optional[str] = None,
    now_iso: Optional[str] = None,
) -> tuple[Optional[PaperFill], str]:
    price, reason = extract_reference_price(
        market_observation, symbol, now_iso=now_iso
    )
    if price is None:
        return None, reason
    payload = {
        "paper_execution_id": paper_execution_id,
        "symbol": symbol,
        "reference_price": price,
        "snapshot_id": snapshot_id or "",
    }
    fid = make_fill_id(payload)
    fill = PaperFill(
        fill_id=fid,
        paper_execution_id=paper_execution_id,
        symbol=symbol,
        reference_price=price,
        simulated_at=simulated_at,
        content_hash=content_hash(payload),
        source_snapshot_id=snapshot_id,
        provenance=build_paper_provenance(payload),
        notes="reference_last_close_only",
    )
    return fill, "ok"
