"""Fail-closed broker/local reconciliation. UNKNOWN is never treated as FAILED."""
from dataclasses import dataclass
@dataclass(frozen=True)
class ReconciliationResult:
    healthy: bool; safe_mode: bool; reasons: tuple[str,...]=()
def reconcile(local_positions, broker_positions, local_orders=None, broker_orders=None):
    reasons=[]
    if local_positions != broker_positions: reasons.append('position_mismatch')
    if local_orders is not None and broker_orders is not None:
        local_unknown={x for x in local_orders if getattr(x,'status',x)=='UNKNOWN'}
        if local_unknown: reasons.append('unknown_order_requires_resolution')
    return ReconciliationResult(not reasons, bool(reasons), tuple(reasons))
