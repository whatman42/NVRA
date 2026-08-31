"""IDX-aware order validation primitives. Rules are configurable and effective-dated."""
from dataclasses import dataclass

@dataclass(frozen=True)
class OrderCheck:
    ok: bool
    reasons: tuple[str, ...] = ()

def tick_size(price: float) -> int:
    p=float(price)
    if p < 200: return 1
    if p < 500: return 2
    if p < 2000: return 5
    if p < 5000: return 10
    return 25

def validate_idx_order(price: float, shares: int, *, last_price: float|None=None, ara_pct: float|None=None, arb_pct: float|None=None) -> OrderCheck:
    reasons=[]
    if price <= 0: reasons.append('invalid_price')
    if shares < 100 or shares % 100: reasons.append('invalid_lot_size')
    tick=tick_size(price)
    if int(round(price)) % tick: reasons.append(f'invalid_tick_size:{tick}')
    if last_price and ara_pct is not None and price > last_price*(1+ara_pct): reasons.append('above_ara')
    if last_price and arb_pct is not None and price < last_price*(1-arb_pct): reasons.append('below_arb')
    return OrderCheck(not reasons, tuple(reasons))
