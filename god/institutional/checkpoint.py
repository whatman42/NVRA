"""Tiny SQLite checkpoint store; no framework dependency and safe for low-end PCs."""
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from typing import Any
class CheckpointStore:
    def __init__(self,path:str|Path)->None:
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS checkpoints (run_id TEXT PRIMARY KEY, node TEXT NOT NULL, state_json TEXT NOT NULL, updated_ns INTEGER NOT NULL)")
            c.commit()
    def save(self,run_id:str,node:str,state:dict[str,Any])->None:
        payload=json.dumps(state,sort_keys=True,separators=(",",":"),default=str)
        with sqlite3.connect(self.path) as c:
            c.execute("INSERT INTO checkpoints VALUES(?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET node=excluded.node,state_json=excluded.state_json,updated_ns=excluded.updated_ns",(run_id,node,payload,time.time_ns()))
            c.commit()
    def load(self,run_id:str)->dict[str,Any]|None:
        with sqlite3.connect(self.path) as c:
            row=c.execute("SELECT node,state_json,updated_ns FROM checkpoints WHERE run_id=?",(run_id,)).fetchone()
        if not row:return None
        return {"node":row[0],"state":json.loads(row[1]),"updated_ns":row[2]}
    def clear(self,run_id:str)->None:
        with sqlite3.connect(self.path) as c:c.execute("DELETE FROM checkpoints WHERE run_id=?",(run_id,)); c.commit()
