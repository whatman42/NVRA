"""Config-driven Indonesian transaction cost accounting; no hardcoded tax policy."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CostBreakdown:
    commission: float=0.0
    exchange_fee: float=0.0
    tax: float=0.0
    slippage: float=0.0
    impact: float=0.0
    @property
    def total(self): return self.commission+self.exchange_fee+self.tax+self.slippage+self.impact

def estimate_cost(notional: float, *, commission_bps=0.0, exchange_bps=0.0, sell_tax_bps=0.0, slippage_bps=0.0, impact_bps=0.0, is_sell=False):
    return CostBreakdown(notional*commission_bps/10000, notional*exchange_bps/10000, notional*sell_tax_bps/10000 if is_sell else 0.0, notional*slippage_bps/10000, notional*impact_bps/10000)
