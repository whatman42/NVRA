"""Typed multi-agent research graph, inspired by TradingAgents without an LLM dependency."""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Callable, Mapping
from .contracts import AgentEvidence, DecisionPacket

@dataclass(frozen=True)
class AnalystReport:
    role:str
    symbol:str
    stance:str
    confidence:float
    evidence:tuple[AgentEvidence,...]=()
    risks:tuple[str,...]=()

@dataclass
class AgentGraph:
    """Deterministic analyst→debate→trader graph.

    Callables are dependency-injected so LLMs are advisory plugins, never execution authorities.
    """
    analysts:list[Callable[[str,Mapping[str,object]],AnalystReport]]=field(default_factory=list)
    debate_rounds:int=1
    def run(self,symbol:str,context:Mapping[str,object])->DecisionPacket:
        reports=[a(symbol,context) for a in self.analysts]
        if not reports: return DecisionPacket(symbol,"NO_ACTION",0.0,"no analyst evidence")
        bullish=sum(r.confidence for r in reports if r.stance=="BULLISH")
        bearish=sum(r.confidence for r in reports if r.stance=="BEARISH")
        if bullish>bearish and bullish>0: action="BUY"
        elif bearish>bullish and bearish>0: action="SELL"
        else: action="HOLD"
        conf=min(1.0,abs(bullish-bearish)/max(1.0,sum(r.confidence for r in reports)))
        evidence=tuple(e for r in reports for e in r.evidence)
        risks=tuple(x for r in reports for x in r.risks)
        return DecisionPacket(symbol,action,conf,f"aggregated {len(reports)} analyst reports",evidence,risks,(), "session",0.0,(),context.get("correlation_id",""))
