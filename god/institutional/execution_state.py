"""Explicit idempotent order lifecycle inspired by event-driven execution engines."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

class OrderState(str,Enum):
    INITIALIZED="INITIALIZED"; ACCEPTED="ACCEPTED"; RELEASED="RELEASED"; PARTIALLY_FILLED="PARTIALLY_FILLED"
    FILLED="FILLED"; CANCELED="CANCELED"; REJECTED="REJECTED"; EXPIRED="EXPIRED"; UNKNOWN="UNKNOWN"

_TRANSITIONS={
OrderState.INITIALIZED:{OrderState.ACCEPTED,OrderState.REJECTED,OrderState.CANCELED},
OrderState.ACCEPTED:{OrderState.RELEASED,OrderState.REJECTED,OrderState.CANCELED},
OrderState.RELEASED:{OrderState.PARTIALLY_FILLED,OrderState.FILLED,OrderState.CANCELED,OrderState.EXPIRED,OrderState.UNKNOWN},
OrderState.PARTIALLY_FILLED:{OrderState.PARTIALLY_FILLED,OrderState.FILLED,OrderState.CANCELED,OrderState.UNKNOWN},
OrderState.UNKNOWN:{OrderState.ACCEPTED,OrderState.RELEASED,OrderState.PARTIALLY_FILLED,OrderState.FILLED,OrderState.CANCELED,OrderState.EXPIRED,OrderState.UNKNOWN},
}
_TERMINAL={OrderState.FILLED,OrderState.CANCELED,OrderState.REJECTED,OrderState.EXPIRED}

@dataclass
class OrderLifecycle:
    order_id:str
    state:OrderState=OrderState.INITIALIZED
    seen_events:set[str]=field(default_factory=set)
    history:list[OrderState]=field(default_factory=list)
    def apply(self,event_id:str,new_state:OrderState)->bool:
        if event_id in self.seen_events: return False
        if self.state in _TERMINAL:
            raise ValueError(f"terminal order cannot transition: {self.state.value}")
        if new_state not in _TRANSITIONS.get(self.state,set()):
            raise ValueError(f"invalid transition {self.state.value}->{new_state.value}")
        self.seen_events.add(event_id); self.state=new_state; self.history.append(new_state); return True
    @property
    def needs_reconciliation(self)->bool: return self.state==OrderState.UNKNOWN
