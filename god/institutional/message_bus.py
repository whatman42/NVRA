"""Bounded deterministic message bus: pub/sub + request handlers + backpressure."""
from __future__ import annotations
from collections import defaultdict, deque
from threading import RLock
from typing import Callable
from .contracts import Message

Handler=Callable[[Message],None]

class MessageBus:
    def __init__(self,max_queue:int=2048)->None:
        if max_queue<1: raise ValueError("max_queue must be positive")
        self._max=max_queue; self._q=deque(); self._subs=defaultdict(list); self._seen=set()
        self._lock=RLock(); self._dropped=0; self._errors=0
    def subscribe(self,topic:str,handler:Handler)->None:
        with self._lock:
            if handler not in self._subs[topic]: self._subs[topic].append(handler)
    def publish(self,msg:Message)->bool:
        with self._lock:
            if msg.message_id in self._seen: return True
            if len(self._q)>=self._max: self._dropped+=1; return False
            self._seen.add(msg.message_id); self._q.append(msg); return True
    def drain(self,max_messages:int|None=None)->int:
        count=0
        while max_messages is None or count<max_messages:
            with self._lock:
                if not self._q: break
                msg=self._q.popleft(); handlers=tuple(self._subs.get(msg.topic,()))+tuple(self._subs.get("*",()))
            for h in handlers:
                try: h(msg)
                except Exception: self._errors+=1
            count+=1
        return count
    def stats(self)->dict[str,int]:
        with self._lock: return {"queued":len(self._q),"seen":len(self._seen),"dropped":self._dropped,"handler_errors":self._errors}
