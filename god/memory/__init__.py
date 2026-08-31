"""Persistent Memory Layer — SQLite source of truth for GOD agent.

No trading intelligence lives here. This package only provides
schema, migrations, typed repositories, transactions, and integrity.
"""

from .database import Database, DatabaseError, IntegrityError
from .models import (
    Experience,
    Trade,
    Position,
    Strategy,
    StrategyVersion,
    Experiment,
    ExperimentResult,
    KnowledgeClaim,
    Hypothesis,
    Observation,
    Decision,
    RiskEvent,
    CapabilityEvent,
    AuditRecord,
    AgentState,
    ModelArtifact,
)
from .repositories import MemoryStore

__all__ = [
    "Database",
    "DatabaseError",
    "IntegrityError",
    "MemoryStore",
    "Experience",
    "Trade",
    "Position",
    "Strategy",
    "StrategyVersion",
    "Experiment",
    "ExperimentResult",
    "KnowledgeClaim",
    "Hypothesis",
    "Observation",
    "Decision",
    "RiskEvent",
    "CapabilityEvent",
    "AuditRecord",
    "AgentState",
    "ModelArtifact",
]
