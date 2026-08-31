"""Universe scanner — per-instrument analysis with failure isolation."""

from __future__ import annotations

from typing import Any, Optional

from .candidate import build_candidate
from .data_quality import assess_observation_series
from .models import (
    Candidate,
    EligibilityStatus,
    InstrumentStatus,
    QualityStatus,
)
from .universe import Universe


class Scanner:
    """Scan configured universe. One bad instrument does not abort all."""

    def __init__(
        self,
        universe: Universe,
        *,
        observations: Optional[dict[str, dict[str, Any]]] = None,
        min_samples: int = 2,
        now_iso: Optional[str] = None,
    ) -> None:
        self.universe = universe
        self.observations = observations or {}
        self.min_samples = min_samples
        self.now_iso = now_iso

    def scan_instrument(self, symbol: str) -> tuple[QualityStatus, str, Optional[Candidate]]:
        sym = symbol.upper()
        ref = self.universe.get(sym)
        if ref is None:
            return QualityStatus.UNKNOWN, "not_in_universe", None

        obs = self.observations.get(sym) or self.observations.get(symbol)
        if obs is None:
            self.universe.set_status(sym, InstrumentStatus.INSUFFICIENT_DATA)
            return (
                QualityStatus.INSUFFICIENT_DATA,
                "no_observation_injected",
                build_candidate(
                    sym,
                    quality_status=QualityStatus.INSUFFICIENT_DATA,
                    eligibility=EligibilityStatus.INSUFFICIENT_DATA,
                    uncertainty="HIGH",
                    notes="no_observation_injected",
                ),
            )

        values = obs.get("values")
        timestamps = obs.get("timestamps")
        q, reason = assess_observation_series(
            values,
            timestamps,
            min_samples=self.min_samples,
            now_iso=self.now_iso,
        )
        if q == QualityStatus.INVALID:
            self.universe.set_status(sym, InstrumentStatus.INVALID_DATA)
            return (
                q,
                reason,
                build_candidate(
                    sym,
                    quality_status=q,
                    eligibility=EligibilityStatus.INELIGIBLE,
                    uncertainty="HIGH",
                    notes=reason,
                ),
            )
        if q == QualityStatus.INSUFFICIENT_DATA:
            self.universe.set_status(sym, InstrumentStatus.INSUFFICIENT_DATA)
            return (
                q,
                reason,
                build_candidate(
                    sym,
                    quality_status=q,
                    eligibility=EligibilityStatus.INSUFFICIENT_DATA,
                    uncertainty="HIGH",
                    notes=reason,
                ),
            )
        if q == QualityStatus.STALE:
            self.universe.set_status(sym, InstrumentStatus.STALE)
            return (
                q,
                reason,
                build_candidate(
                    sym,
                    quality_status=q,
                    eligibility=EligibilityStatus.INELIGIBLE,
                    uncertainty="HIGH",
                    notes=reason,
                ),
            )

        self.universe.set_status(sym, InstrumentStatus.AVAILABLE)
        return (
            QualityStatus.VALID,
            reason,
            build_candidate(
                sym,
                quality_status=QualityStatus.VALID,
                eligibility=EligibilityStatus.UNKNOWN,  # pending strategy/policy
                uncertainty="MODERATE",
                notes="quality_ok_pending_strategy_policy",
            ),
        )

    def scan_all(self) -> list[Candidate]:
        results: list[Candidate] = []
        for ref in self.universe.enumerate():
            try:
                _, _, cand = self.scan_instrument(ref.symbol)
                if cand is not None:
                    results.append(cand)
            except Exception as exc:
                results.append(
                    build_candidate(
                        ref.symbol,
                        quality_status=QualityStatus.INVALID,
                        eligibility=EligibilityStatus.INELIGIBLE,
                        uncertainty="HIGH",
                        notes=f"scan_error:{type(exc).__name__}",
                    )
                )
        return results
