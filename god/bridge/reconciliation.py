"""Reconciliation — compare brain view vs terminal/broker view.

After reconnect / crash / restart: never assume state is still valid.
Broker/terminal state is the external fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from god.ipc.models import Message, MessageType
from god.ipc.protocols import IPCTransport
from .errors import ReconciliationError
from god.memory.database import utc_now


@dataclass
class ReconciliationReport:
    """Result of a reconcile pass."""

    timestamp: str
    success: bool
    brain_positions: list = field(default_factory=list)
    terminal_positions: list = field(default_factory=list)
    brain_orders: list = field(default_factory=list)
    terminal_orders: list = field(default_factory=list)
    discrepancies: list = field(default_factory=list)
    account: dict = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "success": self.success,
            "brain_positions": list(self.brain_positions),
            "terminal_positions": list(self.terminal_positions),
            "brain_orders": list(self.brain_orders),
            "terminal_orders": list(self.terminal_orders),
            "discrepancies": list(self.discrepancies),
            "account": dict(self.account),
            "message": self.message,
        }


def compare_positions(
    brain: Sequence[dict], terminal: Sequence[dict], id_key: str = "position_id"
) -> list[dict]:
    """Return discrepancy records (brain believes X, terminal reports Y)."""
    brain_map = {str(p.get(id_key) or p.get("ticket") or i): p for i, p in enumerate(brain)}
    term_map = {str(p.get(id_key) or p.get("ticket") or i): p for i, p in enumerate(terminal)}
    discs: list[dict] = []
    for k, bp in brain_map.items():
        tp = term_map.get(k)
        if tp is None:
            discs.append(
                {
                    "type": "position_missing_on_terminal",
                    "id": k,
                    "brain": bp,
                    "terminal": None,
                }
            )
        else:
            b_status = (bp.get("status") or "").upper()
            t_status = (tp.get("status") or "").upper()
            if b_status and t_status and b_status != t_status:
                discs.append(
                    {
                        "type": "position_status_mismatch",
                        "id": k,
                        "brain": bp,
                        "terminal": tp,
                    }
                )
    for k, tp in term_map.items():
        if k not in brain_map:
            discs.append(
                {
                    "type": "position_unexpected_on_terminal",
                    "id": k,
                    "brain": None,
                    "terminal": tp,
                }
            )
    return discs


class Reconciler:
    """Drive RECONCILE_REQUEST over IPC and compare local vs remote."""

    def __init__(
        self,
        transport: IPCTransport,
        *,
        source: str = "brain",
        destination: str = "ea",
    ) -> None:
        self.transport = transport
        self.source = source
        self.destination = destination

    def reconcile(
        self,
        brain_positions: Optional[Sequence[dict]] = None,
        brain_orders: Optional[Sequence[dict]] = None,
        timeout: float = 10.0,
    ) -> ReconciliationReport:
        brain_positions = list(brain_positions or [])
        brain_orders = list(brain_orders or [])
        req = Message.create(
            message_type=MessageType.RECONCILE_REQUEST,
            source=self.source,
            destination=self.destination,
            payload={"include": ["account", "positions", "orders"]},
        )
        try:
            resp = self.transport.request(req, timeout=timeout)
        except Exception as e:
            raise ReconciliationError(f"reconcile request failed: {e}") from e
        if resp.message_type != MessageType.RECONCILE_RESPONSE:
            raise ReconciliationError(
                f"expected RECONCILE_RESPONSE, got {resp.message_type}"
            )
        payload = resp.payload or {}
        term_positions = list(payload.get("positions") or [])
        term_orders = list(payload.get("orders") or [])
        account = dict(payload.get("account") or {})
        discs = compare_positions(brain_positions, term_positions)
        # Simple order discrepancy: count mismatch only at this phase
        if len(brain_orders) != len(term_orders):
            discs.append(
                {
                    "type": "order_count_mismatch",
                    "brain_count": len(brain_orders),
                    "terminal_count": len(term_orders),
                }
            )
        return ReconciliationReport(
            timestamp=utc_now(),
            success=True,
            brain_positions=brain_positions,
            terminal_positions=term_positions,
            brain_orders=brain_orders,
            terminal_orders=term_orders,
            discrepancies=discs,
            account=account,
            message="reconciled" if not discs else f"{len(discs)} discrepancy(ies)",
        )
