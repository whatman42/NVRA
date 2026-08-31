"""Phase 5D — N.U.N.G. paper portfolio state. Simulation accounting only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.execution_contract.models import ExecutionIntent, IntentAction
from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import PaperExecution, PaperStatus, build_paper_provenance


class PortfolioStatus(str, Enum):
    EMPTY = "EMPTY"
    OPEN_PAPER = "OPEN_PAPER"
    CLOSED_PAPER = "CLOSED_PAPER"
    INVALID = "INVALID"
    CORRUPTED = "CORRUPTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


SCHEMA_VERSION = "paper-portfolio-5d-v1"


@dataclass(frozen=True)
class PaperHolding:
    symbol: str
    entry_price: float
    entry_at: str
    paper_execution_id: str
    intent_id: str
    decision_id: str
    cycle_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "entry_at": self.entry_at,
            "paper_execution_id": self.paper_execution_id,
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
        }


@dataclass
class PaperPortfolioState:
    portfolio_id: str
    status: PortfolioStatus
    simulated_cash: float
    simulated_equity: float
    realized_pnl: float
    unrealized_pnl: float
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    holding: Optional[PaperHolding] = None
    updated_at: str = ""
    provenance: Optional[dict[str, Any]] = None
    notes: str = "paper_portfolio_simulation_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "status": self.status.value,
            "simulated_cash": self.simulated_cash,
            "simulated_equity": self.simulated_equity,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "holding": self.holding.to_dict() if self.holding else None,
            "updated_at": self.updated_at,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


def _portfolio_hash(payload: dict[str, Any]) -> str:
    return content_hash(payload)


def make_portfolio_id(seed: str = "default") -> str:
    return "pport-" + content_hash({"seed": seed, "v": SCHEMA_VERSION})[:20]


class PaperPortfolioEngine:
    """
    Deterministic paper accounting from PaperExecution + fill price.
    Unit size fixed at 1.0 for simulation (NOT capital allocation / sizing engine).
    """

    UNIT = 1.0  # fixed simulation unit — not live position sizing

    def __init__(
        self,
        *,
        initial_cash: float = 10000.0,
        max_history: int = 200,
    ) -> None:
        self.initial_cash = float(initial_cash)
        self.max_history = max_history
        self._history: list[PaperPortfolioState] = []
        self._state = self._empty_state()

    def _empty_state(self) -> PaperPortfolioState:
        payload = {
            "status": PortfolioStatus.EMPTY.value,
            "cash": self.initial_cash,
            "equity": self.initial_cash,
            "realized": 0.0,
            "unrealized": 0.0,
        }
        return PaperPortfolioState(
            portfolio_id=make_portfolio_id("empty"),
            status=PortfolioStatus.EMPTY,
            simulated_cash=self.initial_cash,
            simulated_equity=self.initial_cash,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            content_hash=_portfolio_hash(payload),
            updated_at=utc_now(),
            provenance=build_paper_provenance(payload),
        )

    @property
    def state(self) -> PaperPortfolioState:
        return self._state

    def apply(
        self,
        execution: PaperExecution,
        *,
        now_iso: Optional[str] = None,
    ) -> PaperPortfolioState:
        now = now_iso or utc_now()
        if execution.status != PaperStatus.PAPER_SIMULATED or execution.fill is None:
            return self._reject(now, "execution_not_simulated")
        price = execution.fill.reference_price
        if price is None:
            return self._reject(now, "missing_reference_price")
        if now_iso and execution.simulated_at and execution.simulated_at > now_iso:
            return self._reject(now, "future_execution")

        action = execution.action
        if action == IntentAction.PAPER_ENTER.value:
            return self._enter(execution, float(price), now)
        if action == IntentAction.PAPER_EXIT.value:
            return self._exit(execution, float(price), now)
        # NO_ACTION or unknown
        return self._state

    def mark_to_market(
        self, mark_price: float, *, now_iso: Optional[str] = None
    ) -> PaperPortfolioState:
        now = now_iso or utc_now()
        if self._state.holding is None:
            return self._state
        unrealized = (float(mark_price) - self._state.holding.entry_price) * self.UNIT
        equity = self._state.simulated_cash + (
            float(mark_price) * self.UNIT
        )
        payload = {
            "status": self._state.status.value,
            "cash": self._state.simulated_cash,
            "equity": equity,
            "realized": self._state.realized_pnl,
            "unrealized": unrealized,
            "holding": self._state.holding.symbol,
        }
        st = PaperPortfolioState(
            portfolio_id=self._state.portfolio_id,
            status=PortfolioStatus.OPEN_PAPER,
            simulated_cash=self._state.simulated_cash,
            simulated_equity=equity,
            realized_pnl=self._state.realized_pnl,
            unrealized_pnl=unrealized,
            content_hash=_portfolio_hash(payload),
            holding=self._state.holding,
            updated_at=now,
            provenance=build_paper_provenance(payload),
        )
        self._state = st
        self._push(st)
        return st

    def _enter(
        self, execution: PaperExecution, price: float, now: str
    ) -> PaperPortfolioState:
        if self._state.holding is not None:
            # already open — idempotent if same execution
            if (
                self._state.holding.paper_execution_id
                == execution.paper_execution_id
            ):
                return self._state
            return self._reject(now, "already_open")
        cost = price * self.UNIT
        cash = self._state.simulated_cash - cost
        holding = PaperHolding(
            symbol=execution.symbol,
            entry_price=price,
            entry_at=execution.simulated_at,
            paper_execution_id=execution.paper_execution_id,
            intent_id=execution.intent_id,
            decision_id=execution.decision_id,
            cycle_id=execution.cycle_id,
        )
        payload = {
            "status": PortfolioStatus.OPEN_PAPER.value,
            "cash": cash,
            "equity": cash + cost,
            "realized": self._state.realized_pnl,
            "unrealized": 0.0,
            "exec": execution.paper_execution_id,
        }
        st = PaperPortfolioState(
            portfolio_id=make_portfolio_id(execution.paper_execution_id),
            status=PortfolioStatus.OPEN_PAPER,
            simulated_cash=cash,
            simulated_equity=cash + cost,
            realized_pnl=self._state.realized_pnl,
            unrealized_pnl=0.0,
            content_hash=_portfolio_hash(payload),
            holding=holding,
            updated_at=now,
            provenance=build_paper_provenance(payload),
        )
        self._state = st
        self._push(st)
        return st

    def _exit(
        self, execution: PaperExecution, price: float, now: str
    ) -> PaperPortfolioState:
        if self._state.holding is None:
            return self._reject(now, "no_open_holding")
        if execution.symbol != self._state.holding.symbol:
            return self._reject(now, "symbol_mismatch")
        if (
            self._state.holding.entry_at
            and execution.simulated_at
            and execution.simulated_at < self._state.holding.entry_at
        ):
            return self._reject(now, "exit_before_entry")
        pnl = (price - self._state.holding.entry_price) * self.UNIT
        cash = self._state.simulated_cash + price * self.UNIT
        realized = self._state.realized_pnl + pnl
        payload = {
            "status": PortfolioStatus.CLOSED_PAPER.value,
            "cash": cash,
            "equity": cash,
            "realized": realized,
            "unrealized": 0.0,
            "exec": execution.paper_execution_id,
        }
        st = PaperPortfolioState(
            portfolio_id=make_portfolio_id(execution.paper_execution_id + "-exit"),
            status=PortfolioStatus.CLOSED_PAPER,
            simulated_cash=cash,
            simulated_equity=cash,
            realized_pnl=realized,
            unrealized_pnl=0.0,
            content_hash=_portfolio_hash(payload),
            holding=None,
            updated_at=now,
            provenance=build_paper_provenance(payload),
        )
        self._state = st
        self._push(st)
        return st

    def _reject(self, now: str, reason: str) -> PaperPortfolioState:
        payload = {
            "status": PortfolioStatus.INVALID.value,
            "reason": reason,
            "cash": self._state.simulated_cash,
        }
        st = PaperPortfolioState(
            portfolio_id=self._state.portfolio_id,
            status=PortfolioStatus.INVALID,
            simulated_cash=self._state.simulated_cash,
            simulated_equity=self._state.simulated_equity,
            realized_pnl=self._state.realized_pnl,
            unrealized_pnl=self._state.unrealized_pnl,
            content_hash=_portfolio_hash(payload),
            holding=self._state.holding,
            updated_at=now,
            provenance=build_paper_provenance(payload),
            notes=reason,
        )
        # do not overwrite open state on reject — return diagnostic only
        return st

    def _push(self, st: PaperPortfolioState) -> None:
        self._history.append(st)
        while len(self._history) > self.max_history:
            self._history.pop(0)

    def history(self) -> list[PaperPortfolioState]:
        return list(self._history)
