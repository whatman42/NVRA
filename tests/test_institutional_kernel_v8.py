from god.institutional.agent_graph import AgentGraph, AnalystReport
from god.institutional.contracts import AgentEvidence, DecisionPacket, Message, MessageKind
from god.institutional.execution_state import OrderLifecycle, OrderState
from god.institutional.resource_profiles import HardwareResourceProfile, policy_for, recommend_profile
from god.ml.hardware import HardwareSnapshot, build_resource_limits, HardwareProfile
from god.ml.model_capabilities import ModelCapabilityRegistry
from god.institutional.kernel import InstitutionalKernel, KernelConfig

def _analyst(stance):
    def run(symbol, ctx):
        return AnalystReport("test", symbol, stance, 0.8, (AgentEvidence("unit", stance, 0.8, 1),), ())
    return run

def test_low_end_policy_preserves_ml_inference_and_serializes_training():
    p=policy_for(HardwareResourceProfile.LOW_END_8GB)
    assert p.training_enabled and p.max_parallel_models == 1
    assert not p.heavy_ml_training and p.max_active_models >= 6

def test_recommended_profile():
    snap=HardwareSnapshot(total_ram_mb=16_384, available_ram_mb=12_000, cpu_threads=8)
    limits=build_resource_limits(snap, HardwareProfile.BALANCED)
    assert not limits.allow_heavy_ml
    assert limits.allow_heavy_ml_inference
    assert "random_forest" in ModelCapabilityRegistry(gpu_available=False).inference_runnable(limits)

    assert recommend_profile(16_384, 8) == HardwareResourceProfile.RECOMMENDED_16GB
    assert recommend_profile(8_192, 4) == HardwareResourceProfile.LOW_END_8GB

def test_agent_graph_structured_decision():
    g=AgentGraph([_analyst("BULLISH"), _analyst("BEARISH")])
    d=g.run("BBCA", {"correlation_id":"r1"})
    assert isinstance(d, DecisionPacket)
    assert d.action == "HOLD" and len(d.evidence) == 2

def test_order_lifecycle_is_idempotent_and_reconciles_unknown():
    o=OrderLifecycle("o1")
    assert o.apply("e1", OrderState.ACCEPTED)
    assert not o.apply("e1", OrderState.ACCEPTED)
    assert o.apply("e2", OrderState.RELEASED)
    assert o.apply("e3", OrderState.UNKNOWN)
    assert o.needs_reconciliation

def test_kernel_checkpoint_and_risk_boundary(tmp_path):
    seen=[]
    def risk(d):
        return DecisionPacket(d.symbol, "HOLD", d.confidence, "risk gated", d.evidence, d.risks)
    k=InstitutionalKernel(KernelConfig(state_dir=str(tmp_path)), risk_gate=risk, executor=lambda d: seen.append(d.action) or {"ok":True})
    k.submit_decision(DecisionPacket("BBCA","BUY",0.9,"test", suggested_size=0.1))
    assert k.drain()==1 and seen == ["HOLD"]
    assert k.checkpoints.load(k.run_id)["node"]=="executed"

def test_message_bus_backpressure():
    from god.institutional.message_bus import MessageBus
    b=MessageBus(1)
    assert b.publish(Message(MessageKind.DATA,"x",{}, "c"))
    assert not b.publish(Message(MessageKind.DATA,"x",{}, "c"))
