"""Durable write-ahead order journal and idempotency primitives."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json, hashlib, time
@dataclass
class OrderRecord:
    intent_id:str; symbol:str; side:str; quantity:float; price:float|None; status:str='INTENT_CREATED'; broker_order_id:str|None=None; ts:float=0.0
class OrderJournal:
    def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    @staticmethod
    def idempotency_key(symbol,side,signal_id,strategy_version): return hashlib.sha256(f'{symbol}|{side}|{signal_id}|{strategy_version}'.encode()).hexdigest()
    def append(self, rec:OrderRecord):
        rec.ts=rec.ts or time.time()
        with self.path.open('a',encoding='utf-8') as f: f.write(json.dumps(asdict(rec),sort_keys=True)+'\n')
    def records(self):
        if not self.path.exists(): return []
        out=[]
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if line.strip(): out.append(OrderRecord(**json.loads(line)))
        return out
