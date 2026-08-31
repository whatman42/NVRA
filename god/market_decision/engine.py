"""TAHAP 4 / Phase 1 MarketDecisionEngine.

Path: data → features → ML prediction → signal → risk → intent.
Never calls broker / MT5 order_send (exchange_submissions always 0).
ML can provide BUY/SELL/HOLD when gate open; never forces entry on invalid data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import hashlib
import time

from god.discovery.ranking import rank_candidates
from god.discovery.models import Candidate, EligibilityStatus, QualityStatus
from god.research.regime.models import RegimeLabel
from god.execution_contract.models import (
    ExecutionIntent,
    IntentAction,
    IntentStatus,
)
from god.execution_contract.engine import ExecutionContractEngine
from god.paper.risk import PaperRiskEngine

from .quotes import Quote, validate_quote, QuoteValidation
from .stream_health import StreamHealthMonitor, StreamState
from .signal import MarketSignal, SignalDirection, build_signal


@dataclass
class PositionView:
    """Minimal position awareness — does not mutate position DB."""

    symbol: str
    side: str = "FLAT"  # LONG | SHORT | FLAT
    quantity: float = 0.0
    avg_entry: Optional[float] = None
    recovery_incomplete: bool = False


@dataclass
class OrderIntentDraft:
    intent_id: str
    symbol: str
    side: str
    quantity: float
    reference_price: float
    timestamp: float
    signal_id: str
    strategy_id: str
    regime: str
    confidence: float
    reason: str
    valid_until: float
    expired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "reference_price": self.reference_price,
            "timestamp": self.timestamp,
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "regime": self.regime,
            "confidence": self.confidence,
            "reason": self.reason,
            "valid_until": self.valid_until,
            "expired": self.expired,
        }


@dataclass
class MarketDecisionResult:
    allowed_new_entry: bool
    action: str  # HOLD | ENTER | EXIT | REDUCE | NO_TRADE
    reasons: list[str] = field(default_factory=list)
    quote_validation: Optional[QuoteValidation] = None
    stream_state: Optional[str] = None
    regime: str = "UNKNOWN"
    signal: Optional[MarketSignal] = None
    ranked_symbols: list[str] = field(default_factory=list)
    intent: Optional[OrderIntentDraft] = None
    risk_allowed: bool = False
    risk_reason: str = ""
    exchange_submissions: int = 0  # always 0 in decision path
    execution_contract_status: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_new_entry": self.allowed_new_entry,
            "action": self.action,
            "reasons": list(self.reasons),
            "quote_validation": self.quote_validation.to_dict() if self.quote_validation else None,
            "stream_state": self.stream_state,
            "regime": self.regime,
            "signal": self.signal.to_dict() if self.signal else None,
            "ranked_symbols": list(self.ranked_symbols),
            "intent": self.intent.to_dict() if self.intent else None,
            "risk_allowed": self.risk_allowed,
            "risk_reason": self.risk_reason,
            "exchange_submissions": 0,
            "execution_contract_status": self.execution_contract_status,
        }




class MarketDecisionEngine:
    def __init__(
        self,
        *,
        stream: Optional[StreamHealthMonitor] = None,
        intent_ttl_seconds: float = 30.0,
        default_qty: float = 0.01,
        safe_mode: bool = False,
        prefer_ml_signal: bool = True,
    ) -> None:
        self.stream = stream or StreamHealthMonitor()
        self.intent_ttl_seconds = intent_ttl_seconds
        self.default_qty = default_qty
        self.safe_mode = safe_mode
        self.prefer_ml_signal = prefer_ml_signal
        self._seen_signal_ids: set[str] = set()
        self._exec = ExecutionContractEngine()
        try:
            self._risk = PaperRiskEngine()
        except Exception:
            self._risk = None

    def evaluate_universe(self, candidates: Sequence[Candidate]) -> list[Candidate]:
        return rank_candidates(list(candidates))

    def detect_regime_from_closes(self, closes: Sequence[float]) -> str:
        if closes is None or len(closes) < 10:
            return RegimeLabel.UNKNOWN.value
        import numpy as np

        c = np.asarray(closes, dtype=float)
        rets = np.diff(c) / np.maximum(c[:-1], 1e-12)
        vol = float(np.std(rets))
        drift = float(np.mean(rets))
        if vol > 0.02:
            return RegimeLabel.HIGH_VOLATILITY.value
        if vol < 0.002:
            return RegimeLabel.LOW_VOLATILITY.value
        if abs(drift) > vol * 0.5:
            return RegimeLabel.TRENDING.value
        return "RANGING"

    def position_aware_action(
        self,
        signal: MarketSignal,
        position: Optional[PositionView],
    ) -> str:
        if signal.direction == SignalDirection.NO_TRADE:
            return "NO_TRADE"
        if signal.direction == SignalDirection.HOLD:
            return "HOLD"
        pos = position or PositionView(symbol=signal.symbol)
        if pos.recovery_incomplete:
            return "NO_TRADE"
        if pos.side == "FLAT":
            if signal.direction in (SignalDirection.BUY, SignalDirection.SELL):
                return "ENTER"
            return "HOLD"
        if pos.side == "LONG":
            if signal.direction == SignalDirection.BUY:
                return "HOLD"
            if signal.direction == SignalDirection.SELL:
                return "EXIT"
        if pos.side == "SHORT":
            if signal.direction == SignalDirection.SELL:
                return "HOLD"
            if signal.direction == SignalDirection.BUY:
                return "EXIT"
        return "HOLD"

    def build_intent(
        self,
        signal: MarketSignal,
        *,
        reference_price: float,
        quantity: Optional[float] = None,
        now: Optional[float] = None,
    ) -> OrderIntentDraft:
        now = now if now is not None else time.time()
        raw = f"{signal.signal_id}:{signal.symbol}:{signal.direction.value}:{now}"
        intent_id = "intent-" + hashlib.sha256(raw.encode()).hexdigest()[:20]
        side = "BUY" if signal.direction == SignalDirection.BUY else "SELL"
        valid_until = now + self.intent_ttl_seconds
        return OrderIntentDraft(
            intent_id=intent_id,
            symbol=signal.symbol,
            side=side,
            quantity=float(quantity if quantity is not None else self.default_qty),
            reference_price=float(reference_price),
            timestamp=now,
            signal_id=signal.signal_id,
            strategy_id=signal.strategy_id,
            regime=signal.regime,
            confidence=signal.confidence,
            reason=signal.reason,
            valid_until=valid_until,
            expired=False,
        )

    def _signal_from_ml(self, ml_evidence: Any, *, symbol: str, regime: str, strategy_id: str, now: float) -> Optional[tuple[SignalDirection, float, str]]:
        """Map ML evidence → direction. None = fall back to momentum."""
        if ml_evidence is None:
            return None
        if not getattr(ml_evidence, "ml_gate_open", False):
            return None
        pred = getattr(ml_evidence, "prediction", None)
        if pred is None:
            return None
        status = getattr(pred, "status", None)
        status_v = status.value if hasattr(status, "value") else str(status or "")
        if status_v != "VALID":
            return None
        direction = getattr(pred, "direction", None)
        dval = direction.value if hasattr(direction, "value") else str(direction or "")
        conf = float(getattr(pred, "confidence", 0.0) or 0.0)
        prob = float(getattr(pred, "probability", 0.0) or 0.0)
        if dval == "UP":
            return SignalDirection.BUY, max(conf, prob), "ml_up"
        if dval == "DOWN":
            return SignalDirection.SELL, max(conf, prob), "ml_down"
        if dval == "NEUTRAL":
            return SignalDirection.HOLD, conf, "ml_neutral"
        return None

    def run(
        self,
        *,
        quote: Quote,
        closes: Sequence[float] | None = None,
        position: Optional[PositionView] = None,
        candidates: Optional[Sequence[Candidate]] = None,
        strategy_id: str = "tahap4_default",
        now: Optional[float] = None,
        reconciliation_healthy: bool = True,
        ml_evidence: Optional[Any] = None,
        quantity: Optional[float] = None,
    ) -> MarketDecisionResult:
        now = now if now is not None else time.time()
        reasons: list[str] = []

        sh = self.stream.tick(now=now)
        if not sh.allows_new_entry:
            reasons.append(f"stream:{sh.state.value}")

        if self.safe_mode:
            reasons.append("SAFE_MODE")

        if not reconciliation_healthy:
            reasons.append("reconciliation_unhealthy")

        if position and position.recovery_incomplete:
            reasons.append("position_recovery_incomplete")

        ml_meta = None
        ml_gate_closed = False
        if ml_evidence is not None:
            try:
                if not getattr(ml_evidence, "ml_gate_open", False):
                    reasons.append("ml_gate_closed")
                    ml_gate_closed = True
                ml_meta = getattr(ml_evidence, "to_dict", lambda: {})()
            except Exception:
                reasons.append("ml_evidence_error")
                ml_gate_closed = True

        qv = validate_quote(quote, now=now, last_sequence=sh.last_sequence)
        if not qv.ok:
            reasons.extend(list(qv.reasons))

        ranked_symbols: list[str] = []
        if candidates:
            ranked = self.evaluate_universe(candidates)
            ranked_symbols = [getattr(c, "instrument_ref", None) or getattr(c, "candidate_id", "") for c in ranked]

        regime = self.detect_regime_from_closes(closes or [])
        if regime in (RegimeLabel.UNKNOWN.value, "UNCERTAIN"):
            reasons.append(f"regime:{regime}")

        direction = SignalDirection.NO_TRADE
        confidence = 0.0
        reason = "no_signal"

        # Phase 1B: prefer ML-driven signal when gate open and VALID
        ml_sig = None
        if self.prefer_ml_signal and ml_evidence is not None and not ml_gate_closed:
            ml_sig = self._signal_from_ml(
                ml_evidence, symbol=quote.symbol, regime=regime, strategy_id=strategy_id, now=now
            )

        if ml_sig is not None and qv.ok and regime not in (RegimeLabel.UNKNOWN.value, "UNCERTAIN", RegimeLabel.MIXED.value):
            direction, confidence, reason = ml_sig
        elif qv.ok and regime not in (RegimeLabel.UNKNOWN.value, "UNCERTAIN", RegimeLabel.MIXED.value):
            # fallback momentum (legacy)
            if closes and len(closes) >= 3:
                if closes[-1] > closes[-3]:
                    direction = SignalDirection.BUY
                    confidence = 0.6
                    reason = "momentum_up"
                elif closes[-1] < closes[-3]:
                    direction = SignalDirection.SELL
                    confidence = 0.6
                    reason = "momentum_down"
                else:
                    direction = SignalDirection.HOLD
                    confidence = 0.5
                    reason = "flat"
            else:
                direction = SignalDirection.NO_TRADE
                reason = "insufficient_closes"

        sig = build_signal(
            symbol=quote.symbol,
            direction=direction,
            confidence=confidence,
            regime=regime,
            reason=reason,
            data_quality="VALID" if qv.ok else "INVALID",
            strategy_id=strategy_id,
            timestamp=now,
        )

        if sig.signal_id in self._seen_signal_ids:
            reasons.append("duplicate_signal")
            sig = build_signal(
                symbol=quote.symbol,
                direction=SignalDirection.NO_TRADE,
                confidence=0.0,
                regime=regime,
                reason="duplicate_signal",
                data_quality="VALID" if qv.ok else "INVALID",
                strategy_id=strategy_id,
                signal_id=sig.signal_id + "-dup",
                timestamp=now,
            )
        else:
            self._seen_signal_ids.add(sig.signal_id)

        action = self.position_aware_action(sig, position)
        if reasons:
            action = "NO_TRADE"

        allowed = action == "ENTER" and not reasons
        intent = None
        risk_allowed = False
        risk_reason = "not_evaluated"
        exec_status = None

        if allowed and sig.direction in (SignalDirection.BUY, SignalDirection.SELL):
            mid = (quote.bid + quote.ask) / 2.0
            intent = self.build_intent(
                sig, reference_price=mid, quantity=quantity, now=now
            )
            if now > intent.valid_until:
                intent.expired = True
                reasons.append("intent_expired")
                allowed = False
                action = "NO_TRADE"
            else:
                risk_allowed = True
                risk_reason = "pass_default"
                if self._risk is not None:
                    try:
                        if intent.quantity <= 0:
                            risk_allowed = False
                            risk_reason = "invalid_qty"
                    except Exception as e:
                        risk_allowed = False
                        risk_reason = f"risk_error:{e}"
                if not risk_allowed:
                    reasons.append(risk_reason)
                    allowed = False
                    action = "NO_TRADE"
                    intent = None
                else:
                    exec_status = "ROUTED_TO_EXECUTION_CONTRACT_NULL"

        return MarketDecisionResult(
            allowed_new_entry=allowed,
            action=action,
            reasons=reasons,
            quote_validation=qv,
            stream_state=sh.state.value,
            regime=regime,
            signal=sig,
            ranked_symbols=ranked_symbols,
            intent=intent if allowed else intent,
            risk_allowed=risk_allowed if allowed else False,
            risk_reason=risk_reason,
            exchange_submissions=0,
            execution_contract_status=exec_status,
        )
