"""Corporate-action transformations are explicit, replayable events."""
from dataclasses import dataclass
@dataclass(frozen=True)
class PositionAdjustment:
    symbol:str; quantity_multiplier:float=1.0; price_multiplier:float=1.0; cash_dividend:float=0.0; reference:str=''
