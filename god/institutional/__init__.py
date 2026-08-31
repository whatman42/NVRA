"""NVRA institutional runtime primitives.

Adapted architecture patterns: deterministic event-driven kernel (NautilusTrader)
and typed multi-agent research/checkpoint concepts (TradingAgents).  No third-party
runtime dependency is required by this package.
"""
from .kernel import InstitutionalKernel, KernelConfig
from .resource_profiles import HardwareResourceProfile, recommend_profile
from .execution_state import OrderLifecycle, OrderState
from .agent_graph import AgentGraph, DecisionPacket
__all__ = ["InstitutionalKernel","KernelConfig","HardwareResourceProfile","recommend_profile",
           "OrderLifecycle","OrderState","AgentGraph","DecisionPacket"]
