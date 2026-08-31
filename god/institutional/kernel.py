"""Institutional kernel: data→intelligence→risk→execution with checkpoint/recovery boundaries."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any,Callable,Mapping
import uuid
from .contracts import Message,MessageKind,DecisionPacket
from .message_bus import MessageBus
from .checkpoint import CheckpointStore
from .resource_profiles import HardwareResourceProfile,WorkloadPolicy,policy_for

@dataclass(frozen=True)
class KernelConfig:
    state_dir:str="~/.nvrafx/state"
    max_bus_queue:int=2048
    hardware_profile:HardwareResourceProfile=HardwareResourceProfile.LOW_END_8GB
    checkpoint_enabled:bool=True
    max_debate_rounds:int=1

class InstitutionalKernel:
    """Composition root. Risk/execution are injected and remain final authorities."""
    def __init__(self,config:KernelConfig|None=None, *, risk_gate:Callable[[DecisionPacket],DecisionPacket]|None=None,
                 executor:Callable[[DecisionPacket],Any]|None=None)->None:
        self.config=config or KernelConfig()
        self.policy:WorkloadPolicy=policy_for(self.config.hardware_profile)
        rounds=min(self.config.max_debate_rounds,self.policy.agent_debate_rounds)
        self.bus=MessageBus(self.config.max_bus_queue)
        self.checkpoints=CheckpointStore(Path(self.config.state_dir).expanduser()/"institutional_checkpoints.db")
        self.risk_gate=risk_gate or (lambda d:d)
        self.executor=executor or (lambda d:{"status":"PAPER_ONLY","action":d.action,"symbol":d.symbol})
        self.run_id=uuid.uuid4().hex
        self.bus.subscribe("kernel.decision",self._on_decision)
        self.last_result:Any=None
        self.rounds=rounds
    def publish_observation(self,symbol:str,context:Mapping[str,object])->str:
        msg=Message(MessageKind.DATA,"kernel.observation",{"symbol":symbol,"context":dict(context)},self.run_id)
        if not self.bus.publish(msg): raise RuntimeError("kernel bus backpressure")
        self.checkpoints.save(self.run_id,"observation",dict(msg.payload)); return msg.message_id
    def submit_decision(self,decision:DecisionPacket)->str:
        msg=Message(MessageKind.DECISION,"kernel.decision",{"decision":decision},self.run_id)
        if not self.bus.publish(msg): raise RuntimeError("kernel bus backpressure")
        self.checkpoints.save(self.run_id,"decision",{"symbol":decision.symbol,"action":decision.action,"confidence":decision.confidence})
        return msg.message_id
    def _on_decision(self,msg:Message)->None:
        decision=msg.payload["decision"]
        gated=self.risk_gate(decision)
        self.checkpoints.save(self.run_id,"risk_gated",{"symbol":gated.symbol,"action":gated.action,"confidence":gated.confidence})
        self.last_result=self.executor(gated)
        self.checkpoints.save(self.run_id,"executed",{"result":self.last_result})
    def drain(self)->int:return self.bus.drain()
    def status(self)->dict[str,Any]:
        return {"run_id":self.run_id,"hardware_profile":self.policy.profile.value,"max_active_models":self.policy.max_active_models,
                "heavy_ml_inference":self.policy.heavy_ml_inference,"heavy_ml_training":self.policy.heavy_ml_training,
                "queue":self.bus.stats(),"last_result":self.last_result}
