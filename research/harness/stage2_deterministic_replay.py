"""Stage 2 deterministic replay harness — INTEGRATED_PARTIAL product path."""
from __future__ import annotations
import hashlib, json, platform, sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

def stable_hash(obj: Any) -> str:
    if isinstance(obj, (bytes, bytearray)):
        data = bytes(obj)
    elif isinstance(obj, str):
        data = obj.encode()
    else:
        data = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(data).hexdigest()

@dataclass
class ReplayConfig:
    seed: int = 42
    symbol: str = "EURUSD"
    n_bars: int = 32
    risk_max_position: float = 1.0
    correlation_id: str = "stage2-replay"

@dataclass
class ReplayResult:
    experiment_id: str
    run_id: str
    git_commit: str
    python_version: str
    platform: str
    seed: int
    input_hash: str
    config_hash: str
    event_stream_hash: str
    analysis_hash: str
    decision_hash: str
    risk_hash: str
    execution_intent_hash: str
    reconciliation_hash: str
    state_hash: str
    artifact_hash: str
    final_result_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)
    def semantic_bundle(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in (
            "input_hash","event_stream_hash","analysis_hash","decision_hash","risk_hash",
            "execution_intent_hash","reconciliation_hash","state_hash","artifact_hash","final_result_hash")}

def _bars(seed: int, n: int, symbol: str):
    x, price, out = seed & 0xFFFFFFFF, 1.1, []
    for i in range(n):
        x = (1664525 * x + 1013904223) & 0xFFFFFFFF
        price = round(price + ((x % 2001) - 1000) / 1e6, 5)
        out.append({"i": i, "symbol": symbol, "close": price, "logical_ts": 1_700_000_000_000 + i * 60_000})
    return out

def _analysis(bars):
    closes = [b["close"] for b in bars]
    mean = sum(closes) / len(closes)
    var = sum((c - mean) ** 2 for c in closes) / len(closes)
    return {"n": len(closes), "mean": round(mean, 8), "var": round(var, 12), "trend": round(closes[-1]-closes[0], 8), "last": closes[-1]}

def _decision(analysis, seed):
    return {"side": "BUY" if analysis["trend"] >= 0 else "SELL", "size": 0.1 if analysis["var"] < 1e-6 else 0.05, "mode": "PAPER", "live_authorized": False, "seed": seed}

def _risk(decision, cfg):
    return {"allowed": decision["size"] <= cfg.risk_max_position, "safety_mode": "NORMAL", "live_authorized": False, "requested_size": decision["size"], "max_position": cfg.risk_max_position}

def _intent(decision, risk):
    if not risk.get("allowed"):
        return {"status": "BLOCKED", "live_authorized": False, "client_order_id": None}
    body = {"side": decision["side"], "size": decision["size"], "mode": "PAPER"}
    return {"status": "INTENT_RECORDED", "mode": "PAPER", "live_authorized": False, "client_order_id": "coid-" + stable_hash(body)[:20], "side": decision["side"], "size": decision["size"]}

def _events(cfg, analysis):
    from god.orchestration.bus import EventBus
    from god.orchestration.models import EventType, create_context, create_event
    bus = EventBus(maxsize=256)
    ctx = create_context(correlation_id=cfg.correlation_id, created_at="L0")
    events = []
    for seq, (etype, parent, payload) in enumerate([
        (EventType.OBSERVATION, None, {"analysis_mean": analysis["mean"], "symbol": cfg.symbol}),
        (EventType.RESEARCH, "prev", {"from": "observation"}),
        (EventType.STRATEGY, "prev", {"trend": analysis["trend"]}),
    ]):
        parent_id = events[-1]["event_id"] if events and parent else None
        e = create_event(etype, correlation_id=cfg.correlation_id, context_id=ctx.context_id, parent_event_id=parent_id, payload_ref=payload, sequence=seq)
        bus.publish(e)
        events.append(e.to_dict())
    while bus.consume() is not None:
        pass
    return events

def run_replay(cfg: ReplayConfig, *, run_id: str = "run-0", experiment_id: str = "S2-REPLAY", git_commit: str = "unknown", event_order: Optional[str] = None) -> ReplayResult:
    bars = _bars(cfg.seed, cfg.n_bars, cfg.symbol)
    input_hash = stable_hash(bars)
    config_hash = stable_hash({"seed": cfg.seed, "symbol": cfg.symbol, "n_bars": cfg.n_bars, "risk_max_position": cfg.risk_max_position, "correlation_id": cfg.correlation_id})
    analysis = _analysis(bars)
    analysis_hash = stable_hash(analysis)
    decision = _decision(analysis, cfg.seed)
    decision_hash = stable_hash(decision)
    risk = _risk(decision, cfg)
    risk_hash = stable_hash(risk)
    intent = _intent(decision, risk)
    execution_intent_hash = stable_hash(intent)
    events = _events(cfg, analysis)
    if event_order == "reversed":
        events = list(reversed(events))
    event_stream_hash = stable_hash(events)
    recon = {"ok": bool(risk.get("allowed")), "live_authorized": False, "mode": "PAPER"}
    reconciliation_hash = stable_hash(recon)
    state = {"analysis": analysis, "decision": decision, "risk": risk, "intent": intent, "recon": recon, "event_ids": [e["event_id"] for e in events]}
    state_hash = stable_hash(state)
    artifact = {"input_hash": input_hash, "analysis_hash": analysis_hash, "decision_hash": decision_hash, "risk_hash": risk_hash, "execution_intent_hash": execution_intent_hash, "event_stream_hash": event_stream_hash, "reconciliation_hash": reconciliation_hash, "state_hash": state_hash}
    artifact_hash = stable_hash(artifact)
    final_result_hash = stable_hash({"artifact_hash": artifact_hash, "state_hash": state_hash, "config_hash": config_hash})
    return ReplayResult(experiment_id=experiment_id, run_id=run_id, git_commit=git_commit, python_version=sys.version.split()[0], platform=platform.platform(), seed=cfg.seed, input_hash=input_hash, config_hash=config_hash, event_stream_hash=event_stream_hash, analysis_hash=analysis_hash, decision_hash=decision_hash, risk_hash=risk_hash, execution_intent_hash=execution_intent_hash, reconciliation_hash=reconciliation_hash, state_hash=state_hash, artifact_hash=artifact_hash, final_result_hash=final_result_hash, metadata={"event_order": event_order or "canonical", "n_events": len(events)})

def run_n(cfg: ReplayConfig, n: int = 100, **kwargs: Any):
    return [run_replay(cfg, run_id=f"run-{i}", **kwargs) for i in range(n)]
